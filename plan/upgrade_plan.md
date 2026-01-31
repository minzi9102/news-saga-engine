这是一个为 **AI 辅助编程** 量身定制的完整技术设计文档。你可以直接将这份文档发给 AI（如 Cursor, Windsurf, 或者继续在这个对话中），让它按部就班地生成代码。

项目名称定为：**News Saga Engine (新闻史诗引擎)**。

---

# 📅 News Saga Engine - 项目设计白皮书

## 1. 项目愿景与核心理念

本项目旨在构建一个**“自动化新闻叙事追踪系统”**。不同于传统的“每日新闻堆叠”，本系统将新闻视为连续剧（Saga）的更新。系统利用 LLM（大语言模型）理解新闻的因果关系，自动维护数百个平行的新闻故事线（Timeline），并托管在 GitHub 上利用 Git 版本控制实现“历史存档”。

**核心差异点**：

* **传统爬虫**：Snapshot（快照式）。今天不知道昨天发生了什么。
* **Saga Engine**：Stateful（状态机）。今天的新闻是对昨天剧情的延续。

---

## 2. 系统架构设计 (Architecture)

系统采用 **“管道-过滤器 (Pipe-Filter)”** 架构，配合 **“文件即数据库 (File-as-Database)”** 模式。

### 四层架构模型：

1. **采集层 (Ingestion Layer)**
* **工具**：`Crawl4AI`, `aiohttp`。
* **职责**：从 CCTV 官网获取原始 HTML，清洗为纯文本。
* **现有资源**：复用你现有的 `crawler_service.py`。


2. **认知层 (Cognitive Layer) —— *核心升级***
* **工具**：`LLM API` (DeepSeek V3 / OpenAI), `Pydantic`。
* **职责**：
* **Router (路由)**：判断新闻属于“旧故事后续”还是“新故事开端”。
* **Analyst (分析)**：分析事件因果，生成摘要。




3. **记忆层 (Memory Layer)**
* **介质**：本地 JSON 文件系统 (`data/sagas/*.json`)。
* **版本控制**：Git。每一次 `git commit` 都是一次历史切片。
* **优势**：零数据库成本，人类可读，Github 原生可视化。


4. **展示层 (Presentation Layer)**
* **产物**：
* `README.md` / `Daily_Report.md`: 每日动态简报。
* `timeline/saga_{id}.md`: 单个议题的完整时间线页面。





---

## 3. 数据结构设计 (Schema)

这是指导 AI 写代码的基石。必须使用 Pydantic 强类型定义。

```python
# src/schema.py
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class SagaStatus(str, Enum):
    ACTIVE = "active"   # 正在发生的（如：巴以冲突）
    DORMANT = "dormant" # 长期未更新（如：某次已结束的访问）
    ARCHIVED = "archived" # 归档

class EventNode(BaseModel):
    """时间线上的单个节点"""
    date: str          # YYYY-MM-DD
    title: str         # 事件简短标题
    summary: str       # 事件详情摘要
    source_url: str    # 原文链接
    causal_tag: str    # 因果标签 (e.g., "Retaliation", "Policy Release")
    importance: int    # 1-5 星级

class Saga(BaseModel):
    """一个完整的故事线"""
    id: str            # UUID (e.g., "saga_001_low_altitude_econ")
    title: str         # 故事标题 (e.g., "低空经济产业发展")
    category: str      # 宏观分类 (e.g., "国内经济")
    status: SagaStatus
    context_summary: str # 当前剧情梗概（用于给LLM做上下文）
    events: List[EventNode]
    last_updated: str  # YYYY-MM-DD

```

---

## 4. 整体工作流程 (Workflow)

**每日运行逻辑 (Daily Loop):**

1. **Git Pull**: 确保本地是最新状态。
2. **Load Context**: 读取 `data/sagas/` 下所有 `status=active` 的 JSON，提取 `title` 和 `context_summary` 放入内存。
3. **Crawl**: 抓取今日新闻列表 `[News_1, News_2, ..., News_12]`。
4. **Reasoning Loop (并发处理)**:
* 将 `News_i` + `Active_Sagas_Context` 发送给 LLM。
* **Prompt 询问**: "这条新闻属于现有故事吗？"
* **分支 A (Match)**: 找到对应 Saga -> 追加 Event -> 更新 Summary -> 保存 JSON。
* **分支 B (New)**: 判定为重大新事件 -> 创建新 JSON -> 初始化 Title/Summary -> 保存。
* **分支 C (Noise)**: 判定为日常琐事 -> 忽略或写入 `daily_misc.md`。


5. **Render**: 重新生成 Markdown 报告。
6. **Git Push**: 提交变更到 GitHub。

---

## 5. 细分模块与现有资源改进计划

请按照以下顺序指导 AI 进行开发：

### 第一步：基础设施重构 (Refactor)

* **目标**：将现有爬虫代码模块化，引入 Pydantic。
* **指令**：
1. 保留 `crawler_service.py` 中的 `AsyncWebCrawler` 和 `aiohttp` 逻辑。
2. 新建 `src/schema.py`，写入上述数据结构。
3. 新建 `src/config.py`，将 CSS 选择器和 LLM API Key 配置分离。



### 第二步：智力核心开发 (The Brain)

* **新建模块**: `src/intelligence.py`
* **核心功能**:
* `SagaMatcher`: 编写 Prompt，输入“今日新闻”和“现有Saga列表”，输出 JSON `{ "action": "append", "saga_id": "xxx" }` 或 `{ "action": "create" }`。
* `SagaWriter`: 编写 Prompt，用于根据新事件重写 `context_summary`。


* **关键改进**: 必须使用 LLM 的 **JSON Output Mode** 确保程序不崩。

### 第三步：状态管理 (The Memory)

* **新建模块**: `src/manager.py`
* **核心功能**:
* `load_active_sagas()`: 遍历文件夹读取 JSON。
* `save_saga(saga_obj)`: 将对象回写为 JSON。
* `get_daily_report_content()`: 聚合今日更新的所有 Saga，为生成报告做准备。



### 第四步：自动化部署 (The Robot)

* **配置**: `.github/workflows/daily_run.yml`
* **核心功能**: 每天定时运行，配置 `DEEPSEEK_API_KEY` Secret，自动 Commit 结果。

---

## 6. 改进方案总结 (基于现有资源)

| 模块 | 现状 | 改进方案 | 难点/注意 |
| --- | --- | --- | --- |
| **爬虫** | 已有 `Crawl4AI` + `aiohttp` | 保持不变，只需调整返回数据结构以匹配 Schema | 确保编码问题（乱码）彻底解决 |
| **存储** | 无 (纯文本生成) | **新增** JSON 文件存储系统 | 初始运行时需要手动建立 1-2 个 JSON 避免空指针 |
| **逻辑** | 简单的线性拼接 | **新增** LLM 语义路由 | LLM 可能会产生幻觉，Prompt 需反复调试 |
| **运行** | 本地手动运行 | **迁移** 至 GitHub Actions | 需配置 API Key Secrets，注意 API 调用成本 |

这个计划将你的项目从一个脚本升级为一个系统，且完全不需要维护服务器。现在，你可以开始构建了。