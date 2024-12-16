from elasticsearch import Elasticsearch
import ast
import re

# 创建 Elasticsearch 客户端连接，指定 scheme 为 http
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

index_name = 'nankai_url_final'

# 检查索引是否存在
if es.indices.exists(index=index_name):
    # 如果索引存在，删除旧的索引
    es.indices.delete(index=index_name)
    print(f"Deleted existing index: {index_name}")

# 定义新的索引映射（根据需要调整映射）
index_mapping = {
    "mappings": {
        "properties": {
            "url": {"type": "text"},
            "title": {"type": "text"},
            "anchor_text": {"type": "keyword"},
            "description": {"type": "text"},
            "pagerank": {"type": "float"}
        }
    }
}

# 创建新的索引
es.indices.create(index=index_name, body=index_mapping)
print(f"Created new index: {index_name}")

def load_and_deduplicate(file_path):
    """加载并去重数据"""
    data = []
    unique_urls = set()
    unique_titles = set()  # 用来存储已见过的标题

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # 修复多余的转义字符和错误的引号
            line = line.strip()

            # 移除多余的反斜杠，防止反斜杠对双引号的干扰
            line = re.sub(r'\\+', '', line)  # 移除所有反斜杠

            # 替换 np.float64(...) 为普通的浮点数格式
            line = re.sub(r'np\.float64\((.*?)\)', r'\1', line)

            # 修复标题中的未转义的双引号
            line = re.sub(r'"title":\s*"([^"]*)"', lambda m: '"title": "' + m.group(1).replace('"', '\\"') + '"', line)

            # 处理标题中的双引号，确保它们被转义
            line = line.replace('"It\'s', r'\"It\'s').replace('world."', 'world.\"')

            try:
                # 将格式化后的字符串转换为字典
                record = ast.literal_eval(line)  # 使用 literal_eval 安全地解析为字典

                url = record.get('url')
                title = record.get('title')

                if url and url not in unique_urls:
                    # 只有标题未出现过，才会添加
                    if title not in unique_titles:
                        unique_urls.add(url)
                        unique_titles.add(title)
                        data.append(record)
            except (ValueError, SyntaxError) as e:
                print(f"Failed to parse line: {line}\nError: {e}")

    return data


def index_data_to_elasticsearch(file_path):
    data = load_and_deduplicate(file_path)
    count = 0
    for record in data:
        # 限制锚文本数量为最多 5 个
        anchor_texts = record.get('anchor_text', [])[:5]

        doc = {
            "url": record.get('url', ''),
            "title": record.get('title', 'No Title'),
            "anchor_text": anchor_texts,
            "description": record.get('description', ''),
            "pagerank": record.get('page_rank', 0.0)
        }
        count += 1
        try:
            es.index(index=index_name, document=doc)
            print(f"Indexed: {count}{doc['url']}")
        except Exception as e:
            print(f"Failed to index {doc['url']}: {e}")


# 文件路径
txt_file = 'urls_with_data.txt'

# 将数据索引到 Elasticsearch
index_data_to_elasticsearch(txt_file)
