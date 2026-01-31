# main.py
import asyncio
import os
from src.date_utils import get_target_date_str
from crawler_service import CrawlerService
from report_builder import generate_markdown

async def main():
    print("=== CCTV 新闻联播抓取任务启动 ===")
    
    # 1. 获取目标日期
    date_str = get_target_date_str()
    
    # 2. 初始化爬虫
    service = CrawlerService()
    
    # 3. 获取列表 (修复版)
    print(">>> 阶段 1: 获取新闻列表")
    abstract_item, news_items_links = await service.fetch_daily_list(date_str)
    
    if not abstract_item:
        print("[!] 无法获取列表，任务终止。")
        return

    print(f"    - 日期: {date_str}")
    print(f"    - 摘要标题: {abstract_item.get('title')}") # 现在应该能打印出标题了
    print(f"    - 新闻数量: {len(news_items_links)}")

    # 4. 并发抓取内容
    print(">>> 阶段 2: 并发抓取详情 (High Speed)")
    abstract_text, full_news_list = await service.fetch_full_content(abstract_item, news_items_links)
    print(f"    - 摘要长度: {len(abstract_text)} 字符")
    print(f"    - 成功抓取详情: {len(full_news_list)}/{len(news_items_links)}")

    # 5. 生成报告
    print(">>> 阶段 3: 生成 Markdown 简报")
    title, md_content = generate_markdown(date_str, abstract_text, full_news_list)
    
    # 6. 保存文件
    filename = f"{title.replace(' ', '_')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"=== 任务完成: 已保存为 {filename} ===")

if __name__ == "__main__":
    asyncio.run(main())