import pandas as pd
import numpy as np
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity

# 计算文本嵌入
def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    embedding = outputs.last_hidden_state.mean(dim=1)  # 可以改为其他池化方式
    return embedding

UNIVS = ["上海交通大学", "清华大学", "北京大学", "浙江大学", "复旦大学", "西安交通大学", "哈尔滨工业大学", "南京大学"]

# 加载模型和对应的 tokenizer
model_name = "richinfoai/ritrieve_zh_v1"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

# 预定义类别
categories = ["学生生活类", "美景照片类", "节庆美食类", "艺术文化类", "运动健康类", "党政类", "招生类", "科技类", "教学类"]

# 获取类别嵌入，并将其转换为一个 2D 数组
category_embeddings = np.vstack([get_embedding(category).squeeze(0) for category in categories])

# 计算嵌入并分类
def classify_notes(df, univ):
    df['category'] = ''  # 添加一个新的列来存储分类结果
    total = df.shape[0]
    with tqdm(total=total, dynamic_ncols=True, desc=f"Classify for {univ}") as pbar:
        for index, row in df.iterrows():
            # 拼接标题和内容
            text = str(row['title']) + " " + str(row['content'])
            
            # 生成文本嵌入
            note_embedding = get_embedding(text).squeeze(0)  # 获取该笔记的嵌入并将其转换为 1D 数组
            
            # 计算文本与类别的相似性
            similarities = cosine_similarity([note_embedding], category_embeddings)  # 计算相似度
            most_similar_category = categories[np.argmax(similarities)]  # 找到最相似的类别
            
            # 填充分类结果
            df.at[index, 'category'] = most_similar_category
            
            pbar.update(1)
        
    return df
    
for univ in UNIVS:
    # 读取 CSV 文件
    file_path = f'output/{univ}_notes.csv'  # 请替换为实际的文件路径
    df = pd.read_csv(file_path)

    # 对笔记进行分类
    df_classified = classify_notes(df, univ)

    # 保存带分类结果的 CSV 文件
    output_file = f'output\{univ}_notes_class.csv'  # 请替换为实际的文件路径
    df_classified.to_csv(output_file, index=False, encoding='utf-8-sig')

