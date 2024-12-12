import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
import chardet
import time
import os
import re

# 全局变量
url_queue = []  # 待爬取的URL队列
visited = set()  # 已访问的URL集合
nankai_urls = set()  # 符合条件的URL集合
adj_list = {}  # 用于PageRank计算的邻接表
max_urls = 100000 # 最大URL爬取数量限制


def check_nankai(url):
    """检查URL的域名是否包含'nankai'"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc  # 获取域名
    return "nankai" in domain


# def extract_links(html, base_url):
#     """从网页中提取所有链接"""
#     soup = BeautifulSoup(html, 'html.parser')
#     links = []
#     for tag in soup.find_all('a', href=True):
#         href = tag.get('href')  # 获取<a>标签的href属性
#         if href.startswith('#') or "javascript:" in href or not href:
#             continue
#         href = urljoin(base_url, href)  # 将相对链接转换为绝对链接
#         parsed_url = urlparse(href)
#         if not parsed_url.scheme or not parsed_url.netloc:  # 检查url是否具备基本格式
#             continue
#         parsed_url = urlparse(href)
#         cleaned_url = urlunparse(parsed_url._replace(query="", fragment=""))  # 去除查询与参数
#         links.append(cleaned_url)
#     return links
def extract_links(html, base_url):
    """从网页中提取所有链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    # 设置不保存的文件后缀
    exclude_extensions = {'.pdf', '.doc', '.mp4', '.zip', '.rar', '.docx', '.xlsx', '.xls'}

    for tag in soup.find_all('a', href=True):
        href = tag.get('href')  # 获取<a>标签的href属性
        if href.startswith('#') or "javascript:" in href or not href:
            continue
        href = urljoin(base_url, href)  # 将相对链接转换为绝对链接
        parsed_url = urlparse(href)
        if not parsed_url.scheme or not parsed_url.netloc:  # 检查url是否具备基本格式
            continue
        # 获取文件后缀并检查是否在排除列表中
        _, ext = os.path.splitext(parsed_url.path)
        if ext.lower() in exclude_extensions:
            continue
        # 清理URL，去除查询和片段
        cleaned_url = urlunparse(parsed_url._replace(query="", fragment=""))
        links.append(cleaned_url)
    return links



def crawl_urls(start_url):
    """爬取域名中包含'nankai'的URL"""
    global url_queue, visited, nankai_urls, adj_list

    # 初始化队列
    url_queue.append(start_url)

    while url_queue and len(nankai_urls) < max_urls:
        url = url_queue.pop(0)  # 从队列中取出一个URL

        if url in visited:
            continue
        visited.add(url)

        if not check_nankai(url):  # 检查URL是否符合条件
            continue

        try:
            # 发送HTTP请求
            response = requests.get(url, timeout=1)
            if response.status_code != 200:
                continue

            raw_html = response.content  # 获取网页内容

            # 尝试直接使用utf-8解码，如果解码失败，跳过当前URL
            try:
                html = raw_html.decode('utf-8')  # 直接使用utf-8解码
            except UnicodeDecodeError:
                print(f"Error decoding {url} with utf-8, skipping.")
                continue  # 解码失败，跳过当前URL

            # 提取链接并添加到队列
            links = extract_links(html, url)
            adj_list[url] = links  # 构建邻接表
            for link in links:
                if link not in visited and check_nankai(link):
                    url_queue.append(link)

            nankai_urls.add(url)  # 保存符合条件的URL
            print(f"add url: {len(nankai_urls)} {url}")

        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue

    print(f"Total nankai URLs collected: {len(nankai_urls)}")
    return nankai_urls



import numpy as np


from scipy.sparse import csr_matrix


def calculate_pagerank_sparse(adj_list, damping=0.85, max_iterations=20, tol=1.0e-6):
    """使用稀疏矩阵优化PageRank计算"""
    from scipy.sparse import csr_matrix
    import numpy as np

    nodes = list(adj_list.keys())  # 获取所有节点
    num_nodes = len(nodes)
    node_index = {node: i for i, node in enumerate(nodes)}  # 节点索引映射

    # 构建稀疏矩阵
    row, col, data = [], [], []
    for node, links in adj_list.items():
        node_idx = node_index[node]
        for link in links:
            if link in node_index:  # 忽略未在邻接表中的链接
                row.append(node_index[link])
                col.append(node_idx)
                data.append(1)
    print(f"构造稀疏矩阵完成")
    # 转换为稀疏矩阵
    M = csr_matrix((data, (row, col)), shape=(num_nodes, num_nodes))
    out_degree = np.array(M.sum(axis=0)).flatten()  # 出度数组
    out_degree[out_degree == 0] = 1  # 防止除零
    M = M.multiply(1 / out_degree)  # 转换为概率转移矩阵

    # 初始化PageRank
    rank = np.ones(num_nodes) / num_nodes

    # 迭代计算
    print("开始PageRank计算...")
    for iteration in range(1, max_iterations + 1):
        new_rank = (1 - damping) / num_nodes + damping * M.dot(rank)
        diff = np.linalg.norm(new_rank - rank, 1)

        # 输出当前迭代进度和L1范数变化
        print(f"第 {iteration} 次迭代: L1 范数差异 = {diff:.6e}")

        if diff < tol:
            print(f"在第 {iteration} 次迭代后收敛。")
            break
        rank = new_rank

    else:
        print("达到最大迭代次数，但未完全收敛。")

    return {node: rank[node_index[node]] for node in nodes}


def main():
    start_time = time.time()
    start_url = "https://www.nankai.edu.cn"  # 起始URL
    nankai_urls = crawl_urls(start_url)

    # 计算PageRank分数
    pagerank_scores = calculate_pagerank_sparse(adj_list)

    # 保存到文件
    with open("urls_with_pagerank.txt", "w", encoding="utf-8") as f:
        for url, score in sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True):
            f.write(f"{url}\t{score:.6f}\n")

    print(f"URL采集和PageRank计算完成，共耗时 {time.time() - start_time:.2f} 秒。")
    print("结果已保存到 'urls_with_pagerank.txt' 文件。")


if __name__ == "__main__":
    main()
