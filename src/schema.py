# src/schema.py
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# --- 新增: 新闻类型枚举 ---
class NewsType(str, Enum):
    NORMAL = "normal"
    FLASH_SUB = "flash_sub"  # 标识这是从快讯里拆出来的

# --- 阶段 1: 爬虫原始数据结构 ---
class RawNewsItem(BaseModel):
    """爬虫抓取到的单条新闻原始数据"""
    title: str
    url: str
    content: str
    date: str  # YYYYMMDD格式
    # [新增字段]
    type: NewsType = NewsType.NORMAL 
    parent_url: Optional[str] = None  # 如果是子新闻，记录父链接

class DailyBriefing(BaseModel):
    """每日抓取的汇总对象"""
    date: str
    abstract_text: str = ""
    news_items: List[RawNewsItem] = []

# --- 阶段 2: 业务逻辑数据结构 (Saga) ---
# (SagaStatus, EventNode, Saga 类保持不变，此处省略...)
class SagaStatus(str, Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    ARCHIVED = "archived"

class EventNode(BaseModel):
    date: str
    title: str
    summary: str
    source_url: str
    causal_tag: str
    importance: int

class Saga(BaseModel):
    id: str
    title: str
    category: str
    status: SagaStatus
    context_summary: str
    events: List[EventNode]
    last_updated: str