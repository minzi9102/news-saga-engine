import asyncio
import sys
from datetime import datetime, timedelta

# 导入你的模块
from src.crawler import CrawlerService
from src.schema import NewsType

async def test_crawler(date_str):
    print(f"\n🚀 开始测试爬虫，目标日期: {date_str}")
    print("=" * 50)
    
    crawler = CrawlerService()
    
    # 调用核心方法
    briefing = await crawler.fetch_daily_briefing(date_str)
    
    if not briefing:
        print(f"❌ 获取失败：{date_str} 没有找到简报或下载错误。")
        return

    print(f"✅ 抓取成功！共获取 {len(briefing.news_items)} 条新闻项。\n")
    print(f"📄 摘要预览: {briefing.abstract_text[:50]}...\n")
    
    print("📋 详细列表审计:")
    print("-" * 50)
    
    flash_sub_count = 0
    normal_count = 0
    
    for i, item in enumerate(briefing.news_items, 1):
        # 根据类型打印不同的图标
        if item.type == NewsType.FLASH_SUB:
            icon = "⚡ [快讯拆解]"
            source_info = f"\n      └── 来自父链接: {item.parent_url}"
            flash_sub_count += 1
        else:
            icon = "📺 [普通新闻]"
            source_info = ""
            normal_count += 1
            
        print(f"{i:02d}. {icon} {item.title}")
        print(f"      🔗 {item.url}{source_info}")
        
        # 如果是快讯子项，打印一部分内容验证是否拆对
        if item.type == NewsType.FLASH_SUB:
            snippet = item.content.replace('\n', ' ')[:60]
            print(f"      📝 内容片段: {snippet}...")
        print("")

    print("=" * 50)
    print(f"📊 测试统计:")
    print(f"   - 普通新闻: {normal_count} 条")
    print(f"   - 快讯拆解: {flash_sub_count} 条")
    
    if flash_sub_count > 0:
        print("\n✅ 测试通过：检测到快讯已被成功拆解！")
    else:
        print("\n⚠️ 警告：未检测到快讯拆解。可能是当天没有快讯，或解析规则失效。")

if __name__ == "__main__":
    # 默认测试昨天（通常今天的新闻还没出，或者刚出）
    # 你也可以手动修改这里的日期，例如 "20240129"
    default_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = input(f"请输入测试日期 (YYYYMMDD) [默认 {default_date}]: ").strip() or default_date
        
    asyncio.run(test_crawler(target_date))