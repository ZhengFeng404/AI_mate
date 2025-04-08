import weaviate
import weaviate.classes as wvc  # 导入 v4 版本 client classes 用于配置
import weaviate.classes.config as wc
from weaviate.classes.config import Property, DataType, Configure
from weaviate.classes.query import MetadataQuery
import time

client = weaviate.connect_to_local(port=8081,
    grpc_port=50052,)


collection = client.collections.get("Events")

# 添加单个对象
jeopardy = client.collections.get("Events")

start_time = time.time()
response = jeopardy.query.near_text(query="健身", limit=3,
                                    return_metadata=MetadataQuery(distance=True))
end_time = time.time()
run_time = end_time - start_time

for o in response.objects:
    print(o.properties)
    print(o.metadata.distance)


print(f"查询运行时间: {run_time:.4f} 秒")
client.close()
