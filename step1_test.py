# step1_test.py
import asyncio
from src.date_utils import get_target_date_str
from crawler_service import CrawlerService

async def main():
    # 1. 获取日期
    date_str = get_target_date_str()
    
    # 2. 初始化爬虫服务
    service = CrawlerService()
    
    # 3. 获取列表
    abstract, news_list = await service.fetch_daily_list(date_str)
    
    # 4. 验证结果
    if abstract:
        print("\n--- 验证数据结构 ---")
        print(f"摘要 URL: {abstract['url']}")
        print(f"新闻列表样例 (前3条):")
        for idx, news in enumerate(news_list[:3]):
            print(f"  {idx+1}. {news['title']} \n     Link: {news['url']}")
    else:
        print("\n[!] 流程中断: 未获取到数据")

if __name__ == "__main__":
    asyncio.run(main())