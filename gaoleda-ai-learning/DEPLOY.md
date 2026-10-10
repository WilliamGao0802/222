# 「学习AI with William Gao」部署上线指南

> 本文回答五件事：**准备哪些文件 → 入口脚本怎么配 → 依赖怎么写 → 选哪种部署方式 → 启动命令与上线后排查**。
> 面向结果：一条命令拉起服务，一个公网网址对外访问。

---

## 0. 当前上线状态

| 项目 | 值 |
|---|---|
| 平台 A（WorkBuddy 发布为应用） | `https://gaoleda-ai-learning-73899.app.workbuddy.host/` |
| 平台 B（Streamlit Community Cloud） | 仓库 `WilliamGao0802/222`，主文件 `app.py` |
| 首页响应 | `HTTP 200` |
| 健康检查 | `GET /_stcore/health` → `ok` |
| 部署方式 | WorkBuddy「发布为应用」（方式 A） |
| 启动命令 | `python app.py` |

---

## 1. 需要准备哪些文件

### 1.1 最小必需集（缺一不可）

| 路径 | 作用 | 说明 |
|---|---|---|
| `app.py` | **入口脚本** | 平台启动的起点，负责页面路由与全局侧边栏 |
| `requirements.txt` | **依赖清单** | 平台据此安装环境 |
| `.streamlit/config.toml` | **主题 + 服务器配置** | 端口/地址/上传大小/XSRF 等 |
| `core/` | 业务逻辑层 | 含 `config.py` `storage.py` `auth.py` `news.py` `discussion.py` `files.py` + `__init__.py` |
| `views/` | 页面渲染层 | `home/news/forum/files/account.py` + `__init__.py` |
| `ui/` | 主题与组件 | `theme.py` `components.py` + `__init__.py` |

> ⚠️ **三个包目录里的 `__init__.py` 必须存在**（哪怕空文件）。缺了它，云端会出现 `ModuleNotFoundError: No module named 'core'` —— 这是 Streamlit 部署最常见的翻车点。

### 1.2 不必上传的（但建议保留在仓库里）

| 路径 | 原因 |
|---|---|
| `tests/` `scripts/` | 本地测试与验收脚本，运行时用不到 |
| `data/` | **运行时自动生成**（SQLite + 上传文件），已被 `.gitignore` 排除，**切勿把真实用户数据提交到公开仓库** |
| `.venv/` `__pycache__/` | 本地环境与字节码缓存，同样已忽略 |

### 1.3 建议一并提供的（可选但省事）

| 文件 | 作用 |
|---|---|
| `run.bat` / `run.sh` | 一键启动脚本：自动建 venv → 装依赖 → 起服务 |
| `README.md` | 功能说明与本地运行方法 |
| `DEPLOY.md` | 本文，部署与运维手册 |
| `.gitattributes` | 强制 `*.sh` 用 LF 换行，避免 Linux 容器里 `bash\r` 报错 |

---

## 2. 入口脚本（`app.py`）怎么配

本项目入口做了**双重兼容**，同一份代码两种启动方式都能跑：

```
streamlit run app.py     ← 标准方式
python app.py            ← 平台/容器方式（自动读 PORT 环境变量）
```

关键设计点：

**① 防递归自启动**
`_should_bootstrap()` 用三重信号判断「是否已经处在 Streamlit 运行时里」，避免 `python app.py` 无限套娃启动：

```python
def _should_bootstrap() -> bool:
    if os.environ.get("GAOLEDA_BOOTSTRAPPED") == "1":   # ① 引导标记
        return False
    if "streamlit" in " ".join(sys.argv[:3]).lower():   # ② 命令行含 streamlit
        return False
    from streamlit.runtime import exists as _runtime_exists
    if _runtime_exists():                               # ③ 运行时已存在
        return False
    return True
```

**② 直接读 `PORT`，不依赖 shell 变量展开**
很多托管平台只给一条启动命令，且不保证经过 shell。因此在代码里读 `os.environ["PORT"]` 比写 `--server.port=$PORT` 更可靠：

```python
sys.argv = ["streamlit", "run", os.path.abspath(__file__),
            "--server.port", str(os.environ.get("PORT", "8501")),
            "--server.address", "0.0.0.0",       # 必须 0.0.0.0，否则容器外访问不到
            "--server.headless", "true",
            "--server.fileWatcherType", "none",  # 云端关掉文件监视，省资源
            "--browser.gatherUsageStats", "false"]
```

**③ `st.set_page_config()` 必须最先调用**
它必须是第一个 Streamlit 命令，否则会抛 `set_page_config() can only be called once`。

**④ 多页用 `st.navigation` + `st.Page`**
比旧的 `pages/` 目录约定更可控，路由路径（`url_path`）可直接作为对外 URL。

---

## 3. 依赖（`requirements.txt`）怎么配

整个项目**只有一行依赖**：

```text
streamlit>=1.37,<2.0
```

原因：其余全部是 **Python 标准库**，无需声明。实测全项目 import 汇总：

```
__future__ concurrent contextlib datetime email functools hashlib hmac html
json os pathlib re secrets shutil sqlite3 sys tempfile threading time typing
urllib uuid xml
```

> 这些是 Pillow / pandas / feedparser / requests 一律用不上的清爽架构。

配置要点：

| 要点 | 说明 |
|---|---|
| **加下界 `>=1.37`** | 项目用了 `st.navigation` / `st.Page`，低于 1.37 不存在该 API |
| **加下界 `<2.0`** | 锁住大版本，避免上游 breaking change 把线上打挂 |
| **不要写死补丁号** | 例如 `==1.37.1` 会卡住安全更新；上界 + 下界足够稳 |
| **不要装 `feedparser`/`requests`** | 新闻模块用标准库 `urllib` + `xml.etree` 自实现 RSS 解析，少一个依赖少一处故障 |

---

## 4. 部署方式怎么选

| 方式 | 适合场景 | 公网访问 | 数据持久 | 成本 | 上手难度 |
|---|---|---|---|---|---|
| **A. WorkBuddy 发布为应用**（当前采用） | 想立刻上线、不想碰服务器 | ✅ 一键生成网址 | ⚠️ 临时文件系统，重新发布会清空 | 免费 | ★☆☆ |
| **B. Streamlit Community Cloud** | 有 GitHub、想要免费长期托管 | ✅ `*.streamlit.app` | ⚠️ 重启即重置 | 免费 | ★★☆ |
| **C. 自有服务器 / Docker** | 要保留用户数据、要自定义域名 | ✅ 自行绑域名 + HTTPS | ✅ 挂持久卷即可 | 服务器费用 | ★★★ |
| **D. Render / Railway** | 想要持久磁盘又不想运维 | ✅ | ✅ 支持 Disk / Volume | 有免费额度 | ★★☆ |

**选择建议**

- **只想先跑起来看效果** → 选 A（已就绪）。
- **要正式运营、要留住用户数据** → 选 C 或 D，并设置 `GAOLEDA_DATA_DIR` 指向持久卷。
- **介于两者之间** → 选 B，但上线前务必把 `data/` 排除在仓库外，并在 `st.secrets` 里管理敏感配置。

---

## 5. 启动命令

### 5.1 本地开发

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
python app.py                     # 或 streamlit run app.py
```

浏览器打开 <http://localhost:8501>。

### 5.2 通用 / 容器 / 托管平台（推荐）

```bash
PORT=8000 python app.py
```

`PORT` 不设时默认 8501；服务始终绑定 `0.0.0.0`。

### 5.3 标准 Streamlit 命令（显式指参）

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 \
                     --server.headless true --server.fileWatcherType none
```

### 5.4 Docker（可选）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8501
EXPOSE 8501
CMD ["python", "app.py"]
```

```bash
docker build -t gaoleda-ai .
docker run -d -p 8501:8501 -v gaoleda_data:/app/data gaoleda-ai   # 挂卷 = 数据持久
```

> `-v gaoleda_data:/app/data` 这一句就是「数据不丢」的关键。

### 5.5 Nginx 反向代理（自有服务器必看）

Streamlit 依赖 **WebSocket**，反代必须透传升级头：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;      # 关键
    proxy_set_header Connection "upgrade";       # 关键
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400;                    # 长连接不中断
}
```

---

## 6. 发布后如何验证访问

按顺序四步，**最后一步最重要**（curl 只能证明 HTTP 通，证明不了 WebSocket 通）：

| 步骤 | 命令 / 操作 | 期望 |
|---|---|---|
| 1. 进程存活 | `curl -s <网址>/_stcore/health` | 返回 `ok` |
| 2. 首页可达 | `curl -s -o /dev/null -w "%{http_code}" <网址>/` | `200` |
| 3. **浏览器实测** | 用真实浏览器打开网址 | 页面完整渲染、不转圈、无控制台报错 |
| 4. 主链路走一遍 | 注册 → 登录 → 发新闻页 → 发帖 → 点赞 → 上传文件 | 全流程可用 |

> Streamlit 是 WebSocket 应用：**HTTP 200 不代表能用**。如果代理没透传 `Upgrade` / `Connection` 头，页面会一直停在骨架屏转圈。

---

## 7. 排查问题要点

| 现象 | 根因 | 解决 |
|---|---|---|
| 页面一直转圈 / 空白骨架 | WebSocket 未打通（代理缺 `Upgrade`/`Connection` 头） | 按 5.5 补齐 Nginx 配置；确认 CDN 未剥离升级头 |
| `ModuleNotFoundError: No module named 'core'` | 包目录缺 `__init__.py`；或在错误目录启动 | 补 `__init__.py`；确认启动目录 = 项目根，主文件 = `app.py` |
| `ModuleNotFoundError: No module named 'streamlit'` | 依赖未装 / `requirements.txt` 缺失 | 确认 `requirements.txt` 存在且在根目录，重装依赖 |
| **重新发布后用户、帖子、上传文件全没了** | 平台用**临时文件系统**，每次重建容器清空 `data/`（其中含 SQLite 库、上传文件、头像、`.secret` 密钥） | 设置 `GAOLEDA_DATA_DIR=/持久卷路径`；或改用带持久磁盘的平台（C / D 方式） |
| 管理员后台不显示 | 当前账号不是管理员 | 用用户名 `William` 注册（命中 `config.ADMIN_USERNAMES` 即自动授权）；老账号会在启动时自动提权 |
| 成员密码显示「（无法解密）」 | `data/.secret` 丢失或更换，历史密码副本无法还原 | 属预期行为；让该成员改一次密码即可重新生成可解密的副本 |
| 刷新后登录状态丢失 | Cookie 被浏览器拦截 / 站点在无 cookie 的隐私模式 | 确认允许站点 Cookie；`data/.secret` 变化也会让旧令牌失效 |
| 上传文件失败 | 超过限制 | `config.toml` 的 `maxUploadSize`（传输层）与 `core/config.py` 的 `MAX_UPLOAD_MB`（业务层）两处都要够 |
| 启动报端口占用 | 本地 8501 被占 | 换端口：`PORT=8502 python app.py` |
| 容器外访问不到 | 绑定了 `127.0.0.1` | 必须绑 `0.0.0.0`（代码已默认处理） |
| 提交表单报 XSRF / 跨域错误 | 反代后来源与配置不符 | `config.toml` 里 `enableCORS = false`、`enableXsrfProtection = false`；HTTPS 场景再由反代统一处理 |
| AI 新闻空白 | 服务器访问不了国际 RSS 源、或被限流 | 代码已内置**近一年精选归档兜底**，页面不会空白；如长期如此，把 `core/news.py` 的 `FEEDS` 换成可访问的源 |
| 移动端侧边栏挡住内容 | 侧边栏默认展开 | 已用 `initial_sidebar_state="auto"`：桌面展开、移动收起 |
| 日志里刷 `missing ScriptRunContext` | 在 `streamlit run` 之外直接跑页面代码 | 正常现象，仅出现在离线测试；线上以 `streamlit run` 启动即无 |

---

## 8. 上线检查清单（发布前逐项打勾）

- [ ] `app.py`、`requirements.txt`、`.streamlit/config.toml` 均在项目根目录
- [ ] `core/` `views/` `ui/` 三个包都含 `__init__.py`
- [ ] `data/` 已写入 `.gitignore`（不把用户数据推到公开仓库）
- [ ] `requirements.txt` 有下界 + 上界，且不含多余依赖
- [ ] 本地 `python -m unittest discover -s tests` 全绿
- [ ] 本地 `python app.py` 起得来，浏览器能正常渲染
- [ ] 发布后 `/_stcore/health` 返回 `ok`
- [ ] 用**真实浏览器**走通「注册 → 登录 → 发帖 → 上传」
- [ ] 桌面端 + 移动端各看一次布局
- [ ] 若需保留数据，已配置 `GAOLEDA_DATA_DIR` 或持久卷

---

## 9. 一条命令速查

```bash
# 装依赖
pip install -r requirements.txt

# 本地起
python app.py

# 指定端口起（云端通用）
PORT=8000 python app.py

# 健康检查
curl -s http://127.0.0.1:8000/_stcore/health      # → ok

# 跑测试
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python scripts/flow_test.py
```
