Dev Context Snapshot 2026/01/30 00:57
1. 核心任务与状态

    当前目标: 构建 CCTV 新闻联播每日简报爬虫 (Python/Crawl4AI 复刻 N8N 逻辑)。

    当前状态: 编码修复完成 / 待集成测试

    关键文件:

        crawler_service.py: [重构核心] 混合模式实现：列表页用 aiohttp + Regex；详情页用 Crawl4AI 并发；已补全 import json。

        config.py: 仅保留详情页/摘要页 CSS Selectors，列表页逻辑已硬编码至 Service。

        main.py: 主流程控制（日期 -> 列表 -> 并发详情 -> 报告）。

2. 本次会话变动 (Changelog)

    [重构] fetch_daily_list: 弃用 Crawl4AI 浏览器渲染，改用 aiohttp 获取原始字节流并强制 utf-8 解码。

        原因: 浏览器将 CCTV 列表页 HTML 片段误判为 GBK，导致标题出现不可逆乱码（[瑙嗛]）及数据丢失。

    [修改] BrowserConfig: 设置 text_mode=False，确保详情页正文编码由浏览器正确自动识别。

    [修复] crawler_service.py: 修复 NameError: name 'json' is not defined，补充 import json。

3. 挂起的任务与已知问题 (CRITICAL)

    TODO: 运行 main.py 进行端到端测试，确认生成的 .md 文件标题与正文均无乱码。

    RISK: aiohttp 直连无 User-Agent 伪装，若遇 403 需在 ClientSession 添加 Headers。

    VERIFY: 确认 fetch_daily_list 返回的 news_items 结构与 main.py 及 report_builder.py 的预期接口一致。

4. 环境与依赖上下文

    Tech Stack: Python 3.x, Crawl4AI, aiohttp (新增), asyncio, re.

    Config:

        列表解析: Regex 匹配 <a ... href="..." title="...">。

        详情解析: CSS Selector (.tit, #content_area)。


Dev Context Snapshot 2026/01/30 01:20
1. 核心任务与状态

    当前目标: 构建 CCTV 新闻联播每日简报爬虫 (Python/Crawl4AI 复刻 N8N 逻辑)。

    当前状态: 核心修复完成 / 待最终验证。

    关键文件:

        crawler_service.py: [关键重构] 实现了“混合抓取模式” (aiohttp 列表 + Crawl4AI 详情) 及“URL 锚定映射”。

        main.py: 业务流程入口。

2. 本次会话变动 (Changelog)

    [修复] 解决了 NameError: name 'json' is not defined 报错，补全了 import json。

    [修复] 解决了新闻标题与内容不匹配 (模式 B 乱序) 问题。

        原因: arun_many 并发返回顺序不固定，依赖索引 i 导致数据错位。

        对策: 在 fetch_full_content 中引入 url_map (Hash Map)，通过 res.url 反向查找标题，不再依赖列表顺序。

    [优化] 增加了结果重排序逻辑，确保最终 Markdown 按照新闻联播播出顺序生成。

3. 挂起的任务与已知问题 (CRITICAL)

    TODO: 运行 main.py 进行最终测试，验证标题与内容是否一一对应，且无乱码。

    RISK: aiohttp 直连目前未配置复杂 Headers，若触发反爬 (403/429) 需补充 User-Agent。

4. 环境与依赖上下文

    Tech Stack: Python 3.x, Crawl4AI, aiohttp, asyncio, re, json。

    Config:

        BrowserConfig: text_mode=False (确保正文编码正确)。

        列表解析: 正则表达式直接提取 HTML 片段。

Dev Context Snapshot 2026/01/31 12:51
1. 核心任务与状态

    当前目标: 构建 "News Saga Engine" —— 基于 LLM 的全自动新闻叙事追踪系统。

    当前状态: 核心功能闭环 (Core Complete) / 生产环境就绪。

    关键文件:

        src/intelligence.py: [关键] 集成 DeepSeek API，实现新闻路由、新事件元数据生成、摘要生成。包含超时重试 (_safe_api_call) 和强类型 Prompt。

        src/manager.py: [关键] 状态机核心。负责加载/保存 Saga JSON，增加 _safe_parse_importance 修复 LLM 输出类型错误。

        src/crawler.py: 重构为模块化服务，返回 Pydantic DailyBriefing 对象。

        src/reporter.py: [新增] 将 JSON 状态库渲染为 README.md 可视化看板。

        main.py: 串联 Crawler -> Brain -> Memory -> Reporter 的完整流水线。

2. 本次会话变动 (Changelog)

    [重构] 将单脚本爬虫重构为 src/ 包结构，引入 Pydantic Schema (src/schema.py)。

    [新增] src/intelligence.py 接入 DeepSeek-V3，实现语义路由 (Append/Create/Ignore)。

    [修复] 解决了 openai.BadRequestError (Model does not exist)，统一了 config.py 中的 LLM_MODEL 变量。

    [修复] 解决了 API 请求无限 hang 住的问题，在 AsyncOpenAI 客户端中强制设置 timeout=30.0 并增加重试机制。

    [修复] 解决了 pydantic.ValidationError (Input should be a valid integer)，在 src/manager.py 增加 _safe_parse_importance 容错层，强制清洗 LLM 返回的非数字重要性字段（如"高" -> 5）。

    [优化] 移除 Mock 模式，生产环境直接调用真实 API。

3. 挂起的任务与已知问题 (CRITICAL)

    TODO: 配置 GitHub Actions (.github/workflows/daily_run.yml) 以实现每日定时自动化运行 (Step 4 of Upgrade Plan)。

    RISK: src/intelligence.py 中的 System Prompt 依赖 LLM 遵循 JSON 格式，虽已优化，极低概率下仍可能输出非标准 JSON 导致解析失败 (当前已做 Try-Catch 兜底)。

    VERIFY: 确认 data/sagas 目录下的 JSON 文件在多次运行后的数据一致性与追加逻辑是否准确。

4. 环境与依赖上下文

    Tech Stack: Python 3.12, Crawl4AI, Aiohttp, OpenAI SDK (DeepSeek Compatible), Pydantic.

    Config:

        src/config.py: 包含 LLM_API_KEY, LLM_BASE_URL, LLM_MODEL ("deepseek-chat" or "deepseek-ai/DeepSeek-V3")。

        USE_MOCK_AI: 已移除/设为 False。

Dev Context Snapshot 2026/01/31 14:42
1. 核心任务与状态

    当前目标: 完成 News Saga Engine v2.0 架构升级 (全量归档 + 快讯拆解 + 透明展示)。

    当前状态: 功能闭环 (Core Complete) / 已通过本地测试。

    关键文件:

        src/crawler.py: 集成 BeautifulSoup，新增 _extract_flash_sub_items (HTML 结构化拆分) 及噪音过滤。

        src/archiver.py: [新增] 实现 DataArchiver，负责 ETL 流程中的 Load (原始数据 JSON 落盘)。

        src/reporter.py: 新增 _render_daily_archive，在 README 中生成 <details> 折叠表格。

        src/schema.py: RawNewsItem 新增 type (Enum) 和 parent_url 字段。

        main.py: 管道流更新 -> Crawler -> Archiver (新增) -> SagaManager -> Reporter (传入 briefing)。

2. 本次会话变动 (Changelog)

    [重构] 爬虫层: 引入 lxml 解析器，针对 "联播快讯" 实施 Zero-Token 拆分，将单条长新闻拆解为多条 type=flash_sub 的子新闻。

    [修复] 爬虫逻辑: 修复 _extract_flash_sub_items 将 "央视网消息..." 误判为标题的 Bug，增加 IGNORE_PATTERNS 过滤。

    [新增] 档案系统: 确保无论 AI 分析成败，原始抓取数据均保存至 data/archive/{YYYY}/{date}_raw.json。

    [新增] 可视化: README.md 底部增加 "今日原始档案" 审计区，清晰展示快讯拆解结果。

3. 挂起的任务与已知问题 (CRITICAL)

    TODO: 观察线上环境 (GitHub Actions) 运行情况，确认 data/archive 目录持久化逻辑。

    RISK: 爬虫拆解高度依赖 CCTV 网页 DOM 结构 (#content_area 下的 <p><strong>)，若官网改版需重写 _extract_flash_sub_items。

    VERIFY: 需确认拆分后的子新闻数量激增是否导致 src/intelligence.py 中的 LLM Token 消耗超出预期。

4. 环境与依赖上下文

    Tech Stack: Python 3.12, Crawl4AI, Aiohttp, BeautifulSoup4, lxml, Pydantic V2.

    Config:

        main.py 入口函数签名未变，但流程已更新。

        新增依赖: pip install beautifulsoup4 lxml。