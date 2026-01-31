# report_builder.py
import re

def generate_markdown(date_str, abstract_raw, news_list):
    """
    组装 Markdown 报告
    逻辑复刻 N8N 节点: e4759eba-f833-45ea-91f7-7d40c0ea9fa3
    """
    
    # 1. 尝试从摘要中提取更准确的标题 (如 "新闻联播 20260129")
    # N8N 正则: /《(.*?)》\s*(\d{8})/
    match = re.search(r"《(.*?)》\s*(\d{8})", abstract_raw)
    if match:
        program_name, date_extracted = match.groups()
        main_title = f"{program_name} {date_extracted}"
    else:
        main_title = f"新闻简报 {date_str}"

    md_content = f"# {main_title}\n\n"

    # 2. 处理“本期内容提要” (N8N 逻辑: 替换标点，转为无序列表)
    # 移除头部和尾部杂质
    clean_abstract = abstract_raw.replace('本期节目主要内容：', '')
    clean_abstract = re.sub(r'\（《.*?》.*?\）', '', clean_abstract).strip()

    # 替换中文标点以优化显示 (N8N 节点 b8073e67)
    clean_abstract = clean_abstract.replace('；', '；\n').replace('：', '：\n')

    # 生成列表
    formatted_lines = []
    for line in clean_abstract.split('\n'):
        line = line.strip()
        if not line: continue
        
        # 将 "1." 或 "10." 替换为 "- "
        line = re.sub(r'^\d+\.\s*', '- ', line)
        # 将 "(1)" 替换为缩进列表 "  - "
        line = re.sub(r'^[（\(]\d+[）\)]\s*', '  - ', line)
        
        if not line.startswith('-') and not line.startswith('  -'):
            line = f"- {line}" # 兜底策略，确保是列表
            
        formatted_lines.append(line)

    md_content += "## 本期内容提要\n\n"
    md_content += "\n".join(formatted_lines)
    md_content += "\n\n---\n\n"

    # 3. 拼接新闻详情
    for news in news_list:
        title = news.get('title', '无标题')
        content = news.get('content', '暂无内容')
        link = news.get('original_url', '')

        md_content += f"## {title}\n\n"
        md_content += f"{content}\n\n"
        if link:
            md_content += f"[原文链接]({link})\n\n"
        md_content += "---\n\n"

    return main_title, md_content