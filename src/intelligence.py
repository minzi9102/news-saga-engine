import json
import time
import re
import asyncio
from typing import List, Dict, Any
from openai import AsyncOpenAI, APITimeoutError
from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .schema import RawNewsItem, Saga

# --- 常量定义：固定 AI 的输出空间 ---
CATEGORIES = ["政治外交", "宏观经济", "产业科技", "社会民生", "军事国防", "国际局势", "文体卫生", "突发事故"]
CAUSAL_TAGS = ["政策发布", "重要会议", "外交声明", "冲突爆发", "合作签署", "数据公布", "人事变动", "灾害事故", "其他"]

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
        """清洗 LLM 返回的字符串"""
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        return text.strip()

    async def _safe_api_call(self, func_name: str, messages: List[Dict], max_retries=2) -> Dict:
        """内部通用 API 调用包装器"""
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                print(f"   [Debug] {func_name} | 请求发送... (Attempt {attempt+1})")
                
                response = await self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1 # 保持低温度以确保格式稳定
                )
                
                duration = time.time() - start_time
                raw_content = response.choices[0].message.content
                clean_json = self._clean_json_string(raw_content)
                
                try:
                    data = json.loads(clean_json)
                    # 列表自动拆包
                    if isinstance(data, list):
                        if len(data) > 0 and isinstance(data[0], dict):
                            data = data[0]
                        else:
                            raise ValueError(f"Invalid list format: {str(data)[:50]}...")
                    
                    print(f"   [Debug] {func_name} | ✅ 响应成功 ({duration:.2f}s)")
                    return data
                    
                except json.JSONDecodeError:
                    print(f"⚠️ [Intelligence] JSON 解析失败: {raw_content[:50]}...")
                    raise ValueError("JSON Decode Error")

            except APITimeoutError:
                print(f"   [Debug] {func_name} | ❌ 请求超时 (90s)!")
            except Exception as e:
                print(f"   [Debug] {func_name} | ❌ 发生错误: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
        
        return {}

    async def route_news(self, news: RawNewsItem, active_sagas: List[Saga]) -> Dict[str, Any]:
        """
        [Prompt 优化点]
        1. CoT (Chain of Thought): 增加 'reason' 字段，强迫 AI 先思考后决策。
        2. 明确 'ignore' 标准: 明确指出排除天气、节气、纯会议通稿等无实质内容。
        3. 上下文注入: 明确告知现有 Saga 的定义。
        """
        saga_context = [{"id": s.id, "title": s.title, "keywords": s.title} for s in active_sagas]
        
        system_prompt = f"""
        你是由中央电视台聘请的高级新闻主编。请分析【输入新闻】，将其分配到合适的处理路径。
        
        现有活跃故事线 (Sagas):
        {json.dumps(saga_context, ensure_ascii=False)}

        决策逻辑：
        1. **APPEND (追加)**: 新闻内容是现有某个 Saga 的直接后续、进展、反转或相关评论。
        2. **CREATE (新建)**: 新闻是具有长期追踪价值的重大独立事件（如新政策、国际冲突、重大科技突破）。
        3. **IGNORE (忽略)**: 日常天气预报、节气介绍、无实质内容的纯礼节性会议、单纯的节日庆祝、广告嫌疑内容。

        请输出严格的 JSON 格式：
        {{
            "reason": "简述判断理由 (50字内)",
            "action": "append" | "create" | "ignore",
            "saga_id": "如果选append，必须填入对应ID，否则为null"
        }}
        """
        
        user_content = f"【今日新闻】\n标题: {news.title}\n内容摘要: {news.content[:500]}"

        result = await self._safe_api_call("Route", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ])
        
        return result if result else {"action": "ignore"}

    async def analyze_new_saga(self, news: RawNewsItem) -> Dict[str, Any]:
        """
        [Prompt 优化点]
        1. 限制 Category: 必须从预定义列表中选，方便前端筛选。
        2. 规范 Title: 要求新闻专业性，主谓宾结构。
        3. 增强 Context: 要求提取背景信息，不仅仅是摘要。
        """
        system_prompt = f"""
        你正在创建一个新的新闻专题（Saga）。请基于输入的新闻内容提取元数据。

        要求：
        1. title: 类似于维基百科词条的客观标题，不超过20字。
        2. category: 必须从以下列表中选择一个: {json.dumps(CATEGORIES, ensure_ascii=False)}
        3. context_summary: 200字以内的背景介绍，说明该事件为何重要，涉及哪些关键方。
        4. causal_tag: 事件的起因标签 (如: 政策发布, 突发事故)。
        5. importance: 整数 3-5 (新建的Saga通常重要性较高)。

        输出严格的 JSON 格式：
        {{
            "title": "...",
            "category": "...",
            "context_summary": "...",
            "causal_tag": "...",
            "importance": 4
        }}
        """
        return await self._safe_api_call("NewSaga", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"标题: {news.title}\n内容: {news.content[:800]}"}
        ])

    async def summarize_event(self, news: RawNewsItem) -> Dict[str, Any]:
        """
        [Prompt 优化点]
        1. 限制 Causal Tag: 使用固定列表。
        2. 规范 Importance: 给出具体的打分标准。
        3. 摘要风格: 要求客观陈述事实（Fact-based）。
        """
        system_prompt = f"""
        请将这条新闻处理为时间线上的一个节点（Event Node）。

        字段定义：
        - summary: 50字以内的核心事实摘要，去掉客套话，保留关键数据/人名/地点。
        - causal_tag: 必须从以下列表中选择: {json.dumps(CAUSAL_TAGS, ensure_ascii=False)}。
        - importance: 整数 1-5。
           * 5: 历史性时刻/国家级重大政策
           * 4: 重要进展/引发广泛关注
           * 3: 正常推进/标准报道
           * 2: 小范围变动/日常事务
           * 1: 提及性报道/背景补充

        输出严格的 JSON 格式：
        {{
            "summary": "...",
            "causal_tag": "...",
            "importance": 3
        }}
        """
        
        result = await self._safe_api_call("Summarize", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": news.content[:800]}
        ])
        
        # 兜底数据
        if not result:
            return {"summary": news.content[:100], "causal_tag": "其他", "importance": 1}
        return result