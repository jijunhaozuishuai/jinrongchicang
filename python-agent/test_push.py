from tools import send_wechat_alert

print("正在测试微信推送...")
result = send_wechat_alert.invoke({"message": "🚨 【测试】你的 AI 投资助手已成功连接！"})
print("测试结果:", result)