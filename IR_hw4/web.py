from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from elasticsearch import Elasticsearch
import json
import os

# 创建 Flask 应用
app = Flask(__name__, template_folder=os.path.join(os.getcwd(), 'web'))  # 设置模板文件夹路径为 'web'

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
Session(app)

# 创建 Elasticsearch 客户端
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

# 用户账号密码（这里为了简单起见，直接在代码中写死）
users = {'admin': 'password123'}

# Elasticsearch 索引名称
index_name = 'test500_index'


def search(query):
    """通过查询字符串查询 Elasticsearch 索引"""
    query_body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title", "anchor_texts", "url"]
            }
        }
    }
    response = es.search(index=index_name, body=query_body)
    return response['hits']['hits']


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
        if users.get(username) == password:
            session['username'] = username
            return redirect(url_for('index'))  # 登录成功后跳转到主页
        else:
            return "Invalid credentials, please try again.", 401  # 登录失败提示

    return render_template('login.html')  # GET 请求时，显示登录页面


@app.route('/logout')
def logout():
    """登出功能"""
    session.pop('username', None)  # 清除会话
    return redirect(url_for('login'))  # 跳转回登录页面


@app.route('/search', methods=['GET', 'POST'])
def search_page():
    """搜索页面，显示检索结果"""
    if 'username' not in session:
        return redirect(url_for('login'))  # 如果用户未登录，跳转到登录页面

    if request.method == 'POST':
        query = request.form['query']
        results = search(query)  # 调用搜索函数进行检索
        return render_template('result.html', query=query, results=results)

    return render_template('search.html')  # 显示搜索框


if __name__ == '__main__':
    app.run(debug=True)
