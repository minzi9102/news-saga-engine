# src/config.py
import os
from dotenv import load_dotenv # [新增] 用于本地加载 .env 文件

load_dotenv()  # [新增] 加载 .env 文件中的环境变量

# --- 基础配置 ---
BASE_URL_TEMPLATE = "https://tv.cctv.com/lm/xwlb/day/{date_str}.shtml"
DATA_DIR = "data"

# --- 爬虫选择器配置 ---
# 请确保这里填入你实际测试通过的 CSS Selectors
SELECTORS = {
    # [修正] 列表页: 改为提取 title 属性
    "daily_list_schema": {
        "name": "CCTV News List",
        "baseSelector": "li",
        "fields": [
            {
                "name": "title", 
                "selector": "a:first-child", 
                "type": "attribute",  # 修正：提取属性
                "attribute": "title"  # 修正：属性名为 title
            },
            {
                "name": "url", 
                "selector": "a:first-child", 
                "type": "attribute", 
                "attribute": "href"
            }
        ]
    },
    # [新增] 摘要页: 对应 N8N 节点 149c26a6
    # 这里的 selector 非常长，为了稳健性，我保留了 N8N 的逻辑但稍微简化
    "abstract_schema": {
        "name": "News Abstract",
        "baseSelector": "body",
        "fields": [
            {
                "name": "raw_content",
                "selector": "#page_body .video18847 .playingCon .nrjianjie_shadow ul li:first-child p",
                "type": "text"
            }
        ]
    },
    # [新增] 详情页: 对应 N8N 节点 43dd14e5
    "news_detail_schema": {
        "name": "News Detail",
        "baseSelector": "body",
        "fields": [
            {
                "name": "title",
                "selector": ".tit", # 简化选择器
                "type": "text"
            },
            {
                "name": "content",
                "selector": "#content_area",
                "type": "text"
            }
        ]
    }
}

# --- LLM 配置 (为后续做准备) ---
LLM_API_KEY = os.getenv("LLM_API_KEY")

if not LLM_API_KEY:
    # 简单的检查，防止没有配置 Key 导致程序空跑
    print("⚠️ 警告: 未检测到 LLM_API_KEY 环境变量，AI 分析功能将不可用。")

# 可选修改：给 Base URL 和 Model 设置默认值，但允许环境变量覆盖
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3") # 注意模型名是否正确