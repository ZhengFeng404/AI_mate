import weaviate
import weaviate.classes as wvc  # 导入 v4 版本 client classes 用于配置
import weaviate.classes.config as wc
from weaviate.classes.config import Property, DataType, Configure

client = weaviate.connect_to_local()

# 检查 Collection 是否已存在，如果存在则删除 (方便示例运行，实际应用中按需处理)
collection_names = ["Events", "Relationships", "Knowledge", "Goals", "Preferences"]
for collection_name in collection_names:
    if client.collections.exists(collection_name):
        client.collections.delete(collection_name)

print("旧的 Class (如果存在) 已删除")

# 1. 定义 Events Collection
client.collections.create(
    name="Events",
    description="存储某个体经历的事件",
    properties=[
        Property(
            name="individual",
            data_type=DataType.TEXT,
            description="参与事件的主体人物"
        ),
        Property(
            name="description",
            data_type=DataType.TEXT,
            description="事件的文字描述"
        ),
        Property(
            name="date",
            data_type=DataType.DATE,
            description="事件发生的时间",
            indexRangeFilters=True
        ),
        Property(
            name="duration",
            data_type=DataType.NUMBER,
            description="事件持续时长 (例如：分钟，小时)",
            indexRangeFilters=True
        ),
        Property(
            name="location",
            data_type=DataType.TEXT,
            description="事件发生的地点"
        ),
        # Adding geo coordinates is an interesting idea but needs more consideration and better design
        #Property(name="geoLocation",data_type=DataType.GEO_COORDINATES,description="事件发生的地点的经纬度"),
        Property(
            name="locationDetails",
            data_type=DataType.TEXT,
            description="更详细的地点描述 (例如：公园的哪个区域，咖啡馆的座位，家里客厅的沙发)"
        ),
        Property(
            name="participants",
            data_type=DataType.TEXT_ARRAY,
            description="事件参与者"
        ),
        Property(
            name="emotionalTone",
            data_type=DataType.TEXT,
            description="事件的情感基调 (例如：快乐，悲伤，兴奋)"
        ),
        Property(
            name="keyMoments",
            data_type=DataType.TEXT,
            description="事件中的关键细节"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Events Collection Schema 创建成功")
client.close()

# 2. 定义 Relationships Collection
client.connect()
client.collections.create(
    name="Relationships",
    description="存储某个体与其他人或实体的关系",
    properties=[
        Property(name="subjectName", data_type=DataType.TEXT,
                            description="关系主体的姓名或实体名称"),
        Property(name="relationshipDescription", data_type=DataType.TEXT, description="关系描述"),
        Property(name="objectName", data_type=DataType.TEXT,
                            description="相关人员姓名或实体名称"),
        Property(name="relationshipType", data_type=DataType.TEXT,
                            description="关系类型 (例如：朋友，家人，恋爱，雇佣，同事，偶像)"),
        Property(name="sentiment", data_type=DataType.TEXT,
                            description="对关系对象的情感倾向 (例如：喜欢，信任，依赖，厌恶，嫉妒)"),
        Property(name="sentimentStrength", data_type=DataType.NUMBER,
                            description="关系情感倾向强度 (例如 0-1 范围)"),
        Property(name="relationshipStage", data_type=DataType.TEXT,
                            description="关系所处阶段 (例如：初识，熟悉，稳定，淡漠，崩溃)"),
        Property(
            name="lastInteractionDate",
            data_type=DataType.DATE,
            description="最近一次互动时间",
            indexRangeFilters=True
        ),
        Property(
            name="relationshipCreationTime",
            data_type=DataType.DATE,
            description="该关系被记入记忆库的时间",
        )
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Relationships Collection Schema 创建成功")
client.close()

# 3. 定义 Knowledge Collection
client.connect()
client.collections.create(
    name="Knowledge",
    description="存储虚拟人格学习到的知识、事实、技能等",
    properties=[
        Property(
            name="title",
            data_type=DataType.TEXT,
            description="知识条目的标题或名称"
        ),
        Property(
            name="content",
            data_type=DataType.TEXT,
            description="知识条目的详细内容"
        ),
        Property(
            name="category",
            data_type=DataType.TEXT,
            description="知识所属类别 (例如：游戏，动漫，医学，法学)"
        ),
        Property(
            name="source",
            data_type=DataType.TEXT,
            description="知识来源 (例如：书籍，网站，对话)"
        ),
        Property(
            name="keywords",
            data_type=DataType.TEXT_ARRAY,
            description="一列关键词")
        ,
        Property(
            name="relevanceScore",
            data_type=DataType.NUMBER,
            description="知识条目的相关性评分"
        ),
        Property(
            name="confidenceLevel",
            data_type=DataType.NUMBER,
            description="对知识的确信程度 (例如 0-1 范围，是知识真实性的可信度)"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Knowledge Collection Schema 创建成功")
client.close()

# 4. 定义 Goals Collection
client.connect()
client.collections.create(
    name="Goals",
    description="用于存储某个体的目标、计划、愿望或决定",
    properties=[
        Property(
            name="owner",
            data_type=DataType.TEXT,
            description="该目标的拥有者"
        ),
        Property(
            name="goalDescription",
            data_type=DataType.TEXT,
            description="目标描述"
        ),
        Property(
            name="goalType",
            data_type=DataType.TEXT,
            description="目标类型"
        ),
        Property(
            name="motivation",
            data_type=DataType.TEXT,
            description="目标的动机和原因"
        ),
        Property(
            name="status",
            data_type=DataType.TEXT,
            description="目标实现状态 (例如：计划中，进行中，已完成，已放弃)"
        ),
        Property(
            name="progress",
            data_type=DataType.NUMBER,
            description="目标完成进度 (例如 0-1 范围，或者百分比)"
        ),
        Property(
            name="obstacles",
            data_type=DataType.TEXT_ARRAY,
            description="实现目标过程中遇到的障碍和挑战"
        ),
        Property(
            name="startingDate",
            data_type=DataType.DATE,
            description="目标设立日期",
            indexRangeFilters=True

        ),
        Property(
            name="endingDate",
            data_type=DataType.DATE,
            description="目标结束日期"
        ),
        Property(
            name="priority",
            data_type=DataType.TEXT,
            description="目标优先级 (例如：高，中，低)"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Goals Collection Schema 创建成功")
client.close()

# 5. 定义 Preferences Collection
client.connect()
client.collections.create(
    name="Preferences",
    description="存储某个体的偏好、喜好、价值观等",
    properties=[
        Property(
            name="preferenceOwner",
            data_type=DataType.TEXT,
            description="偏好拥有者"
        ),
        Property(
            name="preferenceType",
            data_type=DataType.TEXT,
            description="偏好类型 (例如：食物偏好，音乐偏好，颜色偏好，价值观，道德观)"
        ),
        Property(
            name="preferenceDescription",
            data_type=DataType.TEXT,
            description="偏好描述"
        ),
        Property(
            name="reasoning",
            data_type=DataType.TEXT,
            description="偏好背后的原因或逻辑"
        ),
        Property(
            name="preferenceStrength",
            data_type=DataType.TEXT,
            description="分为五档强度（轻微1，有些2，中等3，特别4，强烈5）"
        ),
        Property(
            name="confidenceLevel",
            data_type=DataType.NUMBER,
            description="偏好确信程度 (例如 0-1 范围)"
        ),
        Property(
            name="preferenceCreationTime",
            data_type=DataType.DATE,
            description="该偏好被记入记忆库的时间"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Preferences Collection Schema 创建成功")

print("所有 Collection Schema 定义完成！")
client.close()