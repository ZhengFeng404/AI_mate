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

# Initialize Gemini model (for Embedding) - Choose the appropriate Gemini Embedding model
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
# embedding_model_name = 'models/text-embedding-004'
memory_process_model = genai.GenerativeModel('gemini-1.5-pro')  # PRO?
# gemini_embedding_model = genai.GenerativeModel(embedding_model_name) # Initialize Gemini Embedding model

# Initialize Weaviate client
try:
    client = weaviate.connect_to_local(port=8081,
                                       grpc_port=50052,)
    logging.info("Weaviate client connected successfully.")
except Exception as e:
    logging.error(f"Weaviate client connection failed: {e}")
    raise  # Re-raise the exception so that problems are discovered early during startup

with open("../Prompt/Character/Lily_en.txt", "r") as file:
    character_profile = file.read()

with open("weaviate_declarative_memory.txt", "r", encoding="utf-8") as file:
    weaviate_declarative_memory = file.read()

with open("weaviate_complex_memory.txt", "r", encoding="utf-8") as file:
    weaviate_complex_memory = file.read()


def query_long_term_memory(user_id, user_input, ai_response, memory_type):
    related_memory = []
    if memory_type == "declarative":
        # TODO: Goals and schedule will be put into prospective memory in the future
        collections = ["Events", "Knowledge", "Goals", "Profile"]
    elif memory_type == "complex":
        collections = ["Relationships", "Preferences"]
    for collection_name in collections:
        collection = client.collections.get(collection_name)
        existing_mem = collection.query.hybrid(
            query=f"{user_id}: {user_input}" + f"\nAI: {ai_response}",
            limit=2  # TODO: Figure out whether 1 or 2 would be better. Or 3?
        )
        for mem in existing_mem.objects:
            related_memory.append({"class": collection_name,
                                   "uuid": mem.uuid,
                                   "properties": mem.properties,
                                   })

    return related_memory


async def long_term_memory_async(user_input, ai_response, conversation_history, memory_type,
                                 last_two_long_term_memories=None,
                                 user_id="default_user"):  # memory_type can be "declarative" or "complex"
    """
    Background asynchronous processing of user input and AI response, determines whether to store memory, and stores it in Weaviate.
    """
    print("--- Entering process_and_store_memory_async function ---")  # ADDED DEBUG PRINT HERE

    try:
        # Add related memory from all collections
        related_memory = query_long_term_memory(user_id, user_input, ai_response, memory_type)
        print("related_memory: ", related_memory)
        print("success")

        declarative_memory_prompt = f"""
        **Output in English**
        === Your character profile ===
        {character_profile}

        === **Background LLM memory task instructions** ===
        You are one of the components of this virtual persona's long-term memory module,
        responsible for analyzing the virtual persona's conversations with others, including recent **conversation history**, filtering out information that needs to be remembered like a human, and storing or updating it in a structured manner in the knowledge base Weaviate.
        First, you need to determine if there is any long-term memory information related to **Events**, **Knowledge**, **Goals**, or **Profile**.
        **Note**, you can only focus on information related to **Events**, **Knowledge**, **Goals**, or **Profile**. If there is none, return `[]` directly.

        There are a total of six memory categories, and you are responsible for processing **Events**, **Knowledge**, **Goals**, and **Profile**:
        **Class Definition**
        When storing or updating memory, structured JSON data must be generated according to the class, and each `property` can only be filled with the data type allowed in the class.
        {weaviate_declarative_memory}

        First, you need to determine if there is any long-term memory information related to **Events**, **Knowledge**, **Goals**, or **Profile**.
        If storage is needed, you need to decide which Class to store the memory in and generate content for each attribute of that Class.
        If an update is needed, you need to decide which related memory to update and generate content based on the attributes of that Class.
        **Memory base related content** is obtained by searching the memory base based on user input and virtual persona response before running the long-term memory module.

        ### **1. Memory Storage Judgment Logic**
        Analyze user input, virtual persona response, and other historical information.
        First, determine if it contains worthwhile long-term memory information related to **Events**, **Knowledge**, **Goals**, or **Profile**. If not, return `[]` directly.
        Then choose whether to **ADD** or **UPDATE** memory:
        ✅ **ADD**:
        - If the information is **not** mentioned in the related memory content, choose to add a new memory entry.

        ✅ **UPDATE**:
        - If similar information already exists in the related memory content, but the new information provides more details, or if some change has occurred, or if it contradicts or overturns the new information, choose to update the existing entry.
        - **Example 1**:
          - **Old memory**: This Christmas, the user will invite their parents to a high-end restaurant in the city center.
          - **New information that needs to be updated**: This Christmas, the user will invite their parents and girlfriend to a high-end restaurant in the city center.
        - **Example 2**:
          - **Old memory**: This Christmas, the user will play the role of an elf reindeer.
          - **New information that needs to be updated**: This Christmas, the user will play the role of Santa Claus.

        ### **2. Select the Appropriate Weaviate Class**
        Categorize into one of the following:
        - **Events**: Describes a **specific event** experienced by an individual.
        - **Knowledge**: **New knowledge or information** acquired by the virtual persona.
        - **Goals**: Regarding an individual's **goals, plans, or desires**.
        - **Profile**: Records an individual's long-term identity information, including basic information, health status, social identity, economic status, living situation, etc.

        ### **3. JSON Format for Each Memory**
        The JSON format for each memory is as follows:
        \`\`\`json
        {{
            "class": "Events" / "Knowledge" / "Goals" / "Profile",
            "action": "ADD" / "UPDATE",
            "updated_object_id": "" // Leave blank if it's an ADD operation; if it's an UPDATE operation, enter the uuid of the corresponding memory entry being updated
            "properties_content": {{
                // Fill in the specific attribute content here, strictly following the class structure
                // If it is a time or date type attribute, the format should be RFC3339 format, YYYY-MM-DDTHH:mm:ssZ
            }}
        }}
        \`\`\`

        ### 4. **Output Example**
        #### **Example 1: Event Storage (Events Class)**
        **Conversation Content**:
        - User: I went to a newly opened Japanese restaurant last week, the food was delicious, and I ordered eel rice.
        - Virtual Persona: That sounds great! What's the name of the restaurant?

        **Output**
        \`\`\`json
        [
            {{
                "class": "Events",
                "action": "ADD",
                "updated_object_id": "",
                "properties_content": {{
                    "subject": "User",
                    "description": "The user went to a newly opened Japanese restaurant last week, ordered eel rice, and thought the food was delicious.",
                    "date": "2024-03-01T00:00:00Z",
                    "location": "Japanese restaurant",
                    "participants": ["User"],
                    "emotionalTone": "Satisfied",
                    "keyMoments": "User's enjoyment of the eel rice"
                }}
            }}
        ]
        \`\`\`

        #### **Example 2: Simultaneously Storing an Event (Events) and Updating a Goal (Goals)**
        **Conversation Content**:
        - **User**: Yesterday, I went to a new cat cafe with a friend, and the cats were super cute! I especially liked an orange cat that kept rubbing against me. Then I decided that I wouldn't keep rabbits for now, I want to keep an orange cat first.
        - **Virtual Persona**: That sounds lovely! What's the name of the cat cafe?

        Memory entry found in **memory base related content** that needs to be updated:
        \`\`\`json
        {{
                "class": "Goals",
                "updated_object_id": "vefd8239",
                "properties_content": {{
                    "owner": "User",
                    "goalDescription": "Keep a white rabbit",
                    "goalType": "Personal goal",
                    "motivation": "The user kept a white rabbit when they were a child and has been feeling nostalgic recently.",
                    "status": "Planning",
                    "progress": 0.0,
                    "obstacles": [],
                    "startingDate": "2024-07-20T00:00:00Z",
                    "priority": "Medium"
                }}
        }}
        \`\`\`

        **Output**:
        \`\`\`json
        [
            {{
                "class": "Events",
                "action": "ADD",
                "updated_object_id": "",
                "properties_content": {{
                    "subject": "User",
                    "description": "The user went to a new cat cafe with a friend and interacted with the cats in the cafe.",
                    "date": "2024-08-09T15:00:00Z",
                    "location": "Cat cafe",
                    "participants": ["User", "User's friend"],
                    "emotionalTone": "Joyful",
                    "keyMoments": "The user especially liked an orange cat that kept rubbing against the user"
                }}
            }},
            {{
                "class": "Goals",
                "action": "UPDATE",
                "updated_object_id": "vefd8239",
                "properties_content": {{
                    "owner": "User",
                    "goalDescription": "Keep an orange cat",
                    "goalType": "Personal goal",
                    "motivation": "The user liked an orange cat at the cat cafe and decided to keep a cat instead of a rabbit first.",
                    "status": "Planning",
                    "progress": 0.0,
                    "obstacles": ["Need to find a suitable cattery or adoption channel", "Need to prepare an environment for keeping a cat"],  // If obstacles are no longer needed, you can update to an empty string ""
                    "startingDate": "2024-08-10T00:00:00Z",
                    "priority": "High"
                }}
            }}
        ]
        \`\`\`

        ---

        ## **User Input**
        User{user_id}: {user_input}

        ## **Virtual Persona's Response**
        AI Response: {ai_response}

        ## **Memory Base Related Content**
        {related_memory}

        The following are the long-term memory entries you generated after the last two rounds of dialogue, which also serve as related content for this memory base:
        ```json
        {last_two_long_term_memories}
        ```

        ## **Conversation History**
        {conversation_history}

        **Please start analyzing the user input and the virtual persona's response, determine whether memory needs to be stored, and strictly output the result in the JSON format described above. If no memory needs to be stored, return `[]`.**
        """

        complex_memory_prompt = f"""
        **Output in English**
        === Your character profile ===
        {character_profile}

        === **Background LLM memory task instructions** ===
        You are one of the components of this virtual persona's long-term memory module,
        responsible for analyzing the virtual persona's conversations with others, including **conversation history**, filtering out information that needs to be remembered like a human, and storing or updating it in a structured manner in the knowledge base Weaviate.
        First, you need to determine if there is any long-term memory information related to **Relationships** or **Preferences**. If there is none, return `[]` directly.
        **Note**, you can only focus on information related to **relationships** or **preferences**.

        There are a total of six memory categories, and you are responsible for processing **Relationships** and **Preferences**:
        **Class Definition**
        When storing or updating memory, structured JSON data must be generated according to the class, and each `property` can only be filled with the data type allowed in the class.
        {weaviate_complex_memory}

        If storage is needed, you need to decide which Class to store the memory in and generate content for each attribute of that Class.
        If an update is needed, you need to decide which related memory to update and generate content based on the attributes of that Class.
        **Memory base related content** is obtained by searching the memory base based on user input and virtual persona response before running the long-term memory module.

        ### **1. Memory Storage Judgment Logic**
        Analyze user input, virtual persona response, and other historical information. First, determine if it contains worthwhile long-term memory information related to **Relationships** or **Preferences**.
        You should only focus on information related to **relationships** or **preferences**. If there is none, return `[]` directly.
        Then choose whether to **ADD** or **UPDATE** memory:
        ✅ **ADD**:
        - If the information is **not** mentioned in the related memory content, choose to add a new memory entry.

        ✅ **UPDATE**:
        - If similar information already exists in the related memory content, but the new information provides more details, or if some change has occurred, or if it contradicts or overturns the new information, choose to update the existing entry.
        - **Example 1**:
          - **Old memory**: The user likes milk tea.
          - **New information that needs to be updated**: The user especially likes **less sweet** milk tea.
        - **Example 2**:
          - **Old memory**: The user likes shooting games.
          - **New information that needs to be updated**: The user no longer likes shooting games.
        - **Example 3**:
          - **Old memory**: User A and User B are friends.
          - **New information that needs to be updated**: User A and User B are lovers.

        ### **2. Select the Appropriate Weaviate Class**
        Categorize into one of the following:
        - **Relationships**: Involves **changes in relationships** between people or entities.
        - **Preferences**: Expressed **likes, values**, or **emotional tendencies**.

        ### **3. JSON Format for Each Memory**
        The JSON format for each memory is as follows:
        \`\`\`json
        {{
            "class": "Relationships" / "Preferences",
            "action": "ADD" / "UPDATE",
            "updated_object_id": "" // Leave blank if it's an ADD operation; if it's an UPDATE operation, enter the uuid of the corresponding memory entry being updated
            "properties_content": {{
                // Fill in the specific attribute content here, strictly following the class structure
                // If it is a time or date type attribute, the format should be RFC3339 format, YYYY-MM-DDTHH:mm:ssZ
            }}
        }}
        \`\`\`

        ### 4. **Output Example**
        #### **Example 1: Preference Storage (Preferences)**
        **Conversation Content**:
        - **User**: Yesterday, I went to a new cat cafe with a friend, and the cats were super cute! I especially liked an orange cat that kept rubbing against me. Then I decided that I wouldn't keep rabbits for now, I want to keep an orange cat first.
        - **Virtual Persona**: That sounds lovely! What's the name of the cat cafe?

        **Output**
        \`\`\`json
        [
            {{
                "class": "Preferences",
                "action": "ADD",
                "updated_object_id": "",
                "properties_content": {{
                    "preferenceOwner": "User",
                    "preferenceType": "Animal preference",
                    "preferenceDescription": "The user especially likes orange cats.",
                    "reasoning": "The orange cat kept rubbing against the user, making the user feel it was very cute.",
                    "preferenceStrength": "Especially 4",
                    "confidenceLevel": 0.9
                    “preferenceCreationTime”: "2024-08-011T10:00:00Z"  // Note the correctness of the time and date format here, it should be YYYY-MM-DDTHH:mm:ssZ
                }}
            }}
        ]
        \`\`\`

        #### **Example 2: Relationship Update (Relationships)**
        **Conversation Content**:
        - User: I feel like you understand me better than before! We've talked many times.
        - Virtual Persona: I also feel like we've become more familiar!

        Memory entry found in **memory base related content** that needs to be updated:
        \`\`\`json
        {{
                "class": "Relationships",
                "updated_object_id": "abcd1234",
                "properties_content": {{
                    "subjectName": "User",
                    "relationshipDescription": "The user and the virtual persona initially became friends.",
                    "objectName": "Virtual persona name",
                    "relationshipType": "Friend",
                    "sentiment": "Trust",
                    "sentimentStrength": 0.5,
                    "relationshipStage": "Initial acquaintance",
                    "lastInteractionDate": "2024-07-01T10:00:00Z"
                    “relationshipCreationTime”: "2024-07-01T10:00:00Z"
                }}
        }}
        \`\`\`

        **Output**
        \`\`\`json
        [
            {{
                "class": "Relationships",
                "action": "UPDATE",
                "updated_object_id": "abcd1234",
                "properties_content": {{
                    "subjectName": "User",
                    "relationshipDescription": "The two became friends in early July 2024. Now the user thinks the virtual persona understands them better than before, and the original relationship between them has deepened.",
                    "objectName": "Virtual persona name",
                    "relationshipType": "Friend",
                    "sentiment": "Trust",
                    "sentimentStrength": 0.8,
                    "relationshipStage": "Familiar",
                    "lastInteractionDate": "2024-08-05T11:21:00Z"
                    “relationshipCreationTime”: "2024-07-01T10:00:00Z"
                }}
            }}
        ]
        \`\`\`

        ---

        ## **User Input**
        User{user_id}: {user_input}

        ## **Virtual Persona's Response**
        AI Response: {ai_response}

        ## **Recent Two Rounds of Memory**
        The following are the long-term memory entries you generated after the last two rounds of dialogue, which can be used as a reference for this memory generation task:
        ```json
        {last_two_long_term_memories}
        ```

        ## **Conversation History**
        {conversation_history}

        **Please start analyzing the user input and the virtual persona's response, determine whether memory needs to be stored, and strictly output the result in the JSON format described above. If no memory needs to be stored, return `[]`.**
        """

        if memory_type == "declarative":
            prompt = declarative_memory_prompt
        elif memory_type == "complex":
            prompt = complex_memory_prompt
        else:
            print("[Error] Wrong memory type in long term memory storage.")

        memory_entries = memory_process_model.generate_content(prompt)

        print("--- Raw Response from Memory Processing LLM ---")  # Debug print of the raw response from the LLM
        print(memory_entries.text)  # Print the raw response text from the LLM

        # ---  [Debug]  Print the string before attempting to parse JSON  ---
        json_str_to_parse = memory_entries.text.replace('`json', '').replace('`', '').strip()

        # Attempt to parse JSON
        try:
            memory_entries_json = json.loads(json_str_to_parse)

            file_path = "30_turns_memory_entries.json"  # You can customize the filename and path

            def save_memory_entries(new_entries, filename):
                """Stores in append mode, keeping all historical records"""
                try:
                    # Read existing data
                    existing_data = []
                    if os.path.exists(filename):
                        with open(filename, 'r', encoding='utf-8') as f:
                            try:
                                existing_data = json.load(f)
                                if not isinstance(existing_data, list):  # Handle single data format
                                    existing_data = [existing_data]
                            except json.JSONDecodeError:  # Handle empty file case
                                existing_data = []

                    # Merge new and old data
                    combined_data = existing_data + new_entries

                    # Write the updated complete dataset
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(combined_data, f,
                                  ensure_ascii=False,
                                  indent=2,
                                  separators=(',', ': '))

                    print(f"Successfully appended {len(new_entries)} entries, current total {len(combined_data)}")

                except Exception as e:
                    print(f"Failed to save: {str(e)}")
                    raise

            save_memory_entries(memory_entries_json, file_path)

            if not isinstance(memory_entries_json, list):  # Check if the parsed result is a list
                print(f"[Error] Parsed JSON is NOT a list, but: {type(memory_entries_json)}")  # Report error if it's not a list

            #  --- [Debug]  Check if each entry contains 'class' ---
            if isinstance(memory_entries_json, list):  # Check again to avoid type errors
                for entry in memory_entries_json:
                    if "class" not in entry:
                        print(f"[Error] Missing 'class' in JSON entry: {entry}")  # Report error if 'class' is missing

        except json.JSONDecodeError as e:
            print(f"[Error] JSON Decode Error: {e}")  # Print JSON parsing error information
            print(f"[Error] JSON String that caused error: {json_str_to_parse}")  # Print the JSON string that caused the parsing error
            return  # Return directly if JSON parsing fails to avoid subsequent code errors

        for entry in memory_entries_json:  # Use the parsed JSON data
            class_name = entry["class"]  # <-- Error might occur here if the JSON format is incorrect or 'class' is missing
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
        print(f"Background memory processing LLM call failed: {str(e)}")  # Original error print, keep it
        print(f"Exception details: {str(e)}")  # Print more detailed exception information


# Example call (for testing purposes, may need to be called from other modules in actual application)
async def main():
    user_input_text = "Yesterday, I went to a new cat cafe with a friend, and the cats were super cute! I especially liked an orange cat that kept rubbing against me. Then I decided that I wouldn't keep rabbits for now, I want to keep an orange cat first."
    ai_response_text = "That sounds lovely! What's the name of the cat cafe?"
    conversation_history_text = "The user mentioned wanting to keep rabbits before."

    await long_term_memory_async(user_input_text, ai_response_text, conversation_history_text)


if __name__ == "__main__":
    asyncio.run(main())