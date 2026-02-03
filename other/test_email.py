# test_email.py
import os
from dotenv import load_dotenv
from src.notifier import EmailNotifier

# 1. 加载环境变量
load_dotenv()

def test_send():
    print("📧 正在测试邮件发送...")
    
    # 2. 初始化发送器
    notifier = EmailNotifier()
    
    # 3. 模拟发送
    try:
        notifier.send_daily_report(
            date_str="2024-TEST-DAY", 
            markdown_content="# 测试标题\n\n这是一封来自本地测试脚本的验证邮件。\n\n- 如果你看到这行字，说明 SMTP 配置成功！"
        )
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_send()