from elasticsearch import Elasticsearch
import json

# 创建 Elasticsearch 客户端连接，指定 scheme 为 http
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

# 为 URL 和 PageRank 创建索引（如果不存在）
index_name = 'test500_index'
if not es.indices.exists(index=index_name):
    es.indices.create(
        index=index_name,
        body={
            "mappings": {
                "properties": {
                    "url": {"type": "keyword"},  # URL 存储为 keyword 类型
                    "pagerank": {"type": "float"},  # PageRank 存储为 float 类型
                    "title": {"type": "text"},  # Title 存储为 text 类型
                    "anchor_texts": {
                        "type": "keyword"  # 锚文本存储为 keyword 类型
                    }
                }
            }
        }
    )


def load_urls_and_pageranks(url_file, pagerank_file):
    """从文件中加载 URL 和对应的 PageRank"""
    # 读取 URL 文件
    with open(url_file, 'r', encoding='utf-8') as f:
        urls = f.readlines()

    # 读取 PageRank 文件
    with open(pagerank_file, 'r', encoding='utf-8') as f:
        pageranks = f.readlines()

    # 使用字典将 URL 和对应的 PageRank 进行配对
    url_pagerank_dict = {}
    for line in pageranks:
        # 解析每一行 PageRank 文件
        parts = line.split(', PageRank: ')
        url = parts[0].replace('URL: ', '').strip()
        pagerank = float(parts[1].strip())
        url_pagerank_dict[url] = pagerank

    # 返回 URL 列表和 URL-Pagerank 字典
    return urls, url_pagerank_dict


def index_data_to_elasticsearch_from_file():
    """从文件加载 URL、title 和 Anchor Texts，并将其索引到 Elasticsearch"""
    with open("urls_with_content.txt", 'r', encoding='utf-8') as f:
        content = f.read().split("\n\n")  # 按照 URL 进行分隔

    for entry in content:
        lines = entry.split("\n")

        # 跳过格式不正确的条目
        if len(lines) < 3:
            print(f"Skipping malformed entry: {entry}")
            continue

        # 获取 URL, Title, 和 Anchor Texts
        url = lines[0].replace('URL: ', '').strip()
        title = lines[1].replace('Title: ', '').strip() if len(lines) > 1 else 'No Title'
        anchor_texts = lines[2].replace('Anchor Texts: ', '').strip().split(", ") if len(lines) > 2 else []

        # 从 URL-Pagerank 字典中获取 PageRank
        pagerank = url_pagerank_dict.get(url, 0)  # 默认为0，如果没有找到对应的 PageRank

        # 构建文档
        doc = {
            "url": url,
            "title": title,
            "anchor_texts": anchor_texts,  # 锚文本存储为数组
            "pagerank": pagerank  # 使用从 pagerank_results.txt 获取的 PageRank
        }

        # 将文档索引到 Elasticsearch
        es.index(index=index_name, document=doc)
        print(f"Indexed: {url}")


# 文件路径
url_file = 'urls.txt'  # URL 文件路径
pagerank_file = 'pagerank_results.txt'  # PageRank 文件路径

# 加载数据
urls, url_pagerank_dict = load_urls_and_pageranks(url_file, pagerank_file)

# 将数据索引到 Elasticsearch
index_data_to_elasticsearch_from_file()
