# main.py
import asyncio
from src.date_utils import get_target_date_str
from src.crawler import CrawlerService
from src.manager import SagaManager
from src.reporter import SagaReporter
from src.archiver import DataArchiver

async def main():
    # 1. 确定日期
    date_str = get_target_date_str()
    print(f"=== 启动 News Saga Engine: {date_str} ===")
    
    # 2. 爬取数据 (Eyes)
    crawler = CrawlerService()
    briefing = await crawler.fetch_daily_briefing(date_str)
    
    if not briefing:
        print("❌ 爬取失败或当日无新闻")
        return

    print(f"✅ 爬取完成，共 {len(briefing.news_items)} 条新闻。")

    # 2.5 立即归档 (Memory - Raw)
    archiver = DataArchiver()
    archiver.save_daily_raw(briefing)

    # 3. 认知处理与归档 (Brain + Memory - Sagas)
    print("🧠 进入认知层处理...")
    manager = SagaManager()
    await manager.process_daily_briefing(briefing)

    # 4. 生成展示层报告 (The Face)
    print("\n>>> 阶段 4: 生成可视化报告")
    reporter = SagaReporter()
    
    # [修改] 这里将 briefing 传入，以便渲染“今日原始档案”区域
    reporter.generate_readme("README.md", briefing=briefing)
    
    print("\n=== 全部任务完成 ===")

if __name__ == "__main__":
    asyncio.run(main())