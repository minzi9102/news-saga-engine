### 项目名称：Crawl4AI 新闻联播每日简报生成器

### 1. 项目目标

利用 Python 和 Crawl4AI 框架，复刻并优化 N8N 的抓取逻辑，实现：

1. 自动计算目标日期（处理 CCTV 晚8点前更新逻辑）。
2. 抓取当日新闻联播列表页。
3. 分离“摘要链接”与“详细新闻链接”。
4. **并发抓取**所有详情页（比 N8N 的 Loop 效率更高）。
5. 生成包含“内容提要”和“详细内容”的 Markdown 日报。
6. 发送邮件或保存本地。

---

### 2. 核心逻辑映射 (N8N vs Crawl4AI)

| 步骤 | N8N 节点逻辑 | Python/Crawl4AI 实现方案 | 优势 |
| --- | --- | --- | --- |
| **日期计算** | Code Node (JS): 获取上海时间，20点前取前一天 | Python `datetime` + `pytz` 库实现同等逻辑 | 逻辑更直观 |
| **列表抓取** | HTTP Request: 获取列表 HTML | `crawler.arun(url)` | 自动处理反爬/渲染 |
| **链接提取** | HTML Extract: 提取 `li a:first-child` | Crawl4AI `JsonCssExtractionStrategy` | 结构化提取 |
| **链接分流** | Code Node: `shift()` 取第一个为摘要，其余为新闻 | Python List 切片 `links[0]` vs `links[1:]` | 内存操作，极快 |
| **摘要抓取** | HTTP Request + HTML Extract | `crawler.arun(abstract_url)` | 独立任务 |
| **详情抓取** | **SplitInBatches (循环)** | **`crawler.arun_many(news_urls)`** | **全异步并发，速度提升10倍+** |
| **数据清洗** | Code Node: 正则替换、去重 | Python 字符串处理函数 | 灵活度高 |
| **组装 MD** | Code Node: 拼接字符串 | Jinja2 模板或 f-string 拼接 | 易于维护格式 |

---

### 3. 详细实施步骤

#### 第一阶段：环境与配置

1. **依赖安装**：
```bash
pip install crawl4ai asyncio aiofiles pytz

```


2. **配置文件 (`config.py`)**：
将 N8N 中的硬编码 CSS 选择器提取为常量，方便维护。
```python
# CSS 选择器映射 (源自 N8N 配置)
SELECTORS = {
    "list_items": "li a:first-child", # 列表页链接
    "abstract_content": "#page_body > div.allcontent ... > p", # 摘要页内容
    "news_title": "#page_body ... div.tit", # 详情页标题
    "news_content": "#content_area", # 详情页正文
}

```



#### 第二阶段：核心模块开发

**模块 A：日期计算器 (`date_utils.py`)**

* **逻辑**：实现 N8N 中 `e0decf06...` 节点的逻辑。
* **功能**：获取当前 UTC 时间 -> 转上海时间 -> 判断 `hour < 20` -> 返回 `YYYYMMDD` 格式字符串。

**模块 B：爬虫主逻辑 (`crawler_service.py`)**
这是一个基于 `AsyncWebCrawler` 的类，包含三个主要方法：

1. **`fetch_daily_list(date_str)`**:
* 构造 URL: `http://tv.cctv.com/lm/xwlb/day/{date_str}.shtml`
* 使用 CSS 选择器提取所有链接 (`href`) 和标题。
* **逻辑分离**：将第一个链接标记为 `Abstract`，剩余链接标记为 `News`。


2. **`fetch_abstract(url)`**:
* 抓取摘要页。
* 提取文本，并执行清洗（将中文分号/冒号替换为换行符，对应 N8N 节点 `b8073e67...`）。
* 解析“本期内容提要”生成无序列表。


3. **`fetch_news_details(urls)`**:
* **核心优化点**：使用 `crawler.arun_many(urls)` 并发抓取所有新闻页。
* 为每个页面应用提取策略（提取标题、正文）。
* 清洗标题（移除 `[视频]` 字样）。



#### 第三阶段：数据组装与输出 (`report_builder.py`)

* **Markdown 生成器**：
* 接收摘要数据和新闻详情列表。
* 按照 N8N 节点 `e4759eba...` 的逻辑拼接字符串。
* **头部**：`# 新闻联播 YYYYMMDD`
* **提要**：将摘要文本转换为 Markdown List (`- 列表项`)。
* **详情**：循环插入 `## 标题`、`正文` 和 `[原文链接]`。



#### 第四阶段：通知与自动化 (`main.py`)

* **主流程控制**：
1. 调用日期模块获取 `date`。
2. 初始化 `AsyncWebCrawler`。
3. `await fetch_daily_list`。
4. `await asyncio.gather(fetch_abstract, fetch_news_details)` (并行执行摘要抓取和详情抓取)。
5. 调用 `report_builder` 生成 Markdown。
6. **保存/发送**：
* 保存为 `news_report_{date}.md`。
* (可选) 集成 SMTP 发送邮件 (参考 N8N `Send email` 节点)。





---

### 4. 代码结构示例 (伪代码)

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from datetime import datetime
import pytz

async def main():
    # 1. 计算日期 (N8N 逻辑复刻)
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    # 如果当前时间小于20点，取昨天的新闻
    if now.hour < 20: 
        target_date = ... # 减去一天
    else:
        target_date = now
    date_str = target_date.strftime("%Y%m%d")
    
    list_url = f"http://tv.cctv.com/lm/xwlb/day/{date_str}.shtml"

    async with AsyncWebCrawler() as crawler:
        # 2. 获取列表
        list_result = await crawler.arun(url=list_url)
        # ... 解析链接逻辑 ...
        # 假设解析出: abstract_url 和 news_urls_list
        
        # 3. 并发抓取 (摘要 + 所有新闻详情)
        # N8N 是串行的，这里我们并行处理所有任务
        task_abstract = crawler.arun(url=abstract_url)
        task_news = crawler.arun_many(urls=news_urls_list)
        
        abstract_result, news_results = await asyncio.gather(task_abstract, task_news)
        
        # 4. 数据清洗与组装 Markdown
        markdown_content = generate_markdown(abstract_result, news_results)
        
        # 5. 保存或发送
        save_to_file(markdown_content)

if __name__ == "__main__":
    asyncio.run(main())

```

### 5. 项目时间表

* **Day 1**: 完成日期计算与列表抓取逻辑，验证 CSS 选择器是否依然有效（CCTV 网站结构可能微调）。
* **Day 2**: 实现 `arun_many` 并发详情抓取，完成 Markdown 组装逻辑。
* **Day 3**: 增加错误处理（如当天新闻未出时的重试机制），配置 GitHub Actions 实现每日自动运行并推送到邮箱。

这个计划能够完全覆盖你提供的 N8N 项目逻辑，并且在执行效率和代码可维护性上更胜一筹。是否需要我先给出**第一阶段（日期计算与列表抓取）**的具体代码？