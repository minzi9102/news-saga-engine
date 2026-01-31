# src/manager.py
import json
import uuid
from typing import List
from pathlib import Path
from .schema import Saga, SagaStatus, EventNode, DailyBriefing
from .intelligence import IntelligenceEngine

SAGA_DIR = Path("data/sagas")
SAGA_DIR.mkdir(parents=True, exist_ok=True)

class SagaManager:
    def __init__(self):
        self.brain = IntelligenceEngine()
        
    # [新增] 容错处理函数
    def _safe_parse_importance(self, value) -> int:
        """
        无论 LLM 返回什么（字符串'高'、字符串'5'、数字5），都强制转为 int。
        解析失败则默认为 3。
        """
        try:
            # 如果是整数，直接返回
            if isinstance(value, int):
                return value
            
            # 如果是字符串，尝试转 int
            if isinstance(value, str):
                # 处理 '5' 这种情况
                if value.isdigit():
                    return int(value)
                # 处理 '高/中/低' 这种情况 (简单的中文映射兜底)
                if "高" in value or "重" in value: return 5
                if "中" in value: return 3
                if "低" in value: return 1
                
            # 最后的尝试：强制转换
            return int(value)
        except:
            print(f"   [Warn] Importance 解析失败: '{value}'，已重置为 3")
            return 3

    def load_active_sagas(self) -> List[Saga]:
        # ... (保持不变) ...
        sagas = []
        for file_path in SAGA_DIR.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    saga = Saga(**data)
                    if saga.status == SagaStatus.ACTIVE:
                        sagas.append(saga)
            except Exception as e:
                print(f"[Warn] Failed to load {file_path}: {e}")
        return sagas

    def save_saga(self, saga: Saga):
        # ... (保持不变) ...
        file_path = SAGA_DIR / f"{saga.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(saga.model_dump_json(indent=2))

    async def process_daily_briefing(self, briefing: DailyBriefing):
        print(f"🔄 开始处理 {briefing.date} 的 {len(briefing.news_items)} 条新闻...")
        active_sagas = self.load_active_sagas()
        print(f"📚 当前活跃故事线: {len(active_sagas)} 个")

        for news in briefing.news_items:
            print(f"\n📰 分析: {news.title}...")
            
            # 1. 路由
            decision = await self.brain.route_news(news, active_sagas)
            action = decision.get("action")
            
            if action == "ignore":
                print("   -> 🗑️ 判定为噪音/无关，跳过")
                continue
                
            elif action == "append":
                saga_id = decision.get("saga_id")
                target_saga = next((s for s in active_sagas if s.id == saga_id), None)
                
                if target_saga:
                    print(f"   -> 🔗 链接到现有故事: {target_saga.title}")
                    event_data = await self.brain.summarize_event(news)
                    
                    # [修改] 使用安全解析函数
                    safe_importance = self._safe_parse_importance(event_data.get("importance"))
                    
                    new_event = EventNode(
                        date=news.date,
                        title=news.title,
                        summary=event_data.get("summary", news.content[:100]),
                        source_url=news.url,
                        causal_tag=event_data.get("causal_tag", "Update"),
                        importance=safe_importance # <--- 这里用了清洗后的值
                    )
                    
                    target_saga.events.append(new_event)
                    target_saga.last_updated = news.date
                    self.save_saga(target_saga)
                    print("   -> ✅ 已保存更新")
                else:
                    print(f"   -> ⚠️ 错误: 找不到 ID 为 {saga_id} 的 Saga")

            elif action == "create":
                print("   -> ✨ 发现新故事线！准备生成元数据...")
                saga_meta = await self.brain.analyze_new_saga(news)
                
                if not saga_meta.get("title"):
                    print("   -> ❌ 元数据生成失败，跳过")
                    continue
                
                print(f"   -> 元数据获取成功: {saga_meta.get('title')}")
                print("   -> 正在生成首个事件摘要...")

                event_data = await self.brain.summarize_event(news)
                
                # [修改] 使用安全解析函数
                safe_importance = self._safe_parse_importance(event_data.get("importance"))

                first_event = EventNode(
                    date=news.date,
                    title=news.title,
                    summary=event_data.get("summary", news.content[:100]),
                    source_url=news.url,
                    causal_tag=event_data.get("causal_tag", "Inception"),
                    importance=safe_importance # <--- 这里用了清洗后的值
                )

                new_saga = Saga(
                    id=f"saga_{uuid.uuid4().hex[:8]}", 
                    title=saga_meta.get("title"),
                    category=saga_meta.get("category", "General"),
                    status=SagaStatus.ACTIVE,
                    context_summary=saga_meta.get("context_summary", ""),
                    events=[first_event],
                    last_updated=news.date
                )
                
                self.save_saga(new_saga)
                active_sagas.append(new_saga)
                print(f"   -> ✅ 新故事 '{new_saga.title}' 已创建并保存")