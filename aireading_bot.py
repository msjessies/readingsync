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

def fetch_readwise_data(time_limited=True):
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
    }
    
    # 如果启用时间限制，只获取一周内更新的文档
    if time_limited:
        article_params["updated__gt"] = get_one_week_ago()
        print(f"🕒 只获取 {get_one_week_ago()} 之后更新的文档")
    else:
        print("🕒 获取所有带标签的文档（无时间限制）")
    
    try:
        print("正在获取文章数据...")
        print(f"📡 API请求参数: {article_params}")
        resp = session.get("https://readwise.io/api/v3/list/", headers=headers, params=article_params)
        print(f"📡 API响应状态码: {resp.status_code}")
        
        # 打印响应内容以便调试
        if resp.status_code != 200:
            print(f"📡 API错误响应: {resp.text[:500]}")
        
        resp.raise_for_status()
        articles_data = resp.json()
        
        print(f"获取到 {len(articles_data['results'])} 篇文章")
        if articles_data['results']:
            print(f"📄 文章示例: {articles_data['results'][0].get('title', 'No title')}")
            # 添加调试信息：显示文章ID
            article_ids = [doc.get("id") for doc in articles_data['results'] if doc.get("id")]
            print(f"📄 文章ID前5个: {article_ids[:5]}")
        else:
            print("📄 未找到任何文章")
        
        # 2. 获取这些文章的所有高亮数据（不限时间）
        article_ids = [doc.get("id") for doc in articles_data['results'] if doc.get("id")]
        
        if not article_ids:
            print("没有有效的文章ID，跳过高亮获取")
            return articles_data, {"results": []}
        
        print(f"正在获取 {len(article_ids)} 篇文章的所有高亮数据...")
        highlight_params = {
            "category": "highlight",
            "page_size": 500,  # 高亮数据可能较多
            "parent_id__in": ",".join(str(id) for id in article_ids)  # 确保ID是字符串格式
        }
        
        print(f"📡 高亮API请求参数: {highlight_params}")
        resp = session.get("https://readwise.io/api/v3/list/", headers=headers, params=highlight_params)
        print(f"📡 高亮API响应状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"📡 高亮API错误响应: {resp.text[:500]}")
        
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
    # 添加调试信息：显示有高亮的文档ID
    if highlights_by_parent:
        print(f"📝 有高亮的文档ID前5个: {list(highlights_by_parent.keys())[:5]}")
    return highlights_by_parent

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
    
    # 调试信息：显示匹配情况
    if doc_highlights:
        print(f"✅ 文档 {doc.get('title', 'Unknown')[:50]}... 找到 {len(doc_highlights)} 条高亮")
    else:
        print(f"❌ 文档 {doc.get('title', 'Unknown')[:50]}... 未找到高亮 (ID: {doc_id})")
    
    # 将高亮格式化为markdown
    highlights_markdown = format_highlights_as_markdown(doc_highlights)
    
    # 过滤掉 ai101 标签，只显示其他有用的标签
    filtered_tags = [tag for tag in doc.get("tags", []) if tag.lower() != "ai101"]
    
    return {
        "文章标题Article": doc.get("title", ""),
        "分类Tags": filtered_tags,  # 飞书多选字段需要字符串数组，不是逗号分隔的字符串
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
    
    # 输出调试信息
    print(f"🔍 调试信息:")
    print(f"- 目标标签: {TARGET_TAG}")
    print(f"- READWISE_TOKEN 已配置: {'是' if READWISE_TOKEN else '否'}")
    print(f"- FEISHU_APP_ID 已配置: {'是' if APP_ID else '否'}")
    print(f"- FEISHU_APP_SECRET 已配置: {'是' if APP_SECRET else '否'}")
    print(f"- FEISHU_APP_TOKEN 已配置: {'是' if APP_TOKEN else '否'}")
    print(f"- FEISHU_TABLE_ID 已配置: {'是' if TABLE_ID else '否'}")
    print(f"- 查询时间范围: {get_one_week_ago()} 到现在")
    
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
    
    # 获取 Readwise 数据 - 先尝试所有数据（调试模式）
    print("正在获取 Readwise 数据...")
    data, highlights_data = fetch_readwise_data(time_limited=False)
    
    # 如果没有数据，再尝试一周内的数据（排查API问题）
    if not data["results"]:
        print("⚠️  没有找到任何带标签的文档，尝试限制时间范围...")
        data, highlights_data = fetch_readwise_data(time_limited=True)
    
    # 按文档ID归组高亮
    highlights_by_parent = group_highlights_by_parent(highlights_data)
    
    # 如果还是没有获取到数据，直接返回
    if not data["results"]:
        print("❌ 没有获取到任何数据，可能的原因：")
        print("  1. Readwise 中没有带有指定标签的文章")
        print("  2. Readwise API 调用失败")
        print("  3. 网络连接问题")
        print("💡 建议：")
        print("  - 检查 Readwise 中是否有带 'ai101' 标签的文章")
        print("  - 确认 READWISE_TOKEN 是否正确")
        print("  - 查看上面的API调用详细日志")
        return
    
    # 获取飞书 tenant_access_token
    print("正在获取飞书访问令牌...")
    tenant_token = get_tenant_access_token(APP_ID, APP_SECRET)
    if not tenant_token:
        print("❌ 无法获取飞书访问令牌，退出程序")
        return
    
    # 获取已存在记录的详细信息
    print("正在检查已存在的记录...")
    existing_records = get_existing_records(tenant_token, APP_TOKEN, TABLE_ID)
    print(f"发现 {len(existing_records)} 条已存在记录")
    
    # 分类处理：新增 vs 更新
    new_docs = []  # 新URL，需要插入
    update_docs = []  # 已存在URL，但highlight可能有更新
    skipped_count = 0
    
    # 临时调试：强制处理第一篇文章来测试高亮匹配
    debug_doc = data["results"][0] if data["results"] else None
    if debug_doc:
        print(f"🧪 调试模式：强制处理第一篇文章来测试高亮")
        debug_fields = build_feishu_fields(debug_doc, highlights_by_parent)
        print(f"🧪 调试结果: 高亮内容长度 = {len(debug_fields.get('高亮Highlight', ''))}")
    
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
            
            # 调试信息：显示高亮比较情况
            print(f"🔍 检查文档: {doc.get('title', 'Unknown')[:50]}...")
            print(f"    现有高亮长度: {len(existing_highlight)}")
            print(f"    新高亮长度: {len(new_highlight)}")
            
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


