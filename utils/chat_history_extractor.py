import json

def get_user_interaction_data_from_dict(user_id, raw_data):
    """
    根据用户ID从给定的字典格式的原始数据中获取用户输入和响应的数据集。

    Args:
    user_id: 要查询的用户ID。
    raw_data: 一个字典，键是用户ID，值是该用户的交互记录列表。
              每个交互记录是一个包含 'timestamp', 'user_id', 'user_text', 'ai_response' 键的字典。

    Returns:
    一个包含字典的列表，每个字典包含 'user_input' 和 'response' 键，
    对应于给定用户的交互记录。如果用户ID不存在于 raw_data 中，则返回一个空列表。
    """
    user_data = []
    if user_id in raw_data:
        interactions = raw_data[user_id]
        for interaction in interactions:
            user_data.append({
            "user_input": interaction.get('user_text'),
            "response": interaction.get('ai_response')
            })

    return user_data

def get_user_interaction_data_from_single_user(raw_data):
    """
    根据用户ID从给定的字典格式的原始数据中获取用户输入和响应的数据集。

    Args:
    user_id: 要查询的用户ID。
    raw_data: 一个字典，键是用户ID，值是该用户的交互记录列表。
              每个交互记录是一个包含 'timestamp', 'user_id', 'user_text', 'ai_response' 键的字典。

    Returns:
    一个包含字典的列表，每个字典包含 'user_input' 和 'response' 键，
    对应于给定用户的交互记录。如果用户ID不存在于 raw_data 中，则返回一个空列表。
    """
    user_data = []
    interactions = raw_data
    for interaction in interactions:
        user_data.append({
            "user_input": interaction.get('user_text'),
            "response": interaction.get('ai_response')
            })

    return user_data

#with open(r"Experiments data\long_term_memory\participant_1.json", 'r', encoding='utf-8') as f:
#      raw_data = json.load(f)

#user_id_to_find = "艾利克斯"
#user_dataset = get_user_interaction_data_from_single_user(raw_data)
#print(user_dataset)
