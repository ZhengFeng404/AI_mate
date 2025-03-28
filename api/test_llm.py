# test_llm_performance.py
import asyncio
from llm_handler import get_gemini_response_with_history
import time
import base64


async def test_scenario(scenario_name, user_input, image_base64=None):
    print(f"\n🚀 测试场景: {scenario_name}")
    print(f"输入内容: {user_input[:50]}...")

    # 模拟历史记录
    manual_history = [
        {"user_text": "你好", "ai_response": "你好！最近怎么样？"},
        {"user_text": "还不错，你呢？", "ai_response": "我也很好，谢谢关心！"}
    ]

    # 运行测试
    start_time = time.time()
    response = []
    async for chunk in get_gemini_response_with_history(
            user_input=user_input,
            user_id="test_user",
            manual_history=manual_history,
            image_base64=image_base64
    ):
        if chunk["type"] == "segment":
            response.append(chunk["segment"])
            break  # 仅捕获首segment

    print(f"首segment内容: {''.join(response)}")
    print(f"总测试时间: {time.time() - start_time:.4f}s")


if __name__ == "__main__":


    # 场景2：需要视觉响应的询问
    with open("test_image.jpg", "rb") as f:
        test_image = base64.b64encode(f.read()).decode()

    asyncio.run(test_scenario(
        "视觉相关询问",
        "你能看到我现在拿着什么吗？",
        image_base64=test_image
    ))