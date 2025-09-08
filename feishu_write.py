import requests

# ==== 配置区域（用你的实际参数替换下面的内容） ====
# tenant_access_token 刚刚已经通过接口获取，无需再用 app_id、app_secret
TENANT_TOKEN = "t-g10498hEGT5BA2Q7NRQOPFXZUYC4AAF6QX652PP2"      # 例如 "xxxxxyyyyzzz..."
APP_TOKEN = "APcrbuGUealLe9sdW8DcZBtCnse"     # 你的 BaseId
TABLE_ID = "tblUdRDj28uIPVfG"                 # 你的 table_id

# ==== 写入数据配置 ====
# 这里的字段，必须和你的多维表格表头【名字一模一样】（比如A、单选、日期等）
record_data = {
    "文章标题Article": "Claude 自动",       # 假设你的第一个字段叫A
    "分类Tags": "选项A",                # 假设有个单选字段
    "高亮Highlight": "2025-09-08",    
    "总结Summary": "12345",   
    "URL": "www.45.cn",
           # 假设有个日期字段
    # 你可以继续添加其他列字段
}

# ==== 写入请求逻辑 ====
url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"

headers = {
    "Authorization": f"Bearer {TENANT_TOKEN}",
    "Content-Type": "application/json"
}

payload = {
    "fields": record_data
}

response = requests.post(url, headers=headers, json=payload)
print("返回结果：", response.json())

import requests

READWISE_TOKEN = "4MeKKMerFuUTxT3TITazdkRcltD4uFfnUYu4RVKNX9dHQJ87zG"
TARGET_TAG = "AI101" 

headers = {
    "Authorization": f"Token {READWISE_TOKEN}"
}

params = {
    "tag": TARGET_TAG
    # 还可添加 category/updatedAfter 等参数
}

resp = requests.get(
    "https://readwise.io/api/v3/list/",
    headers=headers,
    params=params
)
data = resp.json()
print("你指定标签的文档数量：", len(data["results"]))
for doc in data["results"]:
    print(doc["title"], doc["tags"])


import requests
READWISE_TOKEN = "4MeKKMerFuUTxT3TITazdkRcltD4uFfnUYu4RVKNX9dHQJ87zG"
TARGET_TAG = "AI101"  # eg: "AI", "必读", "重要"
headers = {"Authorization": f"Token {READWISE_TOKEN}"}

params = {
    "tag": TARGET_TAG,
    "category": "articles"     # 只获取 article 类型文档
}
resp = requests.get(
    "https://readwise.io/api/v3/list/",
    headers=headers,
    params=params
)
data = resp.json()
print("你指定标签+文章类型的文档数量：", len(data["results"]))
for doc in data["results"]:
    print(doc["title"], doc["tags"])


import requests

READWISE_TOKEN = "4MeKKMerFuUTxT3TITazdkRcltD4uFfnUYu4RVKNX9dHQJ87zG"
headers = {"Authorization": f"Token {READWISE_TOKEN}"}

resp = requests.get("https://readwise.io/api/v3/list/", headers=headers)
data = resp.json()

for doc in data["results"]:
    print(doc.get("title"), doc.get("category"), doc.get("tags"))

import requests

READWISE_TOKEN = "4MeKKMerFuUTxT3TITazdkRcltD4uFfnUYu4RVKNX9dHQJ87zG"
headers = {"Authorization": f"Token {READWISE_TOKEN}"}

params = {
    "tag": "AI101",           # 替换为你真实标签名，严格区分大小写与空格
    # 可选，加上 category（如只查 articles 类型）
    # 如想只查文章文档类型，不要则注释掉本行
}



# 你之前配置好的函数和参数
def insert_to_bitable(token, app_token, table_id, fields):
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {"fields": fields}
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()

# 配置你的 token/app_token/table_id
TENANT_TOKEN = "t-g10498hEGT5BA2Q7NRQOPFXZUYC4AAF6QX652PP2"
APP_TOKEN = "APcrbuGUealLe9sdW8DcZBtCnse"
TABLE_ID = "tblUdRDj28uIPVfG"

# 批量写入每个文档
for doc in data["results"]:
    feishu_fields = build_feishu_fields(doc)
    result = insert_to_bitable(TENANT_TOKEN, APP_TOKEN, TABLE_ID, feishu_fields)
    print(f'写入[{feishu_fields["文章标题Article"]}] 结果:', result)



def build_feishu_fields(doc):
    highlights_text = "\n".join([h["text"] for h in doc.get("highlights", []) if h.get("text")])
    return {
        "文章标题Article": doc.get("title", ""),
        "分类Tags": ', '.join(doc.get("tags", [])),
        "高亮Highlight": highlights_text,
        "摘要Summary": doc.get("summary", ""),
        "URL": doc.get("source_url", ""),
        "加入时间Updated Time": doc.get("updated", "")   # 或 "updated_at"、"created"，具体以API返回为准
    }
