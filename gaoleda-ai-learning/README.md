# 高乐达的AI学习

> 探索人工智能前沿 · 交流 · 成长
> 一个可直接部署、可公开访问的 AI 学习社区（Streamlit + SQLite）

**线上地址**：见部署说明（由部署平台生成）

---

## 一、功能总览

| 模块 | 能力 |
|---|---|
| **用户系统** | 注册 / 登录 / 退出；注册总数上限 1000 人；仅需用户名 + 密码；密码必须**恰好 6 位阿拉伯数字**（逐项校验并给出明确提示）；用户名重复、密码格式不符、密码错误、名额已满均有独立提示；密码以 PBKDF2-HMAC-SHA256 + 每用户随机盐存储，不落明文 |
| **AI 新闻** | 聚合 6 个国际权威信源 RSS，并行抓取；只保留近一年内容并去重；30 分钟缓存 + 手动刷新；每条可**点进详情页**，详情页提供**外部原文链接**；信源全部不可达时自动回落到「近一年精选归档」，页面永不空白 |
| **讨论区** | 仅注册用户可发言；话题分类与筛选；**互相点赞**（可取消）、**互相关注**（可取消）；显示点赞人数、我的关注 / 粉丝；活跃用户榜；只能删除自己的发言 |
| **文件区** | 从本地选择文件上传（支持多选）、说明备注、关键词搜索、在线下载、删除自己的文件；扩展名白名单 + 单文件 20MB 上限；**uuid 重命名落盘**，杜绝路径穿越 |
| **个人中心** | 个人简介、修改密码、我的发言 / 我的文件、获赞数、关注 / 粉丝列表 |
| **视觉** | 深空蓝黑底 + 靛紫→青渐变、玻璃拟态卡片、极光流动背景、卡片入场上浮、悬停光晕；桌面 / 移动端自适应（侧边栏桌面展开、移动收起） |

## 二、项目结构

```
gaoleda-ai-learning/
├── app.py                  # 入口：路由 + 全局侧边栏 + 可选独立启动
├── requirements.txt        # 唯一依赖：streamlit
├── .streamlit/config.toml  # 主题与服务器配置
├── core/                   # 纯 Python 业务逻辑（不 import streamlit，可离线单测）
│   ├── config.py           #   常量与路径（支持 GAOLEDA_DATA_DIR 环境变量重定向）
│   ├── storage.py          #   SQLite 持久化层（WAL + 进程写锁）
│   ├── auth.py             #   用户系统
│   ├── news.py             #   AI 新闻（RSS 聚合 / 缓存 / 兜底）
│   ├── discussion.py       #   讨论区（帖 / 赞 / 关注）
│   └── files.py            #   文件区
├── views/                  # 页面渲染函数（只调 core，不直接读写库）
│   ├── home.py / news.py / forum.py / files.py / account.py
├── ui/                     # 主题 CSS 与可复用组件（全部输出经 html.escape）
├── tests/test_core.py      # 44 项单元测试
├── scripts/
│   ├── smoke_test.py       # Streamlit AppTest：11 个页面渲染用例
│   ├── flow_test.py        # 主链路功能测试（真实点按钮）
│   └── _page_runner.py     # 冒烟测试用单页入口
├── run.bat / run.sh        # 一键启动（自动建 venv）
└── data/                   # 运行时数据（自动创建，已 gitignore）
```

**分层铁律**：`core/` 不依赖 UI 框架 → 同一套业务逻辑可复用于桌面版、API 版，且能离线测试。

## 三、本地运行

```bash
# 方式一：一键脚本（推荐，自动创建 .venv）
#   Windows: 双击 run.bat
#   macOS / Linux / WSL: bash run.sh

# 方式二：手动
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
python app.py                     # 或 streamlit run app.py
```

浏览器打开 <http://localhost:8501>。

> `python app.py` 会自动读取 `PORT` 环境变量并绑定 `0.0.0.0`，
> 因此同一条命令既适合本地也适合容器 / 托管平台。

## 四、部署上线

### 方式 A：一键发布（当前已采用）

WorkBuddy「发布为应用」：把项目目录作为单端口 HTTP 服务发布，
自动完成上传、依赖安装、`PORT` 注入与启动，返回公开访问链接。

### 方式 B：Streamlit Community Cloud（免费）

1. 推送到 GitHub（`data/` 已在 `.gitignore` 中，不会上传用户数据）
2. 打开 <https://share.streamlit.io> → 用 GitHub 登录 → **New app**
3. 选仓库 / `main` 分支 / 主文件 `app.py` → **Deploy**
4. 1–3 分钟后得到 `https://<应用名>.streamlit.app`

### 方式 C：自带服务器

```bash
pip install -r requirements.txt
PORT=8000 python app.py          # 再用 Nginx 反代 8000 端口即可
```

Nginx 反代需开启 WebSocket 支持：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;      # 关键：Streamlit 依赖 WebSocket
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
}
```

## 五、测试与验收

```bash
python -m unittest discover -s tests -v   # 44 项单元测试
python scripts/smoke_test.py              # 11 个页面渲染用例
python scripts/flow_test.py               # 注册→登录→发帖→点赞→上传 主链路
```

## 六、运维须知

- **⚠️ 数据存放在 `data/`（SQLite + 上传文件）。** 托管平台用临时文件系统时，
  **重新发布 / 重建容器都会把 `data/` 清空**——用户、帖子、上传文件会全部丢失
  （本站当前即属此类，验收时已实测两次发布后数据归零）。
  需要真正持久化时：把平台提供的持久磁盘路径通过环境变量
  `GAOLEDA_DATA_DIR` 指过去即可，代码无需改动；或改用带持久卷的平台（Render Disk / Railway Volume）。
- **默认演示账号**：`demo` / `123456`（发布后自动创建，含一条示例发言；数据重置后需重建）。
- 新闻每 30 分钟自动刷新；也可在新闻页点「刷新新闻」强制重抓。
- 上传文件有类型白名单与 20MB 上限，可在 `core/config.py` 调整。
- 用户上限 1000、密码 6 位数字等规则集中在 `core/config.py`，改一处全局生效。

## 七、版本

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0.0 | 2026-10-10 | 首个公开版本：用户系统、AI 新闻、讨论区、文件区、个人中心、完整测试与部署说明 |
