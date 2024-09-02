import os
import json

# 文件夹路径，假设所有JSON文件都在此文件夹内
folder_path = 'data3/labels'
destination_folder = 'data3/relabel'
os.makedirs(destination_folder, exist_ok=True)

# 遍历文件夹中的所有文件
for filename in os.listdir(folder_path):
    if filename.endswith('.json'):  # 确保只处理JSON文件
        file_path = os.path.join(folder_path, filename)
        output_path = os.path.join(destination_folder, filename)
        
        # 步骤1: 读取单个JSON文件
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        new_list = [2 if x == 26 else 3 if x == 25 else 4 if x == 1 else 0 for x in data]

        if new_list.count(2) == 5:
            if new_list[len(new_list)-4] == 2:
                new_list[len(new_list)-4] = 1

        if new_list.count(2) == 10:
            if new_list[len(new_list)-4] == 2:
                new_list[len(new_list)-4] = 1
            if new_list[len(new_list)-9] == 2:
                new_list[len(new_list)-9] = 1
        if new_list.count(2) == 15:
            if new_list[len(new_list)-4] == 2:
                new_list[len(new_list)-4] = 1
            if new_list[len(new_list)-9] == 2:
                new_list[len(new_list)-9] = 1
            if new_list[len(new_list)-14] == 2:
                new_list[len(new_list)-14] = 1
                


        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(new_list, file, ensure_ascii=False, indent=4)
print('完结')



