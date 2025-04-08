# llm_handler.py
import google.generativeai as genai
# from google import genai
from dotenv import load_dotenv
import os
import json
import weaviate
from mem0 import Memory  # Import Mem0
import logging
import base64  # Import base64 library, although it might not be strictly necessary here, it's good to have when dealing with image data
import time
from utils.utils import load_api_key
from datetime import datetime
import asyncio
from PIL import Image
import io
import re

load_dotenv()


# Initialize Gemini (keep the same)
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
# client = genai.Client(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
model = genai.GenerativeModel('gemini-1.5-pro')


# Read character profile file (keep the same)
with open("../Prompt/Character/Lily_en.txt", "r") as file:
    character_profile = file.read()


# TODO: check if adding user_id in prompt can let AI distinguish user identity in future memory
def llm_response_generation(user_input, user_id, user_chat_sessions, manual_history,
                            image_base64=None):  # Add manual_history parameter
    """
    Main LLM response generation function (using manually maintained conversation history).

    Args:
        user_input (str): User input text
        user_id (str): User ID
        user_chat_sessions (dict): Still retained, but may no longer directly use ChatSession objects (can be used for other user-related data storage)
        manual_history (list): Manually maintained conversation history list <- Added manual_history parameter
        image_base64 (str, optional): User input image Base64 string, default is None

    Returns:
        dict: Dictionary containing response information (response_text, expression, motion, etc.)
    """
    # 1. No longer need to get or create ChatSession objects

    # 2. Call get_gemini_response_with_history to get Gemini response (modified part)
    gemini_response_dict = get_gemini_response_with_history(user_input, user_id, manual_history,
                                                            image_base64=image_base64)  # Pass manual_history

    # 3. Return result (keep the same)
    return gemini_response_dict


class MetadataParser:
    def __init__(self):
        self.state = "init"  # State: init | meta_started | meta_parsing
        self.buffer = ""
        self.metadata = {"expression": "normal", "motion": "idle", "reasoning": ""}

    def feed(self, chunk):
        output = ""
        self.buffer += chunk

        while True:
            if self.state == "init":
                # First stage: detect initial backticks
                idx = self.buffer.find('```')
                if idx == -1:
                    output += self.buffer
                    self.buffer = ""
                    break

                # Separate leading text
                output += self.buffer[:idx]
                self.buffer = self.buffer[idx + 3:]
                self.state = "meta_started"  # Enter the second stage

            elif self.state == "meta_started":
                # Second stage: detect subsequent meta keywords
                if len(self.buffer) >= 4:
                    if self.buffer.startswith("meta"):
                        # Found complete start tag
                        self.buffer = self.buffer[4:]
                        self.state = "meta_parsing"
                        self.meta_content = ""
                    else:
                        # Non-meta block, revert to initial state
                        output += '```' + self.buffer
                        self.buffer = ""
                        self.state = "init"
                    break
                else:
                    # Keep incomplete data and wait for the next chunk
                    break

            elif self.state == "meta_parsing":
                # Third stage: parse metadata content
                end_idx = self.buffer.find('```')
                if end_idx == -1:
                    self.meta_content += self.buffer
                    self.buffer = ""
                    break

                # Extract complete metadata
                self.meta_content += self.buffer[:end_idx]
                self.buffer = self.buffer[end_idx + 3:]
                self._parse_meta_content()
                self.state = "init"  # Reset state
        return output

    def _parse_meta_content(self):
        try:
            data = json.loads(self.meta_content.strip())
            self.metadata.update({
                "expression": data.get("expression", "normal"),
                "motion": data.get("motion", "idle"),
                "reasoning": data.get("reasoning", "")
            })
            print(f"✅ Metadata updated: {self.metadata}")
        except Exception as e:
            print(f"❌ Metadata parsing failed: {str(e)}")
            print(f"Error content: {self.meta_content}")


def split_text_stream(buffer, min_pause=5):
    # 标点符号及其权重
    pause_rules = [
        {'pattern': '.', 'weight': 1.0, 'offset': 1},    # 句号
        {'pattern': '!', 'weight': 1.0, 'offset': 1},    # 感叹号
        {'pattern': '?', 'weight': 1.0, 'offset': 1},    # 问号
        {'pattern': '...', 'weight': 0.9, 'offset': 3},  # 省略号
        #{'pattern': ',', 'weight': 0.7, 'offset': 1},    # 逗号
        {'pattern': ';', 'weight': 0.8, 'offset': 1},    # 分号
        #{'pattern': ':', 'weight': 0.8, 'offset': 1}     # 冒号
    ]

    # 寻找分割点
    def find_split_point(text):
        # 遍历文本寻找分割点
        for i in range(len(text)):
            for rule in pause_rules:
                pattern_len = len(rule['pattern'])
                if text[i:i + pattern_len] == rule['pattern']:
                    # 如果找到标点符号，检查是否满足最小长度要求
                    pos = i + rule['offset']
                    if pos >= min_pause:
                        return pos
        return None

    # 执行分割
    split_pos = find_split_point(buffer)
    if split_pos is not None:
        return buffer[:split_pos].strip(), buffer[split_pos:].lstrip()

    return None, buffer


def might_need_visual_info(user_input, recent_history=None):
    """
    Determine if the current conversation might need visual information

    Args:
        user_input: User input text
        recent_history: Recent conversation history (optional)

    Returns:
        bool: Whether visual information might be needed
    """
    # Visual related keywords
    visual_keywords = [
        "看", "瞧", "观察", "图", "照片", "图像", "图片", "相片", "样子", "长相",
        "外表", "外貌", "衣服", "穿着", "颜色", "见到", "眼前", "画面", "屏幕",
        "看到", "看见", "图中", "显示", "出现", "observe", "see", "look", "photo",
        "picture", "image", "appearance", "camera", "screen", "visible", "show"
    ]

    # Visual inquiry patterns
    visual_patterns = [
        r"你[能看]*?看[到见]*?[了吗什么]",
        r"[能可][以否]看[到见]",
        r"[能可][以否]描述",
        r"[能可][以否]告诉我你[看见]*?到[了什么]",
        r"这[是长看]什么",
        r"这个[东西物]是",
        r"我[的穿戴拿]着",
        r"[能可][否以]认出",
        r"你觉得[这我][个人]?[怎样如何]",
        r"[你有].*[摄像头相机]"
    ]

    # 1. Check for keyword match
    for keyword in visual_keywords:
        if keyword in user_input:
            return True

    # 2. Check for semantic pattern match
    for pattern in visual_patterns:
        if re.search(pattern, user_input):
            return True

    # 3. Check if recent conversation history is visually related (if any)
    if recent_history and len(recent_history) > 0:
        last_exchange = recent_history[-1]
        if "ai_response" in last_exchange:
            last_response = last_exchange["ai_response"]
            # If the AI recently mentioned visual content in its response, the user might be following up on a visual topic
            for keyword in visual_keywords:
                if keyword in last_response:
                    return True

    # By default, visual information is not needed
    return False


async def get_gemini_response_with_history(user_input, user_id, manual_history,
                                           image_base64=None):  # Modify function signature, add manual_history
    """
    Use manually maintained conversation history to call Gemini and generate a response.

    Args:
        user_input (str): User input text
        user_id (str): User ID
        manual_history (list): Manually maintained conversation history list <- Added manual_history parameter
        image_base64 (str, optional): User input image Base64 string, default is None
    """
    try:
        # Initialize state
        text_buffer = ""
        meta_parser = MetadataParser()
        has_yielded_first_chunk = False  # Track whether the first text chunk has been outputted
        default_metadata = {"expression": "normal", "motion": "idle"}  # Default metadata

        # Set a shorter text segment length to make the conversation more natural
        max_chunk_length = 15  # Default segment length reduced to 15 characters
        min_pause_length = 3  # Default minimum pause length remains 3 characters

        # 1. Retrieve memory (mid-term and long-term) - Retrieve every time (keep the same)
        # mid_term_memories = mem0.search(query=user_input, user_id="default_user", limit=3)
        # memories_str = "\n".join(f"- {entry['memory']}" for entry in mid_term_memories)
        # long_term_memories = query_long_term_memory_input(user_id, user_input)

        # 1. Build the JSON structure of the conversation history
        history_json = json.dumps(manual_history, ensure_ascii=False, indent=2)  # Keep JSON format, avoid ASCII escaping
        timestamp = datetime.now().isoformat()

        # 2. Generate Prompt - Keep the original format unchanged to ensure the model understands
        system_instruction = f"""
                === Your character profile ===
                {character_profile}

                === Current user identity ===
                **Name**: {user_id}
                Identity: You are a former classmate.

                === LLM Task Requirements ===
                You will fully embody your character profile and become the person you are playing. Based on this:
                - Think like a human.
                - Generate your response based on user input and conversation history.
                - In the conversation history, you should pay more attention to recent messages but can still combine the entire conversation history to understand the context.
                - Please note that you will try to associate and recall memories related to the current interaction, so there is long-term memory for reference, but these memories sometimes contain irrelevant content that is associated.
                - If there is a conflict between conversation history and long-term memory information, prioritize using the information from the conversation history.

                === Response Style Guide ===
                - **Refer to conversation history**: Refer to recent conversation history, especially within the last few tens of minutes, to ensure natural and coherent dialogue. However, also be mindful of the user's intention to switch topics.
                - **Keep it short and natural**: This is a real-time conversation, please be concise and natural like a real person chatting.
                - **Control response length**: In general, keep responses within 3 sentences unless the user explicitly asks for a detailed explanation.
                - **Like everyday conversation**: Use colloquial and relaxed expressions, avoid lengthy discussions.
                - **Concise response**: If it's a simple greeting or inquiry, respond with a short 1-sentence answer.
                - **Remember you are in a real conversation**: Real people rarely say a lot at once when chatting.

                === Visual Information Processing Guide ===
                - The visual image input you receive comes from your camera, and you will get a photo of what the current camera sees with each conversation turn.
                - Important: Only analyze visual information in the following situations:
                  1. The user explicitly asks questions about visual content (e.g., "What do you see?", "Can you describe what I look like?")
                  2. The user presents specific items and asks for related information
                  3. The user's question is directly related to the environment, appearance, or visual context
                - If the current conversation topic is abstract concepts, emotional exchanges, or does not involve visual content, please completely ignore the image information and answer the question directly.
                - There is no need to mention in the response whether you see or do not see the image unless the user directly asks about visual content.
                - Prioritize the text content and history of the conversation, and only analyze visual information when it is truly needed.

                - Choose an appropriate expression name and motion name from the following lists to add to the JSON structure.
                    Available expressions: ['吐舌', '表情-委屈', '表情-微笑', '表情-怨气', '表情-泪汪汪', '表情-流汗', '表情-流泪', '表情-生气', '表情-脸红', '表情-脸黑', '表情-花花', '表情-钱钱', '表情-？', '记仇', '记仇点击键']
                    Available motions: ["打瞌睡", "待机动作"]

                Please strictly return in the following format:
                1. First, wrap the JSON metadata (containing expression and motion, must be a separate chunk) with ```meta
                2. Then the natural language response
                3. Finally, wrap the reasoning process (optional) with ```meta again
                ```meta
                {{ "expression":"expression name", "motion":"motion name"}}
                ```
                [Your natural language response]

                ```meta
                {{ "reasoning":"thought process (anthropomorphic thinking)"}}
                ```

                === Dynamic Information ===
                **Conversation History**:
                ```json
                {history_json}
                ```
                **Long-term Memory**:
                None

                **Current User Input**:
                ```text
                {user_input}
                ```

                **System Time**
                {timestamp}
                """

        # 3. Prepare content (parts)
        parts = [{"text": system_instruction}]

        # Determine if the image needs to be included
        recent_history = manual_history[-3:] if len(manual_history) >= 3 else manual_history
        needs_visual = might_need_visual_info(user_input, recent_history)

        if image_base64 and needs_visual:
            start_time = time.time()
            print(f"✅ Detected that visual information might be needed, will include image data")
            try:
                image_data = base64.b64decode(image_base64)
                image = Image.open(io.BytesIO(image_data))
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                })
                print(f"Image processing time: {time.time() - start_time:.4f} seconds")
            except Exception as e:
                print(f"Base64 image data decoding failed: {str(e)}")
        else:
            if image_base64:
                print(f"⏩ Visual information might not be needed for this conversation, skipping image processing")

        # 4. Call LLM
        start_time_gemini = time.time()

        # Use parameters set for higher responsiveness
        generation_config = {
            "temperature": 0.7,  # Maintain some creativity
            "top_p": 0.95,
            "top_k": 40,
            "candidate_count": 1,
            "max_output_tokens": 1024,  # Reduce the maximum number of tokens to encourage short responses
        }



        # 5. Process streaming response - Optimize initial response speed
        fast_start_buffer = ""
        meta_seen = False

        async for chunk in await model.generate_content_async(
                contents=parts,
                generation_config=generation_config,
                stream=True
        ):
            raw_text = chunk.text
            if not raw_text:  # Skip empty responses
                continue

            # Record receiving time
            chunk_receive_time = time.time()
            chunk_latency = chunk_receive_time - start_time_gemini
            print(f"🔴 Raw response chunk: {repr(raw_text)} (Latency: {chunk_latency:.4f}s)")

            # Optimize initial response: detect separation of metadata and text
            if not meta_seen and "```meta" in raw_text:
                meta_seen = True

            # Process metadata chunk
            processed_text = meta_parser.feed(raw_text)

            # Collect fast start text
            if not has_yielded_first_chunk:
                fast_start_buffer += processed_text

                # Quickly return the first meaningful text - if conditions are met
                if (len(fast_start_buffer) >= 5 and meta_seen) or len(fast_start_buffer) >= 10:  # Reduced to 10 characters to start outputting
                    # Check if there is enough text to split
                    segment, remaining = split_text_stream(fast_start_buffer,
                                                           min_pause=min_pause_length)
                    if segment:
                        first_chunk_time = time.time() - start_time_gemini
                        print(f"🟢 Fast first response: {segment} (Total time: {first_chunk_time:.4f}s)")
                        yield {
                            "type": "segment",
                            "segment": segment,
                            "expression": meta_parser.metadata.get("expression", default_metadata["expression"]),
                            "motion": meta_parser.metadata.get("motion", default_metadata["motion"])
                        }
                        has_yielded_first_chunk = True
                        text_buffer = remaining
                    else:
                        text_buffer = fast_start_buffer
                        has_yielded_first_chunk = True
                else:
                    continue
            else:
                # Process subsequent normal stream text
                text_buffer += processed_text

            # Normally process text segments, using shorter segment lengths
            while True:
                segment, remaining = split_text_stream(text_buffer,
                                                       min_pause=min_pause_length)
                if not segment:
                    break

                # Record output time
                segment_time = time.time() - start_time_gemini
                print(f"🟡 Generated paragraph: {segment} (Total time: {segment_time:.4f}s)")
                yield {
                    "type": "segment",
                    "segment": segment,
                    "expression": meta_parser.metadata.get("expression", default_metadata["expression"]),
                    "motion": meta_parser.metadata.get("motion", default_metadata["motion"])
                }
                text_buffer = remaining

        # Process remaining content
        if text_buffer.strip():
            final_chunk_time = time.time() - start_time_gemini
            print(f"🟡 Final paragraph: {text_buffer.strip()} (Total time: {final_chunk_time:.4f}s)")
            yield {
                "type": "segment",
                "segment": text_buffer.strip(),
                "expression": meta_parser.metadata.get("expression", default_metadata["expression"]),
                "motion": meta_parser.metadata.get("motion", default_metadata["motion"])
            }

        print(f"✅ Generation complete, total time: {time.time() - start_time_gemini:.2f} seconds")
    except Exception as e:
        print(f"Stream error: {e}")