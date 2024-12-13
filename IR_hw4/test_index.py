from elasticsearch import Elasticsearch
import re

# 创建 Elasticsearch 客户端连接，指定 scheme 为 http
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

# 为 URL 和 PageRank 创建索引（如果不存在）
index_name = 'nankai_url'

def verify_index(index_name):
    """验证索引中的文档数量"""
    try:
        # 获取文档总数
        count = es.count(index=index_name)["count"]
        print(f"Total documents in index '{index_name}': {count}")

        # 检索一些文档进行查看
        res = es.search(index=index_name, body={"query": {"match_all": {}}, "size": 5})
        for hit in res["hits"]["hits"]:
            print(f"Document: {hit['_source']}")
    except Exception as e:
        print(f"Error while verifying index: {e}")

# 验证索引数据
verify_index(index_name)
