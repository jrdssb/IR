import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
import time
import os


def extract_links(html, base_url):
    """从网页中提取所有链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    exclude_extensions = {'.pdf', '.doc', '.mp4', '.zip', '.rar', '.docx', '.xlsx', '.xls'}

    for tag in soup.find_all('a', href=True):
        href = tag.get('href')
        if href.startswith('#') or "javascript:" in href or not href:
            continue
        href = urljoin(base_url, href)
        parsed_url = urlparse(href)
        if not parsed_url.scheme or not parsed_url.netloc:
            continue
        _, ext = os.path.splitext(parsed_url.path)
        if ext.lower() in exclude_extensions:
            continue
        cleaned_url = urlunparse(parsed_url._replace(query="", fragment=""))
        links.append(cleaned_url)
    return links


def fetch_page_data(url, index):
    """从指定的URL提取页面数据，包括title, description, and anchor_text"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None

        # 采用UTF-8解码
        html = response.content.decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')

        # 获取标题
        title = soup.title.string if soup.title else ""

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
            "url": f"{index}. {url}",  # 在URL前添加数字索引
            "anchor_text": anchor_text,
            "title": title.strip(),
            "description": description.strip(),
            "page_rank": 0  # PageRank值默认设置为0，稍后可修改
        }
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def process_urls_from_file(input_file):
    """批量读取urls_with_pagerank.txt文件中的URL并提取数据"""
    url_data = {}
    batch_size = 100  # 每批次处理100个URL
    current_index = 1  # 当前URL的编号

    with open(input_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()

        for i in range(0, len(lines), batch_size):
            batch_lines = lines[i:i + batch_size]
            for line in batch_lines:
                url, pagerank = line.strip().split('\t')
                print(f"Processing {current_index}: {url}...")
                data = fetch_page_data(url, current_index)
                if data:
                    data["page_rank"] = float(pagerank)
                    url_data[url] = data
                current_index += 1  # 更新当前URL的编号
            save_results_to_file(url_data, 'urls_data.json')  # 每处理100行就保存一次
            url_data.clear()  # 清空已保存的数据
            time.sleep(1)  # 给服务器一个小的延时，避免过快请求

    return url_data


def save_results_to_file(url_data, output_file):
    """将提取的数据保存为格式化的JSON-like格式"""
    with open(output_file, 'a', encoding='utf-8') as file:
        for url, data in url_data.items():
            file.write(f"{url}: {{\n")
            file.write(f'    "url": "{data["url"]}",\n')
            file.write(f'    "anchor_text": {data["anchor_text"]},\n')
            file.write(f'    "title": "{data["title"]}",\n')
            file.write(f'    "description": "{data["description"]}",\n')
            file.write(f'    "page_rank": {data["page_rank"]}\n')
            file.write("},\n")


# 使用示例
input_file = 'urls_with_pagerank.txt'
output_file = 'urls_data.json'

# 清空输出文件，避免数据追加时混乱
with open(output_file, 'w', encoding='utf-8') as file:
    file.write('')

url_data = process_urls_from_file(input_file)
print(f"数据已保存到 {output_file}")
