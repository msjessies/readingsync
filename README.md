# AI Reading List 自动同步工具

自动从 Readwise Reader 同步带有 "ai101" 标签的文章到飞书多维表格。

## 功能特性

- ✅ 自动获取 Readwise Reader 中标记为 "ai101" 的文章
- ✅ 提取文章标题、标签、高亮、摘要、URL、更新时间等字段
- ✅ 自动同步到飞书多维表格
- ✅ 去重功能，避免重复导入
- ✅ 每天凌晨3点自动运行 (北京时间)
- ✅ 环境变量保护敏感信息

## GitHub Actions 部署配置

### 1. 推送代码到 GitHub

```bash
# 初始化 git 仓库 (如果还没有)
git init
git add .
git commit -m "Initial commit: AI reading list sync tool"

# 添加远程仓库并推送
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

### 2. 设置 GitHub Secrets

在你的 GitHub 仓库中，进入 **Settings** → **Secrets and variables** → **Actions**，添加以下 Secrets：

| Secret 名称 | 值 | 说明 |
|------------|----|----|
| `READWISE_TOKEN` | `你的Readwise令牌` | 从 Readwise 设置页面获取 |
| `FEISHU_APP_ID` | `cli_a8342101b9e81013` | 飞书应用ID |
| `FEISHU_APP_SECRET` | `NEvihgdxiNX65LEstosgCd7msCBw6TIY` | 飞书应用密钥 |
| `FEISHU_APP_TOKEN` | `APcrbuGUealLe9sdW8DcZBtCnse` | 飞书多维表格应用令牌 |
| `FEISHU_TABLE_ID` | `tblUdRDj28uIPVfG` | 飞书表格ID |

### 3. 设置 Variables (可选)

在 **Variables** 标签页可以设置：

| Variable 名称 | 值 | 说明 |
|--------------|----|----|
| `TARGET_TAG` | `ai101` | 要同步的标签 (默认为 ai101) |

### 4. 手动触发测试

设置完成后，可以在 **Actions** 页面手动触发 "Daily Readwise to Feishu Sync" 工作流来测试配置是否正确。

## 本地开发和测试

### 环境设置

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 环境变量配置

创建 `.env` 文件 (不要提交到 git)：

```bash
READWISE_TOKEN=你的Readwise令牌
TARGET_TAG=ai101
FEISHU_APP_ID=cli_a8342101b9e81013
FEISHU_APP_SECRET=NEvihgdxiNX65LEstosgCd7msCBw6TIY
FEISHU_APP_TOKEN=APcrbuGUealLe9sdW8DcZBtCnse
FEISHU_TABLE_ID=tblUdRDj28uIPVfG
```

### 运行测试

```bash
# 设置环境变量 (临时)
export READWISE_TOKEN="你的令牌"
export FEISHU_APP_ID="cli_a8342101b9e81013"
# ... 设置其他环境变量

# 运行同步脚本
python aireading_bot.py
```

## 定时任务说明

- 每天北京时间凌晨 3:00 自动运行
- GitHub Actions 免费账户每月有 2000 分钟额度
- 每次运行大约消耗 1-2 分钟，足够日常使用

## 故障排除

1. **检查 GitHub Secrets** - 确保所有必要的 Secrets 都已正确设置
2. **查看 Actions 日志** - 在 GitHub Actions 页面查看详细的运行日志
3. **手动触发测试** - 使用 workflow_dispatch 手动运行工作流进行调试

## 字段映射

| 飞书字段 | Readwise 字段 | 说明 |
|---------|--------------|------|
| 文章标题Article | title | 文章标题 |
| 分类Tags | tags | 标签 (逗号分隔) |
| 高亮Highlight | highlights | 高亮内容 (换行分隔) |
| 摘要Summary | summary | 文章摘要 |
| URL | source_url | 原文链接 |
| 加入时间UpdatedTime | updated | 更新时间 (转换为北京时间) |