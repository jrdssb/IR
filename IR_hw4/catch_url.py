import requests
import networkx as nx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import tldextract  # 用于提取域名
import chardet  # 用于自动检测网页编码
import concurrent.futures

# 全局变量
g = nx.DiGraph()
urllist = {}
visited = set()
url_queue = []
max_urls = 100000
url_file = "urls.txt"


# 全局变量
batch_data = []
batch_size = 10  # 每批次保存的 URL 数量


def check_url_status(url):
    """检查URL的状态码，判断是否为 404"""
    try:
        response = requests.get(url, timeout=5)  # 设置超时时间为5秒
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.RequestException as e:
        return True


def check_nankai(url):
    """检查URL的域名是否包含'nankai'，如果不包含则跳过"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc  # 获取完整的域名（包括子域名）

    if "nankai" not in domain:
        return False
    return True


def extract_links(html, base_url):
    """提取网页中的所有链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for tag in soup.find_all('a', href=True):
        href = tag.get('href')
        if href.startswith('#') or "javascript:" in href or not href:
            continue
        if not href.startswith('http'):
            if href.startswith('/'):
                href = base_url + href
            else:
                href = base_url + '/' + href
        links.append(href)
    return links



def save_url_with_content(url, title, html):
    """保存URL、title和HTML内容到文件"""
    with open("urls_with_content.txt", 'a', encoding='utf-8') as f:
        f.write(f"URL: {url}\nTitle: {title}\nHTML: {html}\n\n")


def extract_anchor_texts(html):
    """提取网页中的所有锚文本"""
    soup = BeautifulSoup(html, 'html.parser')
    anchor_texts = []
    for tag in soup.find_all('a', href=True):
        anchor_texts.append(tag.get_text(strip=True))
    return anchor_texts


def save_pagerank(pagerank):
    """保存PageRank结果到文件"""
    with open("pagerank_results.txt", 'w', encoding='utf-8') as f:
        for node, rank in pagerank.items():
            f.write(f"URL: {node}, PageRank: {rank}\n")
    print("PageRank results saved to pagerank_results.txt.")


def batch_save_data(batch_data):
    """批量保存数据"""
    with open("urls_with_content.txt", 'a', encoding='utf-8') as f:
        for data in batch_data:
            f.write(f"URL: {data['url']}\nTitle: {data['title']}\nAnchor Texts: {', '.join(data['anchor_texts'])}\n\n")
    print(f"Saved {len(batch_data)} URLs.")


def crawl_urls(start_url):
    """同步爬取网页并构建图，同时提取锚文本和title"""
    global urllist, visited, url_queue, batch_data

    while len(urllist) < max_urls and url_queue:
        url = url_queue.pop(0)

        if url in visited or url not in urllist or not check_nankai(url):
            continue

        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue
            raw_html = response.content
            detected_encoding = chardet.detect(raw_html)
            encoding = detected_encoding.get('encoding', 'utf-8')
            html = raw_html.decode(encoding, errors='ignore')

            # 提取网页的title
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string if soup.title else 'No Title'

            # 提取网页中的所有锚文本
            anchor_texts = extract_anchor_texts(html)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue

        visited.add(url)

        # 将数据存储到 batch_data 中
        batch_data.append({
            'url': url,
            'title': title,
            'anchor_texts': anchor_texts
        })

        # 当存储的数据量达到批次大小时，保存并清空 batch_data
        if len(batch_data) >= batch_size:
            batch_save_data(batch_data)
            batch_data.clear()  # 清空列表，准备存储下一批数据

        # 提取链接
        links = extract_links(html, url)
        if url not in g:
            g.add_node(url)

        for link in links:
            is_useful_link = check_url_status(link) and check_nankai(url)
            if link not in visited and is_useful_link:
                url_queue.append(link)
                if link not in urllist:
                    urllist[link] = 0

            # 添加边到图
            if link not in g:
                g.add_node(link)
            g.add_edge(url, link)

    # 计算 PageRank
    pagerank = nx.pagerank(g, alpha=0.85)
    save_pagerank(pagerank)

    # 最后保存剩余的数据（即便它们是叶节点，确保保存）
    if batch_data:
        batch_save_data(batch_data)

    # **强制处理队列中剩余的 URL**，确保它们的标题和锚文本被保存
    while url_queue:
        url = url_queue.pop(0)
        if url not in visited:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    continue
                raw_html = response.content
                detected_encoding = chardet.detect(raw_html)
                encoding = detected_encoding.get('encoding', 'utf-8')
                html = raw_html.decode(encoding, errors='ignore')

                # 提取网页的title
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.string if soup.title else 'No Title'

                # 提取网页中的所有锚文本
                anchor_texts = extract_anchor_texts(html)
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                continue

            visited.add(url)

            # 将数据存储到 batch_data 中
            batch_data.append({
                'url': url,
                'title': title,
                'anchor_texts': anchor_texts
            })

            # 保存数据
            if batch_data:
                batch_save_data(batch_data)
                batch_data.clear()  # 清空列表，准备存储下一批数据


def start_crawl(start_url):
    """启动爬虫"""
    urllist[start_url] = 0
    url_queue.append(start_url)
    crawl_urls(start_url)


def main():
    start_url = "https://www.nankai.edu.cn"  # 起始URL，替换为实际URL
    start_crawl(start_url)

    # 等待爬取完成，计算PageRank
    print(f"Total URLs crawled: {len(visited)}")
    print("Crawl Completed.")


if __name__ == "__main__":
    main()
