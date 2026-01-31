# test_brain.py
import asyncio
from src.intelligence import IntelligenceEngine
from src.schema import RawNewsItem, Saga, SagaStatus

async def test():
    print("=== 测试大脑连接 ===")
    brain = IntelligenceEngine()
    
    # 1. 模拟一条新闻
    fake_news = RawNewsItem(
        title="某国宣布对特定商品加征关税",
        url="http://test.com",
        content="今日，某国财政部发布公告，决定从下月起对进口电动汽车加征100%关税。此举旨在保护本土产业...",
        date="20260130"
    )
    
    # 2. 模拟现有的 Saga
    existing_sagas = [
        Saga(
            id="saga_001",
            title="全球贸易摩擦",
            category="国际经济",
            status=SagaStatus.ACTIVE,
            context_summary="近期全球多国贸易保护主义抬头，关税壁垒增加。",
            events=[],
            last_updated="20260101"
        )
    ]
    
    # 3. 测试路由
    print(f"正在分析新闻: {fake_news.title}...")
    decision = await brain.route_news(fake_news, existing_sagas)
    print(f"🧠 决策结果: {decision}")
    
    # 验证预期：应该返回 append 到 saga_001，或者 create
    
    # 4. 测试新 Saga 生成
    if decision.get("action") == "create":
        print("正在生成新 Saga 结构...")
        new_saga_data = await brain.analyze_new_saga(fake_news)
        print(f"✨ 新 Saga 数据: {new_saga_data}")

if __name__ == "__main__":
    asyncio.run(test())