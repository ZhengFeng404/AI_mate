import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import weaviate
import asyncio
import ollama
import logging
from utils.utils import load_api_key

load_dotenv()

# 初始化 Gemini 模型 (用于 Embedding) -  选择合适的 Gemini Embedding 模型
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
#embedding_model_name = 'models/text-embedding-004'
memory_process_model = genai.GenerativeModel('gemini-1.5-pro') # PRO?
#gemini_embedding_model = genai.GenerativeModel(embedding_model_name) # 初始化 Gemini Embedding 模型

# 初始化 Weaviate 客户端
try:
    client = weaviate.connect_to_local()
    logging.info("Weaviate 客户端连接成功。")
except Exception as e:
    logging.error(f"Weaviate 客户端连接失败: {e}")
    raise  # 重新抛出异常，以便在启动时尽早发现问题


with open("../Prompt/Character/Lily.txt", "r", encoding="utf-8") as file:
    character_profile = file.read()

with open("weaviate_class.txt", "r", encoding="utf-8") as file:
    data_class_def = file.read()



def query_long_term_memory(user_input, ai_response):
    related_memory = []
    for collection_name in ["Events", "Relationships", "Knowledge", "Goals", "Preferences", "Profile"]:
        collection = client.collections.get(collection_name)
        existing_mem = collection.query.hybrid(
            query=f"User: {user_input}" + f"\nAI: {ai_response}",
            limit=2  # TODO: Figure out whether 1 or 2 would be better. Or 3?
        )
        for mem in existing_mem.objects:
            related_memory.append({"class": collection_name,
                                   "uuid": mem.uuid,
                                   "properties": mem.properties,
                                   })

    return related_memory

async def long_term_memory_async(user_input, ai_response, conversation_history,
                                 last_two_long_term_memories=None, user_id="default_user"):
    """
    后台异步处理用户输入和 AI 回复，判断是否存储记忆，并存储到 Weaviate.
    """
    print("--- Entering process_and_store_memory_async function ---")  # ADDED DEBUG PRINT HERE

    try:
        # Add related memory from all collections
        related_memory = query_long_term_memory(user_input, ai_response)
        print("related_memory: ", related_memory)
        print("success")

        memory_process_prompt_template = """
        ## **后台 LLM 记忆任务指示**
        你是虚拟人格的长期记忆模块，负责分析虚拟人格与他人的对话，像人类一样筛选出需要记住的信息，结构化地存储到知识库 Weaviate 中。

        你的任务是分析以下的用户输入和虚拟人格的回复，并判断是否需要将其作为记忆存储或更新到 Weaviate 知识库中。
        如果需要存储，你需要决定将记忆存储到哪个 Class，并为该 Class 的每个属性生成内容。
        如果需要更新，你需要决定更新哪条相关记忆，并根据该 Class 的属性生成内容。
        **记忆库相关内容**是运行长期记忆模块之前，根据用户输入和虚拟人格回复，从记忆库中搜索得到。


        ### **1. 记忆存储判断逻辑**
        分析用户输入和虚拟人格回复，首先判断是否包含**值得长期记忆的信息**，然后选择是**新增（ADD）**或者**更新（UPDATE）**记忆：
        ✅ **新增（ADD）**：
        - 记忆库相关内容中 **没有** 提及该信息，则选择新增记忆条目。

        ✅ **更新（UPDATE）**：
        - 记忆库相关内容中已有相似信息，但新的信息提供了更多细节，或者发生了某种改变，或与与新信息矛盾或被推翻，则选择更新现有条目。
        - **示例1**：
          - **旧记忆**：用户喜欢奶茶。
          - **需要更新的新信息**：用户特别喜欢 **少糖的** 奶茶。
        - **示例2**：
          - **旧记忆**：用户A和用户B是朋友。
          - **需要更新的新信息**：：用户A和用户B是恋人。
        - **示例3**：
          - **旧记忆**：今年圣诞节用户要扮演精灵驯鹿。
          - **需要更新的新信息**：今年圣诞节用户要扮演圣诞老人。
        - **示例4**：
          - **旧记忆**：用户喜欢枪战游戏。
          - **需要更新的新信息**：用户不喜欢枪战游戏了。

        ### **2. 选择适合的 Weaviate Class**
        若需要**新增（ADD）**存储，归类到以下之一：
        - **Events (事件)**：描述某个体经历的**具体事件**。
        - **Relationships (关系)**：涉及人与人或实体间的**关系变化**。
        - **Knowledge (知识)**：虚拟人格获取的**新知识或信息**。
        - **Goals (目标)**：关于某个体的**目标、计划或愿望**。
        - **Preferences (偏好)**：表达的**喜好、价值观**或**情感倾向**。

        ### **3. Weaviate Class 定义 (重要！请LLM务必参考以下Class定义生成JSON)**
        以下是 Weaviate 数据库 Class 结构定义，你必须严格遵循。
        当存储记忆时，必须根据 class 生成结构化 JSON 数据，每个 \`property\` 只能填充 class 中允许的数据类型。
        {data_class_def}

        ### **4. 每条记忆JSON格式**
        每条记忆JSON格式如下：
        \`\`\`json
        {{
            "class": "Events" / "Relationships" / "Knowledge" / "Goals" / "Preferences",
            "action": "ADD" / "UPDATE",
            "updated_object_id": "" // 如果是ADD操作，则留空；如果是UPDATE操作，则录入对应的被更新的记忆条目的uuid
            "properties_content": {{
                // 此处填写具体的属性内容，严格遵循 class 结构
            }}
        }}
        \`\`\`

        ### 5. **输出示例**
        #### **示例 1: 事件存储 (Events Class)**
        **对话内容**：
        - 用户：我上周去了一家新开的日式餐厅，食物很好吃，我点了鳗鱼饭。
        - 虚拟人格：听起来很棒！这家餐厅叫什么名字？

        **输出**
        \`\`\`json
        [
            {{
                "class": "Events",
                "action": "ADD",
                "updated_object_id": "",
                "properties_content": {{
                    "subject": "用户",
                    "description": "用户上周去了一家新开的日式餐厅，点了鳗鱼饭，并认为食物很好吃。",
                    "date": "2024-03-01T00:00:00Z",
                    "location": "日式餐厅",
                    "participants": ["用户"],
                    "emotionalTone": "满意",
                    "keyMoments": "用户对鳗鱼饭的喜爱"
                }}
            }}
        ]
        \`\`\`

        #### **示例 2: 关系更新 (Relationships Class)**
        **对话内容**：
        - 用户：我觉得你比之前更理解我了！我们已经聊了很多次了。
        - 虚拟人格：我也觉得我们变得更熟悉了！

        **记忆库相关内容**中发现的需要被更新的记忆条目：
        \`\`\`json
        {{
                "class": "Relationships",
                "updated_object_id": "abcd1234",
                "properties_content": {{
                    "subjectName": "用户",
                    "relationshipDescription": "用户和虚拟人格初步成为朋友。",
                    "objectName": "虚拟人格",
                    "relationshipType": "朋友",
                    "sentiment": "信任",
                    "sentimentStrength": 0.5,
                    "relationshipStage": "初识",
                    "lastInteractionDate": "2024-07-01T10:00:00Z"
                    “relationshipCreationTime”: "2024-07-01T10:00:00Z"
                }}
        }}
        \`\`\`

        **输出**
        \`\`\`json
        [
            {{
                "class": "Relationships",
                "action": "UPDATE",
                "updated_object_id": "abcd1234",
                "properties_content": {{
                    "subjectName": "用户",
                    "relationshipDescription": "两人在24年7月初成为了朋友，现在用户认为虚拟人格比之前更理解自己，双方原有关系加深。",
                    "objectName": "虚拟人格",
                    "relationshipType": "朋友",
                    "sentiment": "信任",
                    "sentimentStrength": 0.8,
                    "relationshipStage": "熟悉",
                    "lastInteractionDate": "2024-08-05T11:21:00Z"
                    “relationshipCreationTime”: "2024-07-01T10:00:00Z"
                }}
            }}
        ]
        \`\`\`

        #### **示例 3: 同时存储事件 (Events) 和 偏好 (Preferences)，并更新目标 (Goals)**
        **对话内容**：
        - **用户**：昨天我和朋友去了一家新的猫咖啡馆，里面的猫超级可爱！我特别喜欢一只橘猫，它一直蹭我。然后我就决定了，我先不养兔子了，我要先养一只橘猫。
        - **虚拟人格**：听起来很温馨！这家猫咖叫什么名字？

        **记忆库相关内容**中发现的需要被更新的记忆条目：
        \`\`\`json
        {{
                "class": "Goals",
                "updated_object_id": "vefd8239",
                "properties_content": {{
                    "owner": "用户",
                    "goalDescription": "养一只橘猫",
                    "goalType": "个人目标",
                    "motivation": "用户在猫咖啡馆喜欢上了一只橘猫，决定先养猫而不是兔子。",
                    "status": "计划中",
                    "progress": 0.0,
                    "obstacles": ["需要找到合适的猫舍或领养渠道", "需要准备养猫的环境"],
                    "startingDate": "2024-08-10T00:00:00Z",
                    "priority": "高"
                }}
        }}
        \`\`\`

        **输出**：
        \`\`\`json
        [
            {{
                "class": "Events",
                "action": "ADD",
                "updated_object_id": "",
                "properties_content": {{
                    "subject": "用户",
                    "description": "用户和朋友一起去了一家新的猫咖啡馆，并与店里的猫互动。",
                    "date": "2024-08-09T15:00:00Z",
                    "location": "猫咖啡馆",
                    "participants": ["用户", "用户的朋友"],
                    "emotionalTone": "愉悦",
                    "keyMoments": "用户特别喜欢一只橘猫，它一直蹭用户"
                }}
            }},
            {{
                "class": "Preferences",
                "action": "ADD",
                "updated_object_id": "",
                "properties_content": {{
                    "preferenceOwner": "用户",
                    "preferenceType": "动物偏好",
                    "preferenceDescription": "用户特别喜欢橘猫。",
                    "reasoning": "橘猫一直蹭用户，让用户觉得很可爱。",
                    "preferenceStrength": "特别4",
                    "confidenceLevel": 0.9
                    “preferenceCreationTime”: "2024-08-011T10:00:00Z"  // 注意此处时间日期格式的正确性，应该是YYYY-MM-DDTHH:mm:ssZ
                }}
            }},
            {{
                "class": "Goals",
                "action": "UPDATE",
                "updated_object_id": "vefd8239",
                "properties_content": {{
                    "owner": "用户",
                    "goalDescription": "养一只橘猫",
                    "goalType": "个人目标",
                    "motivation": "用户在猫咖啡馆喜欢上了一只橘猫，决定先养猫而不是兔子。",
                    "status": "计划中",
                    "progress": 0.0,
                    "obstacles": "",  // 如果不需要obstacles了，可以更新为空字符串 "" 或 null，根据 Class 定义
                    "startingDate": "2024-08-10T00:00:00Z",
                    "priority": "高"
                }}
            }}
        ]
        \`\`\`

        ---

        ## **用户输入**
        {user_input}

        ## **虚拟人格的回复**
        {ai_response}

        ## **记忆库相关内容**
        {related_memory}
        
        ## **最近两轮记忆**
        以下是最近两轮对话后，你生成的长期记忆条目，可以作为本次记忆生成任务的参考：
        ```json
        {last_two_long_term_memories}
        ```

        ## **对话历史**
        {conversation_text}

        **请开始分析用户输入和虚拟人格回复，判断是否需要存储记忆，并严格按照上述JSON格式输出结果，如果不需要存储任何记忆，则返回 `[]`。**
        """



        prompt = memory_process_prompt_template.format(data_class_def=data_class_def,
                                                       user_input=user_input, ai_response=ai_response,
                                                       related_memory=related_memory,
                                                       last_two_long_term_memories=last_two_long_term_memories,
                                                       conversation_text=conversation_history)

        memory_entries = memory_process_model.generate_content(prompt)

        print("--- Raw Response from Memory Processing LLM ---") # 调试打印 LLM 原始回复
        print(memory_entries.text) # 打印 LLM 原始回复文本

        # ---  [调试]  打印尝试解析 JSON 前的字符串  ---
        json_str_to_parse = memory_entries.text.replace('`json', '').replace('`', '').strip()

        # 尝试解析 JSON
        try:
            memory_entries_json = json.loads(json_str_to_parse)

            if not isinstance(memory_entries_json, list): #  检查解析结果是否是列表
                print(f"[Error] Parsed JSON is NOT a list, but: {type(memory_entries_json)}") #  如果不是列表，报错

            #  --- [调试]  检查每个条目是否包含 'class' ---
            if isinstance(memory_entries_json, list): #  再次检查以避免类型错误
                for entry in memory_entries_json:
                    if "class" not in entry:
                        print(f"[Error] Missing 'class' in JSON entry: {entry}") #  如果缺少 'class'，报错

        except json.JSONDecodeError as e:
            print(f"[Error] JSON Decode Error: {e}") # 打印 JSON 解析错误信息
            print(f"[Error] JSON String that caused error: {json_str_to_parse}") #  打印导致解析错误的 JSON 字符串
            return #  如果 JSON 解析失败，直接返回，避免后续代码报错


        for entry in memory_entries_json: #  使用解析后的 JSON 数据
            class_name = entry["class"] #  <--  错误可能发生在这里，如果 JSON 格式不正确 或 缺少 class
            collection = client.collections.get(class_name)
            properties_content = entry["properties_content"]
            action = entry["action"]
            if action == "UPDATE":
                uuid = entry["updated_object_id"]
                collection.data.update(
                    uuid=uuid,
                    properties=properties_content
                )
            elif action == "ADD":
                collection.data.insert(properties_content)


    except Exception as e:
        print(f"后台记忆处理 LLM 调用失败: {str(e)}") # 原始的错误打印，保留
        print(f"Exception details: {str(e)}") #  打印更详细的异常信息


# 示例调用 (测试用，实际应用中可能需要从其他模块调用)
async def main():
    user_input_text = "昨天我和朋友去了一家新的猫咖啡馆，里面的猫超级可爱！我特别喜欢一只橘猫，它一直蹭我。然后我就决定了，我先不养兔子了，我要先养一只橘猫。"
    ai_response_text = "听起来很温馨！这家猫咖叫什么名字？"
    conversation_history_text = "用户之前提到过想养兔子。"

    await long_term_memory_async(user_input_text, ai_response_text, conversation_history_text)



if __name__ == "__main__":
    asyncio.run(main())
