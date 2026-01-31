# src/intelligence.py
import json
import time
from typing import List, Dict, Any
from openai import AsyncOpenAI, APITimeoutError
from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .schema import RawNewsItem, Saga

class IntelligenceEngine:
    def __init__(self):
        if not LLM_API_KEY:
            raise ValueError("⚠️ [Critical Error] 未找到 LLM_API_KEY")
            
        print(f"🧠 [Brain] 大脑已连接: {LLM_MODEL} (Timeout=90s)")
        # [关键修改] 设置全局超时时间为 90 秒，防止无限卡死
        self.client = AsyncOpenAI(
            api_key=LLM_API_KEY, 
            base_url=LLM_BASE_URL,
            timeout=90.0
        )

    async def _safe_api_call(self, func_name: str, messages: List[Dict], max_retries=2) -> Dict:
        """内部通用 API 调用包装器，带重试和详细日志"""
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                print(f"   [Debug] {func_name} | 请求发送... (Attempt {attempt+1})")
                
                response = await self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                
                duration = time.time() - start_time
                print(f"   [Debug] {func_name} | ✅ 响应成功 ({duration:.2f}s)")
                return json.loads(response.choices[0].message.content)
            
            except APITimeoutError:
                print(f"   [Debug] {func_name} | ❌ 请求超时 (30s)!")
            except Exception as e:
                print(f"   [Debug] {func_name} | ❌ 发生错误: {e}")
            
            # 如果不是最后一次重试，等待一会
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2)
        
        return {} # 失败返回空字典

    async def route_news(self, news: RawNewsItem, active_sagas: List[Saga]) -> Dict[str, Any]:
        """决策路由"""
        saga_context = [{"id": s.id, "title": s.title, "summary": s.context_summary} for s in active_sagas]
        
        system_prompt = """
        你是资深新闻分析师。将【今日新闻】归类：
        1. 现有 Saga 后续 -> "action": "append", "saga_id": "xxx"
        2. 重大新事件 -> "action": "create"
        3. 琐事 -> "action": "ignore"
        输出纯 JSON。
        """
        user_content = f"【现有 Sagas】: {json.dumps(saga_context, ensure_ascii=False)}\n\n【今日新闻】:\n标题: {news.title}\n内容: {news.content[:500]}..."

        result = await self._safe_api_call("Route", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ])
        
        return result if result else {"action": "ignore"}

    async def analyze_new_saga(self, news: RawNewsItem) -> Dict[str, Any]:
        """生成新 Saga 元数据"""
        system_prompt = """
        提取元数据初始化 Saga：title, category, context_summary, causal_tag, importance。输出纯 JSON。
        """
        return await self._safe_api_call("NewSaga", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"标题: {news.title}\n内容: {news.content[:800]}"}
        ])

    async def summarize_event(self, news: RawNewsItem) -> Dict[str, Any]:
        """生成 EventNode"""
        # [修改点] 极度明确的类型约束
        system_prompt = """
        请将这条新闻浓缩为一个 Event Node。
        输出纯 JSON 格式，包含以下字段:
        - summary: 50字以内的核心事实摘要。
        - causal_tag: 事件性质 (如 "Meeting", "Statement", "Accident")。
        - importance: 必须是 1 到 5 之间的整数 (int)。绝对禁止输出汉字(如"高")或字符串。
          (5=极度重要, 1=日常琐事)
        """
        result = await self._safe_api_call("Summarize", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": news.content[:800]}
        ])
        
        # 兜底数据
        if not result:
            return {"summary": news.content[:100], "causal_tag": "TimeoutFallback", "importance": 1}
        return result