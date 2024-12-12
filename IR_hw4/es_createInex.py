#1.需要去重

from elasticsearch import Elasticsearch
import re

# 创建 Elasticsearch 客户端连接，指定 scheme 为 http
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

# 为 URL 和 PageRank 创建索引（如果不存在）
index_name = 'nankai'
if not es.indices.exists(index=index_name):
    es.indices.create(
        index=index_name,
        body={
            "mappings": {
                "properties": {
                    "url": {"type": "keyword"},  # URL 存储为 keyword 类型
                    "pagerank": {"type": "float"},  # PageRank 存储为 float 类型
                    "title": {"type": "text"},  # Title 存储为 text 类型
                    "anchor_text": {"type": "keyword"},  # 锚文本存储为 keyword 类型
                    "description": {"type": "text"}  # 描述存储为 text 类型
                }
            }
        }
    )

def parse_non_standard_json(file_path):
    """解析非标准 JSON 格式的文件"""
    data = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用正则提取每个 URL 数据块
    blocks = re.findall(r'(https?://[\w\./:]+):\s*\{(.*?)\},?\n', content, re.DOTALL)
    for url, attributes_raw in blocks:
        attributes = {}
        # 按行解析属性
        for attr in attributes_raw.split(',\n'):
            key_value = re.match(r'^\s*(\w+):\s*(.+)$', attr.strip())
            if key_value:
                key = key_value.group(1).strip()
                value = key_value.group(2).strip()

                # 去掉字符串值的引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith('[') and value.endswith(']'):
                    value = [v.strip('"') for v in value[1:-1].split(',')]
                elif value.replace('.', '', 1).isdigit():
                    value = float(value) if '.' in value else int(value)

                attributes[key] = value

        data[url] = attributes
    return data

def index_data_to_elasticsearch(file_path):
    """从非标准 JSON 文件加载数据并将其索引到 Elasticsearch"""
    data = parse_non_standard_json(file_path)

    for url, attributes in data.items():
        # 限制只保存前 5 个锚文本
        anchor_texts = attributes.get('anchor_text', [])[:5]

        # 构建文档
        doc = {
            "url": attributes.get('url', url),
            "title": attributes.get('title', 'No Title'),
            "anchor_text": anchor_texts,
            "description": attributes.get('description', ''),
            "pagerank": attributes.get('page_rank', 0.0)
        }

        # 将文档索引到 Elasticsearch
        try:
            es.index(index=index_name, document=doc)
            print(f"Indexed: {doc['url']}")
        except Exception as e:
            print(f"Failed to index {url}: {e}")

# 文件路径
json_file = 'urls_data.json'

# 将数据索引到 Elasticsearch
index_data_to_elasticsearch(json_file)
