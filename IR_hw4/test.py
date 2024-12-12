import requests

# 要访问的 URL
url = "http://www.nankai.edu.cn/"

# 发送 GET 请求
response = requests.get(url)

# 检查响应状态码是否为 200（即请求成功）
if response.status_code == 200:
    # 获取 HTML 内容
    html_content = response.text
    print(html_content)  # 打印出网页的 HTML 内容
else:
    print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
