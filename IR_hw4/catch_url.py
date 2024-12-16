import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
import time
import os
import re
from scipy.sparse import csr_matrix
import numpy as np

# 全局变量
url_queue = []  # 待爬取的 URL 队列
visited = set()  # 已访问的 URL 集合
nankai_urls = []  # 符合条件的 URL 数据列表
adj_list = {}  # 用于 PageRank 计算的邻接表
max_urls = 100000  # 最大 URL 爬取数量限制

def check_nankai(url):
    """检查 URL 的域名是否包含 'nankai'"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    return "nankai" in domain

def fetch_page_data(url, index):
    """从指定的 URL 提取页面数据，包括 title, description, 和 anchor_text"""
    try:
        response = requests.get(url, timeout=1)
        if response.status_code != 200:
            return None

        # 采用 UTF-8 解码
        html = response.content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')

        # 获取标题
        title = soup.title.string.strip() if soup.title else ""

        # 获取描述
        description = ""
        meta_desc = soup.find('meta', attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            description = meta_desc.get("content").strip()

        # 获取前五个锚文本
        anchor_text = []
        for tag in soup.find_all('a', href=True):
            text = tag.get_text(strip=True)
            if text:
                anchor_text.append(text)
                if len(anchor_text) >= 5:  # 只保存前五个
                    break

        return {
            "url": url,
            "anchor_text": anchor_text,
            "title": title,
            "description": description,
            "page_rank": 0  # PageRank 值默认设置为 0，稍后可修改
        }
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_links(html, base_url):
    """从网页中提取所有链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    for tag in soup.find_all('a', href=True):
        href = tag.get('href')
        if href.startswith('#') or "javascript:" in href or not href:
            continue
        href = urljoin(base_url, href)  # 将相对链接转换为绝对链接
        parsed_url = urlparse(href)
        if not parsed_url.scheme or not parsed_url.netloc:  # 检查 URL 是否具备基本格式
            continue
        # 清理 URL，去除查询和片段
        cleaned_url = urlunparse(parsed_url._replace(query="", fragment=""))
        text = tag.get_text(strip=True)
        links.append((cleaned_url, text))
    return links

def crawl_urls(start_url):
    """爬取域名中包含 'nankai' 的 URL"""
    global url_queue, visited, nankai_urls, adj_list

    url_queue.append(start_url)

    while url_queue and len(nankai_urls) < max_urls:
        url = url_queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            # 发送 GET 请求获取页面内容
            response = requests.get(url, timeout=1)
            if response.status_code != 200:
                continue

            raw_html = response.content
            html = raw_html.decode('utf-8', errors='ignore')

            # 提取所有链接并分类
            links = extract_links(html, url)
            download_links = []  # 存储下载链接
            page_links = []  # 存储页面链接

            # 分类链接为下载链接和页面链接
            for link, anchor in links:
                content_type = response.headers.get('Content-Type', '').lower()
                if any(ext in link for ext in ['pdf', 'zip', 'doc', 'excel', 'mp4']):
                    download_links.append((link, anchor))
                else:
                    page_links.append((link, anchor))

            # 处理下载链接
            for download_link, anchor in download_links:
                nankai_urls.append({
                    "url": download_link,
                    "anchor_text": [anchor],
                    "title": anchor or "Download Link",
                    "description": "",
                    "page_rank": 0
                })
                print(f"[GET] Add download URL: {len(nankai_urls)} {download_link}")

            # 处理页面链接
            adj_list[url] = [link for link, _ in page_links]  # 仅存储页面链接用于 PageRank
            for link, _ in page_links:
                if link not in visited and check_nankai(link):
                    url_queue.append(link)

            # 提取页面数据
            page_data = fetch_page_data(url, len(nankai_urls) + 1)
            if page_data:
                nankai_urls.append(page_data)
                print(f"[GET] Add URL: {len(nankai_urls)} {url}")

        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue

    print(f"Total nankai URLs collected: {len(nankai_urls)}")
    return nankai_urls

def calculate_pagerank_sparse(adj_list, damping=0.85, max_iterations=100, tol=1.0e-6):
    """使用稀疏矩阵优化 PageRank 计算"""
    nodes = list(adj_list.keys())
    num_nodes = len(nodes)
    node_index = {node: i for i, node in enumerate(nodes)}

    row, col, data = [], [], []
    for node, links in adj_list.items():
        node_idx = node_index[node]
        for link in links:
            if link in node_index:
                row.append(node_index[link])
                col.append(node_idx)
                data.append(1)

    M = csr_matrix((data, (row, col)), shape=(num_nodes, num_nodes))
    out_degree = np.array(M.sum(axis=0)).flatten()
    out_degree[out_degree == 0] = 1
    M = M.multiply(1 / out_degree)

    rank = np.ones(num_nodes) / num_nodes

    for iteration in range(max_iterations):
        new_rank = (1 - damping) / num_nodes + damping * M.dot(rank)
        if np.linalg.norm(new_rank - rank, 1) < tol:
            break
        rank = new_rank

    return {nodes[i]: rank[i] for i in range(num_nodes)}

def cu():
    start_time = time.time()
    start_url = "https://www.nankai.edu.cn"
    nankai_urls_data = crawl_urls(start_url)

    pagerank_scores = calculate_pagerank_sparse(adj_list)

    for entry in nankai_urls_data:
        entry["page_rank"] = pagerank_scores.get(entry["url"], 0)

    with open("urls_with_data.txt", "w", encoding="utf-8") as f:
        for entry in nankai_urls_data:
            f.write(f"{entry}\n")

    print(f"Crawling and PageRank computation completed in {time.time() - start_time:.2f} seconds.")


cu()