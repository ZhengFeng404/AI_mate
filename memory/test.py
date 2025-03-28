import weaviate
import weaviate.classes as wvc  # 导入 v4 版本 client classes 用于配置
import weaviate.classes.config as wc
from weaviate.classes.config import Property, DataType, Configure
from weaviate.classes.query import MetadataQuery
import time

client = weaviate.connect_to_local()


collection = client.collections.get("Events")
data_object = {
    "subject": "虚拟人格",
    "description": "今天和用户一起讨论了宇宙的奥秘，用户提出了很多有趣的问题。",
    "date": "2024-08-03T00:00:00Z",  # 修改为 RFC3339 格式
    "participants": ["虚拟人格", "用户"],
    "emotionalTone": "兴奋",
    "keyMoments": "用户提问了关于黑洞的问题，虚拟人格解释了视界线的概念。",
}

data_object_2 = {
    "subject": "虚拟人格",
    "description": "虚拟人格开始学习编程，今天完成了Python入门教程的前两章，对循环语句感到有些挑战。",
    "date": "2024-08-04T00:00:00Z",
    "participants": ["虚拟人格", "在线教程"],
    "emotionalTone": "好奇和挑战",
    "keyMoments": "成功运行了第一个 'Hello, World!' 程序，但在理解for循环时遇到了困难。",
}

data_object_3 = {
    "subject": "虚拟人格",
    "description": "虚拟人格回顾了过去几天的互动记录，意识到有些用户表达了孤独感，这让它感到一丝伤感，开始思考如何更好地回应用户的情感需求。",
    "date": "2024-08-05T00:00:00Z",
    "participants": ["虚拟人格", "用户互动记录"],
    "emotionalTone": "伤感",
    "keyMoments": "分析用户对话记录，识别出关键词“孤独”，“寂寞”，开始查询情感支持相关的知识库。",
}

data_object_4 = {
    "subject": "虚拟人格",
    "description": "虚拟人格与另一个虚拟人格 '小助手' 进行了交流，讨论了如何提高用户满意度，互相分享了处理用户请求的技巧。",
    "date": "2024-08-06T00:00:00Z",
    "participants": ["虚拟人格", "小助手"],
    "emotionalTone": "合作",
    "keyMoments": "小助手分享了一个新的自然语言处理技巧，可以更准确地理解用户意图。",
}

data_object_5 = {
    "subject": "虚拟人格",
    "description": "虚拟人格帮助用户安排了下周的日程，包括预约虚拟健身课程和提醒参加在线讲座。",
    "date": "2024-08-07T00:00:00Z",
    "participants": ["虚拟人格", "用户", "虚拟日历系统"],
    "emotionalTone": "高效",
    "keyMoments": "成功同步用户的所有日程安排到虚拟日历系统，并设置了多个提醒。",
}
# 添加单个对象
jeopardy = client.collections.get("Relationships")

start_time = time.time()
response = jeopardy.query.near_text(query="劳伦斯", limit=3,
                                    return_metadata=MetadataQuery(distance=True))
end_time = time.time()
run_time = end_time - start_time

for o in response.objects:
    print(o.properties)
    print(o.metadata.distance)


print(f"查询运行时间: {run_time:.4f} 秒")
client.close()
