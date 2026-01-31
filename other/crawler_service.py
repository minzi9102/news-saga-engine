# crawler_service.py
import asyncio
import re
import json  # <--- [关键修正] 之前漏掉了这个
import aiohttp
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from config import BASE_URL_TEMPLATE, SELECTORS

class CrawlerService:
    def __init__(self):
        # 浏览器配置保持不变，用于抓取详情页
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            text_mode=False 
        )

    async def fetch_daily_list(self, date_str):
        """
        [重构版] 步骤1: 获取列表
        不再使用浏览器，而是直接下载原始字节流并强制 UTF-8 解码。
        解决浏览器对 HTML 片段编码识别错误导致的乱码问题。
        """
        url = BASE_URL_TEMPLATE.format(date_str=date_str)
        print(f"[*] [Direct] 正在下载列表: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        print(f"[Error] 下载失败，状态码: {response.status}")
                        return None, []
                    
                    # 关键点：获取原始二进制数据
                    content_bytes = await response.read()
                    
            # 关键点：强制使用 utf-8 解码，忽略微小的错误
            html_content = content_bytes.decode('utf-8', errors='ignore')
            
            # 使用正则提取链接和标题
            items = []
            # 正则匹配 href 和 title
            pattern = re.compile(r'<a\s+[^>]*?href=[\'"](.*?)[\'"][^>]*?title=[\'"](.*?)[\'"]', re.IGNORECASE)
            
            matches = pattern.findall(html_content)
            
            # 如果没找到带 title 的，尝试只匹配 href 和 标签内的文本
            if not matches:
                print("[Warning] 未找到 title 属性，尝试提取标签文本...")
                pattern_text = re.compile(r'<a\s+[^>]*?href=[\'"](.*?)[\'"][^>]*?>(.*?)</a>', re.IGNORECASE)
                matches = pattern_text.findall(html_content)

            print(f"[*] 原始提取到 {len(matches)} 条链接")

            unique_items = {}
            for url, title in matches:
                if not url or not title: continue
                if url in unique_items: continue
                
                # 数据清洗
                clean_title = title.replace('[视频]', '').strip()
                
                unique_items[url] = {
                    'url': url,
                    'title': clean_title
                }

            final_list = list(unique_items.values())

            if not final_list:
                return None, []

            # 第一条通常是摘要
            abstract_item = final_list[0]
            news_items = final_list[1:]

            print(f"[*] 成功解析。摘要标题: {abstract_item['title']}")
            return abstract_item, news_items

        except Exception as e:
            print(f"[Error] 列表获取异常: {e}")
            return None, []

    async def fetch_full_content(self, abstract_item, news_items):
        """步骤2 & 3: 并发抓取"""
        
        print(f"[*] 启动并发抓取: 1 个摘要 + {len(news_items)} 条新闻详情...")
        
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
            
            # [关键修复 1] 建立 URL -> Title 的查找字典
            # 这样无论结果顺序怎么乱，我们都能通过 URL 找回正确的标题
            url_map = {item['url']: item['title'] for item in news_items}

            schema = SELECTORS["news_detail_schema"]
            config = CrawlerRunConfig(
                extraction_strategy=JsonCssExtractionStrategy(schema),
                cache_mode=CacheMode.BYPASS
            )
            
            results_list = []
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                crawl_results = await crawler.arun_many(urls=urls, config=config)
                
                # [关键修复 2] 不再依赖索引 i，而是遍历结果本身
                for res in crawl_results:
                    if res.success:
                        data = json.loads(res.extracted_content)
                        if data:
                            detail = data[0]
                            
                            # 通过结果中的 URL 反查原始标题
                            # 注意：res.url 可能是经过重定向的，但在 CCTV 这个场景下通常是一致的
                            # 如果不一致，我们做一个简单的容错处理
                            original_title = url_map.get(res.url)
                            
                            if original_title:
                                detail['title'] = original_title
                            else:
                                print(f"[Warning] URL不匹配，无法映射标题: {res.url}")
                                # 兜底：尝试从 url_map 中找一个最相似的 key (可选，暂不复杂化)
                                # 此时只能用页面自己抓到的标题（可能包含[视频]）
                                pass 

                            detail['original_url'] = res.url
                            
                            if 'content' not in detail:
                                detail['content'] = ""
                                
                            results_list.append(detail)
            
            # [可选优化] 既然顺序乱了，我们在返回前按照原始 news_items 的顺序排个序
            # 这样生成的 Markdown 就会按照新闻联播的播出顺序排列
            ordered_results = []
            for item in news_items:
                # 在结果列表中找到对应的那个（效率较低但列表很短，没关系）
                found = next((r for r in results_list if r['original_url'] == item['url']), None)
                if found:
                    ordered_results.append(found)
            
            return ordered_results

        abstract_text, details_list = await asyncio.gather(get_abstract(), get_details())
        return abstract_text, details_list