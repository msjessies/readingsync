import requests
import os
from datetime import datetime, timedelta, timezone
import pytz

# 禁用代理设置，解决连接问题
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 配置从环境变量获取
READWISE_TOKEN = os.getenv("READWISE_TOKEN")
TARGET_TAG = os.getenv("TARGET_TAG", "ai101")  # 默认标签，也可以通过环境变量修改

def get_one_week_ago():
    """获取一周前的ISO 8601格式时间戳"""
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    return one_week_ago.strftime('%Y-%m-%dT%H:%M:%SZ')

def fetch_readwise_data():
    """从 Readwise API 获取文章数据和高亮数据"""
    # 创建不使用代理的session
    session = requests.Session()
    session.proxies = {}
    session.trust_env = False
    
    headers = {"Authorization": f"Token {READWISE_TOKEN}"}
    
    # 1. 获取带有指定标签的文章
    article_params = {
        "tag": TARGET_TAG, 
        "page_size": 100,
        "updated__gt": get_one_week_ago()  # 只获取一周内更新的文档
    }
    
    try:
        print("正在获取文章数据...")
        resp = session.get("https://readwise.io/api/v3/list/", headers=headers, params=article_params)
        resp.raise_for_status()
        articles_data = resp.json()
        
        print(f"获取到 {len(articles_data['results'])} 篇文章")
        
        # 2. 获取这些文章的所有高亮数据（不限时间）
        article_ids = [doc.get("id") for doc in articles_data['results'] if doc.get("id")]
        
        if not article_ids:
            print("没有有效的文章ID，跳过高亮获取")
            return articles_data, {"results": []}
        
        print(f"正在获取 {len(article_ids)} 篇文章的所有高亮数据...")
        highlight_params = {
            "category": "highlight",
            "page_size": 500,  # 高亮数据可能较多
            "parent_id__in": ",".join(article_ids)  # 只获取相关文章的高亮
        }
        
        resp = session.get("https://readwise.io/api/v3/list/", headers=headers, params=highlight_params)
        resp.raise_for_status()
        highlights_data = resp.json()
        
        print(f"获取到 {len(highlights_data['results'])} 条高亮")
        
        return articles_data, highlights_data
        
    except requests.exceptions.RequestException as e:
        print(f"获取 Readwise 数据失败: {e}")
        return {"results": []}, {"results": []}
    except Exception as e:
        print(f"数据处理失败: {e}")
        return {"results": []}, {"results": []}

# 获取数据
data, highlights_data = fetch_readwise_data()

def group_highlights_by_parent(highlights_data):
    """按 parent_id 归组高亮数据"""
    highlights_by_parent = {}
    
    for highlight in highlights_data.get("results", []):
        parent_id = highlight.get("parent_id")
        if parent_id:
            if parent_id not in highlights_by_parent:
                highlights_by_parent[parent_id] = []
            highlights_by_parent[parent_id].append(highlight)
    
    print(f"找到 {len(highlights_by_parent)} 个文档有相关高亮")
    return highlights_by_parent

# 按文档ID归组高亮
highlights_by_parent = group_highlights_by_parent(highlights_data)

def format_highlights_as_markdown(highlights_list):
    """将高亮列表格式化为markdown格式"""
    if not highlights_list:
        return ""
    
    markdown_lines = []
    for i, highlight in enumerate(highlights_list, 1):
        # 获取高亮文本
        text = highlight.get("text", "").strip()
        if text:
            # 使用markdown的引用格式
            markdown_lines.append(f"> {text}")
            
            # 如果有注释，添加注释
            note = highlight.get("note", "").strip()
            if note:
                markdown_lines.append(f"*注: {note}*")
            
            # 添加空行分隔（除了最后一个）
            if i < len(highlights_list):
                markdown_lines.append("")
    
    return "\n".join(markdown_lines)


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


def build_feishu_fields(doc, highlights_by_parent):
    """构建飞书表格字段，使用分离的高亮数据"""
    # 获取该文档的高亮数据
    doc_id = doc.get("id")
    doc_highlights = highlights_by_parent.get(doc_id, [])
    
    # 将高亮格式化为markdown
    highlights_markdown = format_highlights_as_markdown(doc_highlights)
    
    # 过滤掉 ai101 标签，只显示其他有用的标签
    filtered_tags = [tag for tag in doc.get("tags", []) if tag.lower() != "ai101"]
    
    return {
        "文章标题Article": doc.get("title", ""),
        "分类Tags": ', '.join(filtered_tags),
        "高亮Highlight": highlights_markdown,
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

def get_existing_records(token, app_token, table_id):
    """获取已存在记录的详细信息，用于去重和更新判断"""
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records'
    headers = {'Authorization': f'Bearer {token}'}
    params = {'page_size': 500}  # 获取更多记录来检查重复
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        result = resp.json()
        
        existing_records = {}  # URL -> {record_id, highlight, ...}
        if 'data' in result and 'items' in result['data']:
            for item in result['data']['items']:
                if 'fields' in item and 'URL' in item['fields']:
                    url = item['fields']['URL']
                    existing_records[url] = {
                        'record_id': item.get('record_id'),
                        'highlight': item['fields'].get('高亮Highlight', ''),
                        'title': item['fields'].get('文章标题Article', ''),
                    }
        
        return existing_records
    except Exception as e:
        print(f"获取已存在记录失败: {e}")
        return {}

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

def update_bitable_record(token, app_token, table_id, record_id, fields):
    """更新飞书多维表格中的指定记录"""
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {"fields": fields}
    
    try:
        resp = requests.put(url, headers=headers, json=payload)
        resp.raise_for_status()  # 检查HTTP状态码
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"飞书更新API调用失败: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"更新数据处理失败: {e}")
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
    
    # 获取已存在记录的详细信息
    print("正在检查已存在的记录...")
    existing_records = get_existing_records(tenant_token, APP_TOKEN, TABLE_ID)
    print(f"发现 {len(existing_records)} 条已存在记录")
    
    # 分类处理：新增 vs 更新
    new_docs = []  # 新URL，需要插入
    update_docs = []  # 已存在URL，但highlight可能有更新
    skipped_count = 0
    
    for doc in data["results"]:
        doc_url = doc.get("source_url", "")
        if not doc_url:
            continue
            
        if doc_url in existing_records:
            # 检查highlight是否有更新
            existing_record = existing_records[doc_url]
            # 获取该文档的新高亮数据
            doc_id = doc.get("id")
            doc_highlights = highlights_by_parent.get(doc_id, [])
            new_highlight = format_highlights_as_markdown(doc_highlights)
            existing_highlight = existing_record['highlight']
            
            if new_highlight != existing_highlight:
                print(f"🔄 发现highlight更新: {doc.get('title', 'Unknown')}")
                update_docs.append((doc, existing_record))
            else:
                skipped_count += 1
                print(f"⚠️  无变更，跳过: {doc.get('title', 'Unknown')}")
        else:
            print(f"✨ 发现新文档: {doc.get('title', 'Unknown')}")
            new_docs.append(doc)
    
    print(f"共 {len(data['results'])} 条记录: {len(new_docs)} 条新增，{len(update_docs)} 条需更新highlight，{skipped_count} 条无变更")
    
    if not new_docs and not update_docs:
        print("🎉 没有记录需要同步或更新！")
        return
    
    # 处理新增记录
    insert_success_count = 0
    if new_docs:
        print(f"\n📝 开始处理 {len(new_docs)} 条新增记录...")
        for doc in new_docs:
            feishu_fields = build_feishu_fields(doc, highlights_by_parent)
            print("新增内容：", feishu_fields)    # 可选：方便 debug
            result = insert_to_bitable(tenant_token, APP_TOKEN, TABLE_ID, feishu_fields)
            
            if "error" not in result:
                insert_success_count += 1
                print(f'✓ 新增[{feishu_fields["文章标题Article"]}] 成功')
            else:
                print(f'✗ 新增[{feishu_fields["文章标题Article"]}] 失败:', result)
    
    # 处理highlight更新记录
    update_success_count = 0
    if update_docs:
        print(f"\n🔄 开始处理 {len(update_docs)} 条highlight更新记录...")
        for doc, existing_record in update_docs:
            # 只更新highlight字段
            # 获取该文档的新高亮数据
            doc_id = doc.get("id")
            doc_highlights = highlights_by_parent.get(doc_id, [])
            new_highlight = format_highlights_as_markdown(doc_highlights)
            update_fields = {"高亮Highlight": new_highlight}
            
            print(f"更新highlight: {existing_record['title']}")
            result = update_bitable_record(tenant_token, APP_TOKEN, TABLE_ID, existing_record['record_id'], update_fields)
            
            if "error" not in result:
                update_success_count += 1
                print(f'✓ 更新[{existing_record["title"]}]的highlight 成功')
            else:
                print(f'✗ 更新[{existing_record["title"]}]的highlight 失败:', result)
    
    print(f"\n🎉 同步完成！")
    print(f"📊 结果统计:")
    print(f"   • 新增记录: {insert_success_count}/{len(new_docs)} 成功")
    print(f"   • 更新记录: {update_success_count}/{len(update_docs)} 成功")
    print(f"   • 无变更记录: {skipped_count} 条")
    print(f"   • 总共获取: {len(data['results'])} 条 (过去一周内更新)")


if __name__ == "__main__":
    main()


