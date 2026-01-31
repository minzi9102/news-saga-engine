# src/date_utils.py
from datetime import datetime, timedelta
import pytz

def get_target_date_str():
    """
    获取目标日期字符串 (YYYYMMDD)。
    逻辑：获取上海时间，如果当前小时 < 20点，则取前一天，否则取当天。
    对应 N8N 节点: e0decf06-750d-4ccf-8515-fb68967ec67b
    """
    # 1. 设置时区
    shanghai_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(shanghai_tz)
    
    # 2. 判断小时数 (N8N logic: if shanghaiHour < 20)
    if now.hour < 20:
        target_date = now - timedelta(days=1)
        print(f"[Info] 当前时间 {now.strftime('%H:%M')} (小于20点), 获取昨日新闻: {target_date.strftime('%Y%m%d')}")
    else:
        target_date = now
        print(f"[Info] 当前时间 {now.strftime('%H:%M')} (大于等于20点), 获取今日新闻: {target_date.strftime('%Y%m%d')}")
        
    # 3. 格式化并移除斜杠 (YYYYMMDD)
    return target_date.strftime("%Y%m%d")

if __name__ == "__main__":
    # 测试打印
    print(get_target_date_str())