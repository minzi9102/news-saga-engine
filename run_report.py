'''
FilePath: \news_crawl\run_report.py
'''
# run_report.py
import asyncio
import os
import sys
from dotenv import load_dotenv
from src.date_utils import get_target_date_str
from src.archiver import DataArchiver
from src.manager import SagaManager
from src.reporter import SagaReporter
from src.notifier import EmailNotifier

# 加载环境变量 (API Key, SMTP Config)
load_dotenv()

async def main():
    # 1. 确定目标日期
    date_str = get_target_date_str()
    print(f"=== 📊 启动报告生成 (Report): {date_str} ===")

    # 2. 读取原始数据 (Load)
    archiver = DataArchiver()
    try:
        briefing = archiver.load_daily_raw(date_str)
        print(f"✅ 成功加载原始档案，包含 {len(briefing.news_items)} 条新闻")
    except FileNotFoundError:
        print(f"❌ 未找到日期 {date_str} 的原始档案！")
        print("💡 请先运行 'python run_fetch.py' 获取数据。")
        sys.exit(1)

    # 3. 认知层处理 (AI Analysis & Saga Update)
    # 注意：这一步会调用 LLM 并更新 data/sagas 下的 JSON 文件
    print("\n🧠 进入认知层处理 (Saga Analysis)...")
    manager = SagaManager()
    await manager.process_daily_briefing(briefing)

    # 4. 生成可视化报告 (Render)
    print("\n🎨 生成可视化报告...")
    reporter = SagaReporter()
    
    # A. 生成 Markdown (用于 GitHub 仓库展示)
    reporter.generate_readme("README.md", briefing=briefing)

    # B. 生成 HTML (用于邮件和附件)
    html_content = reporter.generate_html_report("report.html", briefing=briefing)

    # 5. 发送通知 (Notify)
    if os.getenv("ENABLE_EMAIL", "false").lower() == "true":
        print("\n📧 正在发送邮件通知...")
        notifier = EmailNotifier()
        notifier.send_daily_report(date_str, html_content)
    else:
        print("\n🚫 邮件发送已禁用 (ENABLE_EMAIL != true)")

    print(f"=== 📊 报告任务完成 ===")

if __name__ == "__main__":
    asyncio.run(main())