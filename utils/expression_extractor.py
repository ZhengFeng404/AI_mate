import os

folder_path = "C:/Users/fengz/Downloads/魔法少女猫猫/魔法少女猫猫/模型文件/长发猫猫/expressions"  # 将这里替换为您的实际文件夹路径
file_names_list = []

try:
    for filename in os.listdir(folder_path):
        if filename.endswith(".exp3.json"):
            base_name = filename[:-len(".exp3.json")]
            file_names_list.append(base_name)

    print(file_names_list)

except FileNotFoundError:
    print(f"错误：指定的文件夹路径 '{folder_path}' 不存在。")
except Exception as e:
    print(f"发生错误：{e}")