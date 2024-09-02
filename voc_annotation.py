import os
import random

# 文件夹路径，请替换为你实际的文件夹路径
folder_path = 'data2/steps'
files = [os.path.splitext(os.path.basename(f))[0] for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.endswith('.step')]

# 打乱文件顺序以确保随机性
random.shuffle(files)

# 按照8:2比例分割文件名列表
split_index = int(len(files) * 0.8)
train_files = files[:split_index]
test_files = files[split_index:]

# 分别保存到两个txt文件
def save_to_txt(file_list, filename):
    with open(filename, 'w') as f:
        for item in file_list:
            f.write("%s\n" % item)

train_filename = 'train_filenames.txt'
test_filename = 'test_filenames.txt'

save_to_txt(train_files, train_filename)
save_to_txt(test_files, test_filename)

print(f"Training filenames saved to {train_filename}")
print(f"Testing filenames saved to {test_filename}")