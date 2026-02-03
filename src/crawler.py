import asyncio
import re
import json
from typing import Optional, List
import aiohttp
from bs4 import BeautifulSoup  # 确保已安装 beautifulsoup4
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# 相对导入
from .config import BASE_URL_TEMPLATE, SELECTORS
from .schema import RawNewsItem, DailyBriefing, NewsType

class CrawlerService:
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            text_mode=False
        )

    async def fetch_daily_briefing(self, date_str) -> Optional[DailyBriefing]:
        """
        统一入口函数：获取当天的完整简报数据
        """
        # 1. 获取列表
        abstract_item, news_items_links = await self._fetch_daily_list(date_str)
        if not abstract_item:
            return None

        # 2. 获取详情
        abstract_text, details_list = await self._fetch_full_content(abstract_item, news_items_links)

        # 3. 组装 Pydantic 对象
        raw_items = []
        for detail in details_list:
            raw_items.append(RawNewsItem(
                title=detail.get('title', 'No Title'),
                url=detail.get('original_url', ''),
                content=detail.get('content', ''),
                date=date_str,
                type=detail.get('type', NewsType.NORMAL),
                parent_url=detail.get('parent_url', None)
            ))
        
        return DailyBriefing(
            date=date_str,
            abstract_text=abstract_text,
            news_items=raw_items
        )

    async def _fetch_daily_list(self, date_str):
        # 保持原有的列表获取逻辑不变
        url = BASE_URL_TEMPLATE.format(date_str=date_str)
        print(f"[*] [Direct] 正在下载列表: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200: return None, []
                    content_bytes = await response.read()
            
            html_content = content_bytes.decode('utf-8', errors='ignore')
            pattern = re.compile(r'<a\s+[^>]*?href=[\'"](.*?)[\'"][^>]*?title=[\'"](.*?)[\'"]', re.IGNORECASE)
            matches = pattern.findall(html_content)
            
            if not matches:
                 pattern_text = re.compile(r'<a\s+[^>]*?href=[\'"](.*?)[\'"][^>]*?>(.*?)</a>', re.IGNORECASE)
                 matches = pattern_text.findall(html_content)

            unique_items = {}
            for url, title in matches:
                if not url or not title: continue
                if url in unique_items: continue
                clean_title = title.replace('[视频]', '').strip()
                unique_items[url] = {'url': url, 'title': clean_title}

            final_list = list(unique_items.values())
            if not final_list: return None, []
            return final_list[0], final_list[1:]
        except Exception as e:
            print(f"[Error] 列表获取异常: {e}")
            return None, []

    async def _fetch_full_content(self, abstract_item, news_items):
        url_map = {item['url']: item['title'] for item in news_items}
        
        async def get_abstract():
            # 摘要页通常格式比较简单，保持原样或也可以应用格式化
            schema = SELECTORS["abstract_schema"]
            config = CrawlerRunConfig(extraction_strategy=JsonCssExtractionStrategy(schema))
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                res = await crawler.arun(url=abstract_item['url'], config=config)
                if res.success:
                    # 尝试用 BS4 提取以获得更好的格式，如果失败则回退
                    formatted = self._extract_normal_content(res.html)
                    if formatted: return formatted
                    
                    data = json.loads(res.extracted_content)
                    return data[0]['raw_content'] if data else ""
                return ""

        async def get_details():
            urls = [item['url'] for item in news_items]
            # 依然使用 CSS 策略作为兜底，但主要依赖 res.html 解析
            schema = SELECTORS["news_detail_schema"]
            config = CrawlerRunConfig(
                extraction_strategy=JsonCssExtractionStrategy(schema),
                cache_mode=CacheMode.BYPASS
            )
            
            results_list = []
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                crawl_results = await crawler.arun_many(urls=urls, config=config)
                
                for res in crawl_results:
                    if not res.success:
                        continue

                    original_title = url_map.get(res.url, "Unknown Title")
                    
                    # --- 分支 A: 快讯 (包含多个子新闻) ---
                    if "快讯" in original_title:
                        # print(f"⚡ 发现快讯: {original_title}")
                        sub_items = self._extract_flash_sub_items(res.html, res.url, original_title)
                        if sub_items:
                            results_list.extend(sub_items)
                            continue 
                        else:
                            print(f"⚠️ 快讯拆解失败，回退: {original_title}")

                    # --- 分支 B: 普通新闻 (保持格式) ---
                    # [修改点] 不再直接使用 extracted_content，而是手动解析 HTML 以保留格式
                    formatted_content = self._extract_normal_content(res.html)
                    
                    # 只有当手动解析失败时，才回退到 Crawl4AI 的自动提取
                    if not formatted_content:
                        data = json.loads(res.extracted_content)
                        if data:
                            formatted_content = data[0].get('content', '')

                    results_list.append({
                        "title": original_title,
                        "content": formatted_content, # 这里现在包含了缩进和换行
                        "original_url": res.url,
                        "type": NewsType.NORMAL,
                        "parent_url": None
                    })
            
            # 重新排序
            ordered_results = []
            for item in news_items:
                target_url = item['url']
                related = [
                    r for r in results_list 
                    if r.get('original_url') == target_url or r.get('parent_url') == target_url
                ]
                ordered_results.extend(related)
            return ordered_results

        abstract_text, details_list = await asyncio.gather(get_abstract(), get_details())
        return abstract_text, details_list

    def _extract_normal_content(self, html_source: str) -> str:
        """
        [新增] 专门用于提取普通新闻正文，保留段落缩进和换行
        """
        if not html_source: return ""
        soup = BeautifulSoup(html_source, 'lxml')
        
        # CCTV 正文通常在 #content_area
        content_div = soup.find(id="content_area")
        if not content_div:
            return ""

        paragraphs = []
        for p in content_div.find_all('p', recursive=False):
            text = p.get_text(strip=True)
            if text:
                # 核心技巧：手动添加两个全角空格 (\u3000) 实现缩进
                formatted_p = f"\u3000\u3000{text}"
                paragraphs.append(formatted_p)
        
        # 用换行符连接各段落
        return "\n".join(paragraphs)

    def _extract_flash_sub_items(self, html_source: str, parent_url: str, parent_title: str) -> List[dict]:
        """
        [修改] 提取快讯子项，并增加缩进处理
        """
        soup = BeautifulSoup(html_source, 'lxml')
        content_div = soup.find(id="content_area")
        if not content_div:
            return []

        items = []
        current_title = ""
        current_content = []
        sub_index = 1

        IGNORE_PATTERNS = [
            "央视网消息（新闻联播）：",
            "央视网消息："
        ]

        for p in content_div.find_all('p', recursive=False):
            text = p.get_text(strip=True)
            if not text:
                continue

            if text in IGNORE_PATTERNS or (len(text) < 15 and "央视网消息" in text):
                continue

            is_header = p.find('strong') or p.find('b')
            
            if is_header:
                if current_title:
                    full_content = "\n".join(current_content).strip()
                    if full_content: 
                        items.append({
                            "title": current_title,
                            "content": full_content,
                            "original_url": f"{parent_url}#sub{sub_index}",
                            "type": NewsType.FLASH_SUB,
                            "parent_url": parent_url
                        })
                        sub_index += 1
                
                current_title = text
                current_content = []
            else:
                if current_title: 
                    # [修改点] 核心技巧：如果是内容行，手动添加缩进
                    formatted_line = f"\u3000\u3000{text}"
                    current_content.append(formatted_line)

        # 保存最后一条
        if current_title:
            full_content = "\n".join(current_content).strip()
            if full_content:
                items.append({
                    "title": current_title,
                    "content": full_content,
                    "original_url": f"{parent_url}#sub{sub_index}",
                    "type": NewsType.FLASH_SUB,
                    "parent_url": parent_url
                })

        return items