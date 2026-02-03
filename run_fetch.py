# run_fetch.py
import asyncio
import sys
from src.date_utils import get_target_date_str
from src.crawler import CrawlerService
from src.archiver import DataArchiver

async def main():
    # 1. 确定目标日期
    date_str = get_target_date_str()
    print(f"=== 📥 启动数据采集 (Fetch): {date_str} ===")
    
    # 2. 爬取数据 (Crawl)
    crawler = CrawlerService()
    briefing = await crawler.fetch_daily_briefing(date_str)
    
    if not briefing or not briefing.news_items:
        print(f"❌ 采集失败或当日({date_str})无新闻内容")
        # 返回非零状态码，以便 CI/CD 知道这步失败了，停止后续步骤
        sys.exit(1)

    print(f"✅ 采集完成，共抓取 {len(briefing.news_items)} 条新闻 (含快讯子条目)")

    # 3. 归档原始数据 (Archive)
    archiver = DataArchiver()
    saved_path = archiver.save_daily_raw(briefing)
    
    print(f"=== 📥 采集任务结束，数据已保存至: {saved_path} ===")

if __name__ == "__main__":
    asyncio.run(main())