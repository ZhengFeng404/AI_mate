
# test_llm_handler.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, mock_open
import json
from llm_handler import query_long_term_memory_input, llm_response_generation, get_gemini_response_with_history  # 假设你的 llm_handler.py 文件名为 llm_handler.py

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """自动 mock 环境变量"""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")

@pytest.fixture
def mock_load_api_key():
    """Mock load_api_key 函数"""
    with patch('llm_handler.load_api_key', return_value="test_api_key") as mock:
        yield mock

@pytest.fixture
def mock_weaviate_client():
    """Mock Weaviate 客户端和相关方法"""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_query = MagicMock()
    mock_hybrid = AsyncMock() # 使用 AsyncMock for hybrid

    mock_client.collections.get.return_value = mock_collection
    mock_collection.query = mock_query
    mock_query.hybrid = mock_hybrid

    with patch('llm_handler.weaviate.connect_to_local', return_value=mock_client):
        yield mock_client, mock_collection, mock_query, mock_hybrid

@pytest.fixture
def mock_genai_modules():
    """Mock google.generativeai 模块和相关类/方法"""
    mock_genai = MagicMock()
    mock_generative_model = MagicMock()
    mock_generate_content_async = AsyncMock() #  使用 AsyncMock
    mock_generate_content_stream = AsyncMock() # 使用 AsyncMock for stream

    mock_genai.GenerativeModel.return_value = mock_generative_model
    mock_generative_model.generate_content_async = mock_generate_content_async
    mock_generative_model.generate_content_stream = mock_generate_content_stream
    mock_genai.GenerativeModel = mock_generative_model #  直接赋值 Mock 对象
    mock_genai.generate_content_stream = mock_generate_content_stream # 直接赋值 Mock 对象


    with patch('llm_handler.genai', new=mock_genai) as mock: #  直接替换 genai 模块
        yield mock_genai, mock_generative_model, mock_generate_content_async, mock_generate_content_stream


@pytest.fixture
def mock_mem0_memory():
    """Mock Mem0 Memory 类"""
    mock_memory_instance = MagicMock()
    mock_memory_from_config = MagicMock(return_value=mock_memory_instance)
    mock_memory_search = AsyncMock(return_value=[{"memory": "mock memory"}]) # 使用 AsyncMock

    mock_memory_instance.search = mock_memory_search

    with patch('llm_handler.Memory.from_config', mock_memory_from_config) as mock_from_config, \
         patch('llm_handler.Memory', return_value=mock_memory_instance) as mock_memory_cls: #  Mock Memory 类本身
        yield mock_memory_instance, mock_memory_from_config, mock_memory_search, mock_memory_cls


@pytest.fixture
def mock_character_profile():
    """Mock 角色设定文件读取"""
    mock_profile_content = "This is mock character profile."
    with patch("builtins.open", mock_open(read_data=mock_profile_content)):
        yield mock_profile_content

@pytest.mark.asyncio
async def test_query_long_term_memory_input(mock_weaviate_client):
    """测试 query_long_term_memory_input 函数"""
    mock_client, _, mock_query, mock_hybrid = mock_weaviate_client
    mock_hybrid.return_value.objects = [{"properties": {"content": "mock memory content"}}] # 模拟返回数据

    user_input = "test input"
    related_memory = await query_long_term_memory_input(user_input)

    mock_client.collections.get.assert_called() #  assert_called 比 assert_called_once 更宽松，更适合这里
    mock_hybrid.assert_called()
    assert isinstance(related_memory, list)
    #  更细致地检查返回结果，例如检查每个元素的结构和内容
    for mem_result in related_memory:
        assert hasattr(mem_result, 'objects') # 检查是否是 Weaviate 的 QueryResponse 对象 (或 Mock 对象)


@pytest.mark.asyncio
async def test_get_gemini_response_with_history_text_only(mock_genai_modules, mock_character_profile, mock_weaviate_client):
    """
    测试 get_gemini_response_with_history 函数，仅文本输入场景
    """
    mock_genai, mock_generative_model, mock_generate_content_async, mock_generate_content_stream = mock_genai_modules
    mock_hybrid_query_results = MagicMock()
    mock_hybrid_query_results.objects = [] #  模拟长期记忆查询结果为空
    mock_weaviate_client[3].return_value = mock_hybrid_query_results #  设置 mock_hybrid 的返回值

    # 模拟 Gemini 模型返回的流式响应
    mock_stream_response = [
        AsyncMock(text='{"expression": "mock_expression", "motion": "mock_motion", "reasoning": "mock reasoning", "response_text": "mock response"}'),
        AsyncMock(text='```json'),
        AsyncMock(text='{"expression": "mock_expression2"'),
        AsyncMock(text=', "motion": "mock_motion2"'),
        AsyncMock(text=', "reasoning": "mock reasoning2"'),
        AsyncMock(text=', "response_text": "segment 1,"'),
        AsyncMock(text='}```'),
        AsyncMock(text='segment 2。')
    ]
    mock_generate_content_async.return_value = mock_stream_response  #  修改为 mock_generate_content_async


    user_input = "你好"
    user_id = "test_user"
    manual_history = [{"role": "user", "content": "你好"}]

    async for response_segment in get_gemini_response_with_history(user_input, user_id, manual_history):
        if response_segment["type"] == "complete":
            result = response_segment["result"]
            assert "expression" in result
            assert "motion" in result
            assert "reasoning" in result
            assert "response_text" in result
            assert result["response_text"] == "segment 1,segment 2。" # 检查最终的 response_text 是否正确合并


@pytest.mark.asyncio
async def test_get_gemini_response_with_history_with_image(mock_genai_modules, mock_character_profile, mock_weaviate_client):
    """测试 get_gemini_response_with_history 函数，包含图像输入场景"""
    mock_genai, mock_generative_model, mock_generate_content_async, mock_generate_content_stream = mock_genai_modules
    mock_hybrid_query_results = MagicMock()
    mock_hybrid_query_results.objects = [] #  模拟长期记忆查询结果为空
    mock_weaviate_client[3].return_value = mock_hybrid_query_results #  设置 mock_hybrid 的返回值
    mock_generate_content_async.return_value = [AsyncMock(text='{"expression": "mock_expression", "motion": "mock_motion", "reasoning": "mock reasoning", "response_text": "mock response"}')] # 模拟 Gemini 返回

    user_input = "你好，这是我的照片"
    user_id = "test_user"
    manual_history = [{"role": "user", "content": "你好"}]
    image_base64 = "mock_base64_image_data" #  使用 mock base64 数据

    async for response_segment in get_gemini_response_with_history(user_input, user_id, manual_history, image_base64=image_base64):
        if response_segment["type"] == "complete":
            result = response_segment["result"]
            assert "expression" in result
            assert "motion" in result
            assert "reasoning" in result
            assert "response_text" in result
            mock_genai.GenerativeModel.assert_called_once() # 检查 Gemini 模型是否被调用
            mock_generative_model.generate_content_async.assert_called_once() #  检查 generate_content_async 是否被调用


@pytest.mark.asyncio
async def test_llm_response_generation_text_only(mock_genai_modules, mock_character_profile, mock_weaviate_client):
    """测试 llm_response_generation 函数，仅文本输入场景"""
    mock_genai, mock_generative_model, mock_generate_content_async, mock_generate_content_stream = mock_genai_modules
    mock_hybrid_query_results = MagicMock()
    mock_hybrid_query_results.objects = [] #  模拟长期记忆查询结果为空
    mock_weaviate_client[3].return_value = mock_hybrid_query_results #  设置 mock_hybrid 的返回值
    mock_generate_content_async.return_value = [AsyncMock(text='{"expression": "mock_expression", "motion": "mock_motion", "reasoning": "mock reasoning", "response_text": "mock response"}')] # 模拟 Gemini 返回

    user_input = "今天天气真好"
    user_id = "test_user_for_llm_gen"
    user_chat_sessions = {} #  可以传入一个空字典
    manual_history = [{"role": "user", "content": "你好"}] #  提供 manual_history

    response_dict = await llm_response_generation(user_input, user_id, user_chat_sessions, manual_history) #  传递 manual_history
    assert "expression" in response_dict
    assert "motion" in response_dict
    assert "reasoning" in response_dict
    assert "response_text" in response_dict


@pytest.mark.asyncio
async def test_llm_response_generation_with_image(mock_genai_modules, mock_character_profile, mock_weaviate_client):
    """测试 llm_response_generation 函数，包含图像输入场景"""
    mock_genai, mock_generative_model, mock_generate_content_async, mock_generate_content_stream = mock_genai_modules
    mock_hybrid_query_results = MagicMock()
    mock_hybrid_query_results.objects = [] #  模拟长期记忆查询结果为空
    mock_weaviate_client[3].return_value = mock_hybrid_query_results #  设置 mock_hybrid 的返回值
    mock_generate_content_async.return_value = [AsyncMock(text='{"expression": "mock_expression", "motion": "mock_motion", "reasoning": "mock reasoning", "response_text": "mock response"}')] # 模拟 Gemini 返回

    user_input = "看看这张照片"
    user_id = "test_user_image"
    user_chat_sessions = {} #  可以传入空字典
    manual_history = [{"role": "user", "content": "你好"}] #  提供 manual_history
    image_base64 = "mock_base64_image_data_for_llm"

    response_dict = await llm_response_generation(user_input, user_id, user_chat_sessions, manual_history, image_base64=image_base64) # 传递 manual_history 和 image_base64
    assert "expression" in response_dict
    assert "motion" in response_dict
    assert "reasoning" in response_dict
    assert "response_text" in response_dict
    mock_genai.GenerativeModel.assert_called_once() # 检查 Gemini 模型是否被调用
    mock_generative_model.generate_content_async.assert_called_once() #  检查 generate_content_async 是否被调用


# 可以继续添加更多的测试用例，例如错误处理、更复杂的对话历史场景等等