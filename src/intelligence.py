import json
import time
import re
import asyncio
from typing import List, Dict, Any
from openai import AsyncOpenAI, APITimeoutError
from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .schema import RawNewsItem, Saga

class IntelligenceEngine:
    def __init__(self):
        if not LLM_API_KEY:
            raise ValueError("⚠️ [Critical Error] 未找到 LLM_API_KEY")
            
        print(f"🧠 [Brain] 大脑已连接: {LLM_MODEL} (Timeout=90s)")
        self.client = AsyncOpenAI(
            api_key=LLM_API_KEY, 
            base_url=LLM_BASE_URL,
            timeout=90.0
        )

    def _clean_json_string(self, text: str) -> str:
        """
        [新增] 清洗 LLM 返回的字符串，去除 Markdown 代码块标记
        """
        # 去除 ```json 或 ``` 标记
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        return text.strip()

    async def _safe_api_call(self, func_name: str, messages: List[Dict], max_retries=2) -> Dict:
        """内部通用 API 调用包装器，带重试、JSON清洗和类型修正"""
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
                raw_content = response.choices[0].message.content
                
                # 1. 清洗字符串 (去除 Markdown)
                clean_json = self._clean_json_string(raw_content)
                
                # 2. 解析 JSON
                try:
                    data = json.loads(clean_json)
                    
                    # 3. [核心修复] 列表自动拆包
                    # 如果 LLM 抽风返回了 [{"action":...}] 而不是 {"action":...}
                    if isinstance(data, list):
                        print(f"⚠️ [Intelligence] 检测到返回值为列表，正在自动拆包...")
                        if len(data) > 0 and isinstance(data[0], dict):
                            data = data[0]
                        else:
                            raise ValueError(f"返回了无效的列表格式: {str(data)[:50]}...")
                            
                    print(f"   [Debug] {func_name} | ✅ 响应成功 ({duration:.2f}s)")
                    return data
                    
                except json.JSONDecodeError:
                    print(f"⚠️ [Intelligence] JSON 解析失败: {raw_content[:50]}...")
                    raise ValueError("JSON Decode Error")

            except APITimeoutError:
                print(f"   [Debug] {func_name} | ❌ 请求超时 (90s)!")
            except Exception as e:
                print(f"   [Debug] {func_name} | ❌ 发生错误: {e}")
            
            # 如果不是最后一次重试，等待一会
            if attempt < max_retries - 1:
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
        
        **重要：请直接输出纯 JSON 对象，不要包裹在数组([])中。**
        """
        user_content = f"【现有 Sagas】: {json.dumps(saga_context, ensure_ascii=False)}\n\n【今日新闻】:\n标题: {news.title}\n内容: {news.content[:500]}..."

        result = await self._safe_api_call("Route", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ])
        
        # 兜底：如果 API 彻底失败返回空字典，则视为 ignore
        return result if result else {"action": "ignore"}

    async def analyze_new_saga(self, news: RawNewsItem) -> Dict[str, Any]:
        """生成新 Saga 元数据"""
        system_prompt = """
        提取元数据初始化 Saga：title, category, context_summary, causal_tag, importance。
        **重要：请直接输出纯 JSON 对象，不要包裹在数组([])中。**
        """
        return await self._safe_api_call("NewSaga", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"标题: {news.title}\n内容: {news.content[:800]}"}
        ])

    async def summarize_event(self, news: RawNewsItem) -> Dict[str, Any]:
        """生成 EventNode"""
        system_prompt = """
        请将这条新闻浓缩为一个 Event Node。
        输出纯 JSON 格式，包含以下字段:
        - summary: 50字以内的核心事实摘要。
        - causal_tag: 事件性质 (如 "Meeting", "Statement", "Accident")。
        - importance: 必须是 1 到 5 之间的整数 (int)。绝对禁止输出汉字(如"高")或字符串。
        
        **重要：请直接输出纯 JSON 对象，不要包裹在数组([])中。**
        """
        result = await self._safe_api_call("Summarize", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": news.content[:800]}
        ])
        
        # 兜底数据
        if not result:
            return {"summary": news.content[:100], "causal_tag": "TimeoutFallback", "importance": 1}
        return result