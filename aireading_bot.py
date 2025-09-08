import requests
import os
from datetime import datetime
import pytz

# 配置从环境变量获取
READWISE_TOKEN = os.getenv("READWISE_TOKEN")
TARGET_TAG = os.getenv("TARGET_TAG", "ai101")  # 默认标签，也可以通过环境变量修改

headers = {"Authorization": f"Token {READWISE_TOKEN}"}
params = {"tag": TARGET_TAG, "page_size": 100}   # 拉最多100条，可酌情调整

try:
    resp = requests.get("https://readwise.io/api/v3/list/", headers=headers, params=params)
    resp.raise_for_status()  # 检查HTTP状态码
    data = resp.json()
    
    print(f"命中的文档数量：{len(data['results'])}")
    for doc in data["results"][:2]:   # 打印前2条，核对格式
        print(doc["title"], doc.get("tags", []), doc.get("source_url", ""))
        
except requests.exceptions.RequestException as e:
    print(f"获取 Readwise 数据失败: {e}")
    data = {"results": []}
except Exception as e:
    print(f"数据处理失败: {e}")
    data = {"results": []}


def utc_to_beijing(utc_time_str):
    """将UTC时间字符串转换为北京时间"""
    if not utc_time_str:
        return ""
    try:
        # 解析UTC时间
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        # 转换为北京时间
        beijing_tz = pytz.timezone('Asia/Shanghai')
        
        beijing_time = utc_time.astimezone(beijing_tz)
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"时间转换失败: {e}")
        return utc_time_str


def build_feishu_fields(doc):
    highlights_text = "\n".join([h["text"] for h in doc.get("highlights", []) if h.get("text")])
    return {
        "文章标题Article": doc.get("title", ""),
        "分类Tags": ', '.join(doc.get("tags", [])),
        "高亮Highlight": highlights_text,
        "摘要Summary": doc.get("summary", ""),
        "URL": doc.get("source_url", ""),    # 原文url
        "加入时间UpdatedTime": utc_to_beijing(doc.get("updated", "") or doc.get("updated_at", ""))
    }

# 飞书应用配置 - 全部从环境变量获取
APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")
APP_TOKEN = os.getenv("FEISHU_APP_TOKEN")
TABLE_ID = os.getenv("FEISHU_TABLE_ID")

def get_tenant_access_token(app_id, app_secret):
    """获取飞书 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get("code") == 0:
            token = result.get("tenant_access_token")
            print(f"✓ 成功获取 tenant_access_token")
            return token
        else:
            print(f"✗ 获取 tenant_access_token 失败: {result}")
            return None
    except Exception as e:
        print(f"✗ 获取 tenant_access_token 异常: {e}")
        return None

def get_existing_urls(token, app_token, table_id):
    """获取已存在的URL列表，用于去重"""
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records'
    headers = {'Authorization': f'Bearer {token}'}
    params = {'page_size': 500}  # 获取更多记录来检查重复
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        result = resp.json()
        
        existing_urls = set()
        if 'data' in result and 'items' in result['data']:
            for item in result['data']['items']:
                if 'fields' in item and 'URL' in item['fields']:
                    existing_urls.add(item['fields']['URL'])
        
        return existing_urls
    except Exception as e:
        print(f"获取已存在URL失败: {e}")
        return set()

def insert_to_bitable(token, app_token, table_id, fields):
    """向飞书多维表格插入数据"""
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {"fields": fields}
    
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()  # 检查HTTP状态码
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"飞书API调用失败: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"数据处理失败: {e}")
        return {"error": str(e)}

def main():
    """主函数：执行完整的数据同步流程"""
    print("开始同步 Readwise Reader 数据到飞书...")
    
    # 检查必要的环境变量
    required_vars = {
        "READWISE_TOKEN": READWISE_TOKEN,
        "FEISHU_APP_ID": APP_ID,
        "FEISHU_APP_SECRET": APP_SECRET,
        "FEISHU_APP_TOKEN": APP_TOKEN,
        "FEISHU_TABLE_ID": TABLE_ID,
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        print(f"❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        print("请设置这些环境变量后重新运行程序")
        return
    
    # 获取飞书 tenant_access_token
    print("正在获取飞书访问令牌...")
    tenant_token = get_tenant_access_token(APP_ID, APP_SECRET)
    if not tenant_token:
        print("❌ 无法获取飞书访问令牌，退出程序")
        return
    
    # 如果没有获取到数据，直接返回
    if not data["results"]:
        print("没有获取到数据，退出程序")
        return
    
    # 获取已存在的URL用于去重
    print("正在检查已存在的记录...")
    existing_urls = get_existing_urls(tenant_token, APP_TOKEN, TABLE_ID)
    print(f"发现 {len(existing_urls)} 条已存在记录")
    
    # 过滤掉已存在的记录
    new_docs = []
    duplicate_count = 0
    for doc in data["results"]:
        doc_url = doc.get("source_url", "")
        if doc_url and doc_url in existing_urls:
            duplicate_count += 1
            print(f"⚠️  跳过重复记录: {doc.get('title', 'Unknown')}")
        else:
            new_docs.append(doc)
    
    print(f"共 {len(data['results'])} 条记录，跳过 {duplicate_count} 条重复，将同步 {len(new_docs)} 条新记录")
    
    if not new_docs:
        print("🎉 没有新记录需要同步！")
        return
    
    # 批量同步新记录
    success_count = 0
    for doc in new_docs:
        feishu_fields = build_feishu_fields(doc)
        print("写入内容：", feishu_fields)    # 可选：方便 debug
        result = insert_to_bitable(tenant_token, APP_TOKEN, TABLE_ID, feishu_fields)
        
        if "error" not in result:
            success_count += 1
            print(f'✓ 写入[{feishu_fields["文章标题Article"]}] 成功')
        else:
            print(f'✗ 写入[{feishu_fields["文章标题Article"]}] 失败:', result)
    
    print(f"\n🎉 同步完成！成功: {success_count}/{len(new_docs)} (总共获取: {len(data['results'])})")


if __name__ == "__main__":
    main()


