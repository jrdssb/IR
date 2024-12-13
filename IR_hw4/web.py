from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from elasticsearch import Elasticsearch
import json
import re
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


from PIL import Image
if not os.path.exists('html_snapshots'):
    os.makedirs('html_snapshots')

if not os.path.exists('screenshot_snapshots'):
    os.makedirs('screenshot_snapshots')

# 创建 history 文件夹（如果不存在）
if not os.path.exists('history'):
    os.makedirs('history')

# 创建 Flask 应用
app = Flask(__name__, template_folder=os.path.join(os.getcwd(), 'web'))

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
Session(app)

# 创建 Elasticsearch 客户端
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

# 用户账户密码存储路径
users_file = 'users.json'


def compute_cosine_similarity(query, document):
    """计算查询词与文档的余弦相似度"""
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([query, document])
    cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return cosine_sim[0][0]



def load_users():
    """加载用户数据"""
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            return json.load(f)
    return {}


def save_users(users):
    """保存用户数据"""
    with open(users_file, 'w') as f:
        json.dump(users, f)


def clean_url(url):
    """去除 URL 中的数字前缀"""
    # 使用正则表达式去除前缀数字和点
    cleaned_url = re.sub(r'^\d+\.', '', url)
    return cleaned_url


# Elasticsearch 索引名称
index_name = 'nankai_url'


def search(query, username=None, use_wildcard=False):
    """进行搜索并考虑历史记录和PageRank进行个性化排序"""
    # Step 1: 原始查询，得到初步搜索结果
    if use_wildcard:
        query_body = {
            "query": {
                "wildcard": {
                    "title": {
                        "value": query
                    }
                }
            }
        }
    else:
        query_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "title^3",  # 给标题更高的权重
                        "description^2",  # 给描述适中的权重
                        "anchor_texts^2",  # 给 anchor_texts 权重
                        "page_rank^1",  # 给 page_rank 最低的权重
                        "url^1"  # 可选的，给 URL 加上权重
                    ]
                }
            }
        }

    # 执行查询
    response = es.search(index=index_name, body=query_body)
    hits = response['hits']['hits']

    # Step 2: 获取用户历史记录
    user_history = get_search_history(username) if username else []

    # Step 3: 计算历史记录的余弦相似度
    historical_similarities = []
    for hit in hits:
        title = hit['_source'].get('title', '').strip()
        similarity = 0
        for history_item in user_history:
            similarity += compute_cosine_similarity(history_item.strip(), title)
        historical_similarities.append(similarity)

    # Step 4: 计算查询词与结果的余弦相似度
    query_similarities = []
    for hit in hits:
        title = hit['_source'].get('title', '').strip()
        query_similarities.append(compute_cosine_similarity(query, title))

    # Step 5: 获取PageRank
    pageranks = [hit['_source'].get('page_rank', 0) for hit in hits]

    # Step 6: 归一化所有得分
    def normalize(scores):
        min_score = min(scores)
        max_score = max(scores)
        return [(score - min_score) / (max_score - min_score) if max_score != min_score else 0 for score in scores]

    historical_similarities = normalize(historical_similarities)
    query_similarities = normalize(query_similarities)
    pageranks = normalize(pageranks)

    # Step 7: 加权综合评分
    weighted_scores = []
    weight_history = 0.6
    weight_query = 0.2
    weight_pagerank = 0.2

    for i in range(len(hits)):
        score = (weight_history * historical_similarities[i] +
                 weight_query * query_similarities[i] +
                 weight_pagerank * pageranks[i])
        weighted_scores.append(score)

    # Step 8: 对每个结果的 URL 进行处理
    for hit in hits:
        url = hit['_source'].get('url', '').strip()
        cleaned_url = clean_url(url)
        hit['_source']['url'] = cleaned_url  # 更新 URL 为去除前缀后的版本

    # 去重：根据标题去重
    seen_titles = set()
    unique_hits = []
    for hit in hits:
        title = hit['_source'].get('title', '').strip()
        if title not in seen_titles:
            seen_titles.add(title)
            unique_hits.append(hit)

    # 之后的代码使用 unique_hits 代替 hits
    hits = unique_hits

    # Step 8: 根据综合得分进行排序
    # 对结果按照 weighted_scores 排序
    sorted_results = [hit for _, hit in sorted(zip(weighted_scores, hits), key=lambda x: x[0], reverse=True)]

    return sorted_results




def save_html_snapshot(url, filename):
    """保存网页的 HTML 快照"""
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return True
    return False


def save_screenshot_snapshot(url, filename):
    """使用 Selenium 截图保存网页快照"""
    options = Options()
    options.headless = True  # 设置无头模式
    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # 等待页面加载完成后截屏
    driver.save_screenshot(filename)
    driver.quit()
    return True


def save_search_history(username, query):
    """保存用户的查询历史"""
    history_file = f'history/{username}.txt'
    # 读取现有历史记录
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = f.readlines()
    else:
        history = []

    # 将最新查询添加到历史记录
    history.append(query + '\n')


    # 保存历史记录，使用 UTF-8 编码
    with open(history_file, 'w', encoding='utf-8') as f:
        f.writelines(history)


def get_search_history(username):
    """获取用户的查询历史（最多 5 条）"""
    history_file = f'history/{username}.txt'
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = f.readlines()
        return history[-5:]  # 返回最近的 5 条
    return []


@app.route('/')
def index():
    """显示主页（搜索框和登录链接）"""
    if 'username' in session:
        return render_template('search.html')  # 如果用户已登录，显示搜索页面
    return redirect(url_for('login'))  # 否则跳转到登录页面


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()  # 加载用户数据
        if users.get(username) == password:
            session['username'] = username
            # 登录成功后，加载用户的查询历史
            recent_searches = get_search_history(username)
            return render_template('search.html', recent_searches=recent_searches)  # 显示历史记录
        else:
            return "Invalid credentials, please try again.", 401  # 登录失败提示

    return render_template('login.html')  # GET 请求时，显示登录页面


@app.route('/logout')
def logout():
    """登出功能"""
    session.pop('username', None)  # 清除会话
    return redirect(url_for('login'))  # 跳转回登录页面


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()  # 加载现有用户
        if username in users:
            return "Username already exists, please choose another one.", 400  # 用户名已存在
        users[username] = password  # 添加新用户
        save_users(users)  # 保存到文件
        return redirect(url_for('login'))  # 注册成功后跳转到登录页面

    return render_template('register.html')  # 显示注册页面


def get_personalized_recommendations(username, query, search_results):
    """获取个性化推荐，基于用户历史查询，并去除已显示的搜索结果"""
    user_history = get_search_history(username)  # 获取用户历史查询

    # 将当前查询与历史查询记录结合起来，作为新的查询
    combined_query = query + ' ' + ' '.join(user_history)  # 合并当前查询与历史查询

    # 在 Elasticsearch 中进行搜索，获取推荐内容
    query_body = {
        "query": {
            "multi_match": {
                "query": combined_query,
                "fields": [
                    "title^3",  # 给标题更高的权重
                    "description^2",  # 给描述适中的权重
                    "anchor_texts^2",  # 给 anchor_texts 权重
                    "url^1"  # 给 URL 加上权重
                ]
            }
        }
    }

    # 执行查询
    response = es.search(index=index_name, body=query_body)
    hits = response['hits']['hits']

    # 将搜索结果的 URLs 提取出来，便于后续去重
    search_result_urls = {hit['_source'].get('url', '') for hit in search_results}

    # 过滤掉已经出现在搜索结果中的推荐项
    recommended_results = []
    for hit in hits[:5]:  # 取前 5 个相关结果
        url = hit['_source'].get('url', '')
        if url not in search_result_urls:  # 如果推荐的 URL 不在搜索结果中
            recommended_results.append({
                'title': hit['_source'].get('title', ''),
                'url': url,
                'description': hit['_source'].get('description', ''),
            })

    return recommended_results


@app.route('/search', methods=['GET', 'POST'])
def search_page():
    """搜索页面，显示检索结果和个性化推荐"""
    if 'username' not in session:
        return redirect(url_for('login'))  # 如果用户未登录，跳转到登录页面

    username = session['username']
    recent_searches = get_search_history(username)  # 获取最近的查询记录

    if request.method == 'POST':
        query = request.form['query']
        use_wildcard = 'wildcard' in request.form  # 检查是否勾选了通配符查询
        search_results = search(query, username=username, use_wildcard=use_wildcard)  # 调用搜索函数进行检索

        # 保存查询历史
        save_search_history(username, query)

        # 获取个性化推荐，基于用户历史查询和当前查询，排除搜索结果中已显示的内容
        recommended_results = get_personalized_recommendations(username, query, search_results)

        return render_template('result.html', query=query, results=search_results, recent_searches=recent_searches, recommended_results=recommended_results)

    return render_template('search.html', recent_searches=recent_searches)  # 显示搜索框并展示查询历史



@app.route('/snapshot', methods=['GET', 'POST'])
def snapshot():
    """网页快照功能"""
    if 'username' not in session:
        return redirect(url_for('login'))  # 如果用户未登录，跳转到登录页面

    if request.method == 'POST':
        url = request.form['url']
        snapshot_type = request.form['snapshot_type']

        if snapshot_type == 'html':
            filename = f"html_snapshots/{url.split('//')[1].replace('/', '_')}.html"
            success = save_html_snapshot(url, filename)
            message = "HTML snapshot saved successfully!" if success else "Failed to save HTML snapshot."

        elif snapshot_type == 'screenshot':
            filename = f"screenshot_snapshots/{url.split('//')[1].replace('/', '_')}.png"
            success = save_screenshot_snapshot(url, filename)
            message = "Screenshot snapshot saved successfully!" if success else "Failed to save screenshot snapshot."

        return render_template('snapshot_result.html', message=message, url=url)

    return render_template('snapshot.html')  # 网页快照页面


if __name__ == '__main__':
    app.run(debug=True)
