from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from elasticsearch import Elasticsearch
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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


# Elasticsearch 索引名称
index_name = 'nankai'


def search(query, use_wildcard=False):
    """通过查询字符串查询 Elasticsearch 索引"""
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
    return response['hits']['hits']


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

    # 保留最多 5 条历史记录
    history = history[-5:]

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


@app.route('/search', methods=['GET', 'POST'])
def search_page():
    """搜索页面，显示检索结果"""
    if 'username' not in session:
        return redirect(url_for('login'))  # 如果用户未登录，跳转到登录页面

    username = session['username']
    recent_searches = get_search_history(username)  # 获取最近的查询记录

    if request.method == 'POST':
        query = request.form['query']
        use_wildcard = 'wildcard' in request.form  # 检查是否勾选了通配符查询
        results = search(query, use_wildcard)  # 调用搜索函数进行检索

        # 保存查询历史
        save_search_history(username, query)

        return render_template('result.html', query=query, results=results, recent_searches=recent_searches)

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
