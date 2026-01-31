# src/manager.py (修改版)
import json
import os
from pathlib import Path
from typing import List, Dict, Set # 新增 Set
from .schema import Saga, SagaStatus, DailyBriefing, EventNode, RawNewsItem
from .intelligence import IntelligenceEngine

class SagaManager:
    def __init__(self, db_dir: str = "data/sagas"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.sagas: Dict[str, Saga] = {}
        self.intelligence = IntelligenceEngine()
        self._load_sagas()

    def _load_sagas(self):
        """加载所有现存的 Saga"""
        for file_path in self.db_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    saga = Saga(**data)
                    self.sagas[saga.id] = saga
            except Exception as e:
                print(f"⚠️ 加载 Saga 异常 {file_path}: {e}")

    # [新增方法] 获取所有已经存在的新闻链接
    def _get_all_processed_urls(self) -> Set[str]:
        processed_urls = set()
        for saga in self.sagas.values():
            for event in saga.events:
                if event.source_url:
                    processed_urls.add(event.source_url)
        return processed_urls

    async def process_daily_briefing(self, briefing: DailyBriefing):
        """核心业务流：处理每日简报"""
        if not briefing or not briefing.news_items:
            print("📭 今日无新闻，跳过处理。")
            return

        # 1. [关键修复] 构建去重集合
        # 收集所有 Saga 中已经记录过的 URL
        existing_urls = self._get_all_processed_urls()
        print(f"🛡️ 已知历史事件 URL: {len(existing_urls)} 个 (用于去重)")

        active_sagas = [s for s in self.sagas.values() if s.status == SagaStatus.ACTIVE]
        print(f"📚 当前活跃故事线: {len(active_sagas)} 个")

        for news in briefing.news_items:
            print(f"\n📰 分析: {news.title[:30]}...")
            
            # 2. [关键修复] 强力去重逻辑
            # 如果这条新闻的 URL 已经在数据库里了，直接跳过！
            # 注意：快讯拆分后的 URL 带有 #sub1, #sub2，是唯一的，所以也能完美去重
            if news.url in existing_urls:
                print(f"   ↳ 🚫 [Duplicate] 该新闻已存在于故事线中，跳过 (省钱模式)。")
                continue

            # --- 下面是正常的 AI 流程 ---
            
            # A. 路由决策 (Router)
            decision = await self.intelligence.route_news(news, active_sagas)
            action = decision.get("action", "ignore")
            
            if action == "ignore":
                print("   ↳ 🗑️ [Ignore] 琐事/无关")
                continue
                
            elif action == "append":
                saga_id = decision.get("saga_id")
                if saga_id and saga_id in self.sagas:
                    print(f"   ↳ 🔗 [Append] 归入 Saga: {self.sagas[saga_id].title}")
                    await self._handle_append(saga_id, news)
                else:
                    print(f"   ↳ ⚠️ [Error] AI 建议 Append 但 ID 无效，转为 Create")
                    await self._handle_create(news)

            elif action == "create":
                print(f"   ↳ ✨ [Create] 发现新故事线")
                await self._handle_create(news)

            # [小优化] 处理完一条后，立即把它加入去重集合
            # 防止同一天的新闻列表里有重复链接（虽然爬虫层已经去重了，但双重保险更好）
            existing_urls.add(news.url)

    async def _handle_create(self, news: RawNewsItem):
        # 1. 生成元数据
        meta = await self.intelligence.analyze_new_saga(news)
        
        # 2. 生成第一个事件
        event_data = await self.intelligence.summarize_event(news)
        
        # 3. 组装 Saga 对象
        new_saga_id = f"saga_{int(os.times().system)}_{abs(hash(news.title))}"[:20] # 简单 ID 生成
        
        # 确保 importance 是整数
        safe_importance = self._safe_parse_importance(event_data.get("importance", 3))

        first_event = EventNode(
            date=news.date,
            title=meta.get("title", news.title), #以此为题
            summary=event_data.get("summary", news.content[:100]),
            source_url=news.url,
            causal_tag="Inception",
            importance=safe_importance
        )

        new_saga = Saga(
            id=new_saga_id,
            title=meta.get("title", news.title),
            category=meta.get("category", "General"),
            status=SagaStatus.ACTIVE,
            context_summary=meta.get("context_summary", ""),
            events=[first_event],
            last_updated=news.date
        )

        # 4. 保存
        self.sagas[new_saga_id] = new_saga
        self._save_saga(new_saga)
        print(f"   -> ✅ 新故事 '{new_saga.title}' 已创建并保存")

    async def _handle_append(self, saga_id: str, news: RawNewsItem):
        saga = self.sagas[saga_id]
        
        # 1. 生成事件
        event_data = await self.intelligence.summarize_event(news)
        
        safe_importance = self._safe_parse_importance(event_data.get("importance", 1))

        new_event = EventNode(
            date=news.date,
            title=news.title, # 或者让 AI 生成短标题
            summary=event_data.get("summary", ""),
            source_url=news.url,
            causal_tag=event_data.get("causal_tag", "Update"),
            importance=safe_importance
        )
        
        # 2. 更新 Saga 状态
        saga.events.append(new_event)
        saga.last_updated = news.date
        # (可选: 更新 context_summary，这里暂时略过，保留原 summary)
        
        # 3. 保存
        self._save_saga(saga)
        print(f"   -> ✅ 事件已追加到 '{saga.title}'")

    def _save_saga(self, saga: Saga):
        file_path = self.db_dir / f"{saga.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(saga.model_dump_json(indent=2))

    def _safe_parse_importance(self, val) -> int:
        """清洗 importance 字段，确保是 int"""
        try:
            return int(val)
        except:
            return 3