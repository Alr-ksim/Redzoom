import pandas as pd

# 读取分类好的 CSV 文件
file_path = 'output\浙江大学_notes_class.csv'  # 请替换为实际的文件路径
df = pd.read_csv(file_path)

# 统计每一列的总数
total_likes = df['like_count'].sum()
total_collects = df['collect_count'].sum()
total_shares = df['share_count'].sum()
total_comments = df['comment_count'].sum()

# 统计笔记总数
total_notes = len(df)

# 统计各个分类的数量
categories = ["学生生活类", "美景照片类", "节庆美食类", "艺术文化类", "运动健康类", "党政类", "招生类", "科技类", "教学类"]
category_counts = {category: df['category'].value_counts().get(category, 0) for category in categories}

# 统计笔记类型：视频笔记和图文笔记
video_notes = df[df['type'] == 'video'].shape[0]
text_image_notes = df[df['type'] == 'normal'].shape[0]

# 输出统计结果
statistics = {
    '获赞总数': total_likes,
    '收藏总数': total_collects,
    '转发总数': total_shares,
    '评论总数': total_comments,
    '笔记总数': total_notes,
    '学生生活类': category_counts['学生生活类'],
    '节庆美食类': category_counts['节庆美食类'],  # 假设“节庆美食类”对应的是“美景宣传类”
    '科技成果类': category_counts['科技类'],  # 假设“科技成果类”对应的是“科技科研类”
    '美景照片类': category_counts['美景照片类'],  # 假设“美景照片类”对应的是“美景宣传类”
    '艺术文化类': category_counts['艺术文化类'],
    '运动健康类': category_counts['运动健康类'],
    '招生类': category_counts['招生类'],
    '教学类': category_counts['教学类'],
    '党政类': category_counts['党政类'],
    '视频笔记': video_notes,
    '图文笔记': text_image_notes
}

# 转换为 DataFrame 以便展示或保存
stats_df = pd.DataFrame(statistics, index=[0])

# 保存统计结果到新的 CSV 文件
stats_df.to_csv('output/统计结果.csv', index=False, encoding='utf-8-sig')

# 显示统计结果
print(stats_df)
