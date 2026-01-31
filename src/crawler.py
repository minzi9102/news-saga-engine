# src/crawler.py
import asyncio
import re
import json
from typing import Optional, List
import aiohttp
from bs4 import BeautifulSoup  # [新增]
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# 相对导入
from .config import BASE_URL_TEMPLATE, SELECTORS
from .schema import RawNewsItem, DailyBriefing, NewsType # [新增导入 NewsType]

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

        # 2. 获取详情 (返回的是包含 type, parent_url 的字典列表)
        abstract_text, details_list = await self._fetch_full_content(abstract_item, news_items_links)

        # 3. 组装 Pydantic 对象
        raw_items = []
        for detail in details_list:
            raw_items.append(RawNewsItem(
                title=detail.get('title', 'No Title'),
                url=detail.get('original_url', ''), # 子新闻的 URL 可能带有锚点 #1, #2
                content=detail.get('content', ''),
                date=date_str,
                type=detail.get('type', NewsType.NORMAL),          # [新增]
                parent_url=detail.get('parent_url', None)          # [新增]
            ))
        
        return DailyBriefing(
            date=date_str,
            abstract_text=abstract_text,
            news_items=raw_items
        )

    # _fetch_daily_list 保持不变，此处省略...
    async def _fetch_daily_list(self, date_str):
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

    # [核心修改区域]
    async def _fetch_full_content(self, abstract_item, news_items):
        # 建立映射
        url_map = {item['url']: item['title'] for item in news_items}
        
        async def get_abstract():
            schema = SELECTORS["abstract_schema"]
            config = CrawlerRunConfig(extraction_strategy=JsonCssExtractionStrategy(schema))
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                res = await crawler.arun(url=abstract_item['url'], config=config)
                if res.success:
                    data = json.loads(res.extracted_content)
                    return data[0]['raw_content'] if data else ""
                return ""

        async def get_details():
            urls = [item['url'] for item in news_items]
            # 注意：对于快讯，我们需要 HTML 结构，Crawl4AI 的 res.html 包含了完整 HTML
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

                    # 1. 基础信息提取
                    original_title = url_map.get(res.url, "Unknown Title")
                    
                    # 2. 判断是否为“快讯”并进行特殊处理
                    # 关键词通常是 "联播快讯" 或 "国内联播快讯" 等
                    if "快讯" in original_title:
                        print(f"⚡ 发现快讯，正在拆解: {original_title}")
                        # 传入 res.html (完整HTML) 进行 BeautifulSoup 解析
                        sub_items = self._extract_flash_sub_items(res.html, res.url, original_title)
                        if sub_items:
                            results_list.extend(sub_items)
                            continue # 如果拆解成功，就不添加原始的大条目了
                        else:
                            print(f"⚠️ 快讯拆解失败，回退到普通模式: {original_title}")

                    # 3. 普通新闻处理 (Fallback)
                    data = json.loads(res.extracted_content)
                    if data:
                        detail = data[0]
                        detail['title'] = original_title
                        detail['original_url'] = res.url
                        detail['type'] = NewsType.NORMAL
                        detail['parent_url'] = None
                        if 'content' not in detail: detail['content'] = ""
                        results_list.append(detail)
            
            # 4. 重新排序 (支持一对多展开)
            ordered_results = []
            for item in news_items: # 遍历原始列表顺序
                target_url = item['url']
                # 查找所有匹配该 URL 的结果 (包括普通新闻和拆解后的子新闻)
                # 子新闻的 parent_url 会等于 target_url
                related = [
                    r for r in results_list 
                    if r.get('original_url') == target_url or r.get('parent_url') == target_url
                ]
                ordered_results.extend(related)
                
            return ordered_results

        abstract_text, details_list = await asyncio.gather(get_abstract(), get_details())
        return abstract_text, details_list

    def _extract_flash_sub_items(self, html_source: str, parent_url: str, parent_title: str) -> List[dict]:
        """
        [修改] 增加过滤逻辑，忽略开头的来源声明
        """
        soup = BeautifulSoup(html_source, 'lxml')
        content_div = soup.find(id="content_area")
        if not content_div:
            return []

        items = []
        current_title = ""
        current_content = []
        sub_index = 1

        # 定义需要忽略的特定文本模式
        # 这些通常是央视网的固定格式，不算新闻内容
        IGNORE_PATTERNS = [
            "央视网消息（新闻联播）：",
            "央视网消息："
        ]

        for p in content_div.find_all('p', recursive=False):
            text = p.get_text(strip=True)
            if not text:
                continue

            # --- [新增] 过滤逻辑 ---
            # 如果文本完全匹配忽略列表，或者包含类似 "央视网消息" 且非常短，直接跳过
            if text in IGNORE_PATTERNS or (len(text) < 15 and "央视网消息" in text):
                continue
            # ---------------------

            # 检查是否为标题行 (包含加粗标签 或 看起来像标题)
            # 有时候标题不一定在 strong 里，可能整段就是加粗，这里保持原有逻辑即可
            is_header = p.find('strong') or p.find('b')
            
            if is_header:
                # 如果之前已经有正在收集的内容，先保存上一条
                if current_title:
                    # [优化] 只有当内容不为空时才保存，防止保存空标题
                    # 或者只有当标题不是被忽略的文本时才保存
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
                # 是内容行
                if current_title: 
                    current_content.append(text)

        # 循环结束后，保存最后一条
        if current_title:
            full_content = "\n".join(current_content).strip()
            if full_content: # [优化] 同样检查内容是否为空
                items.append({
                    "title": current_title,
                    "content": full_content,
                    "original_url": f"{parent_url}#sub{sub_index}",
                    "type": NewsType.FLASH_SUB,
                    "parent_url": parent_url
                })

        return items