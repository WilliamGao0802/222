# 学习AI with William Gao

> 一个可直接部署、可公开访问的 AI 学习社区 —— Streamlit + SQLite 单文件持久化。

站点源码位于 **[`gaoleda-ai-learning/`](./gaoleda-ai-learning)** 目录。

---

## 快速开始

```bash
cd gaoleda-ai-learning
pip install -r requirements.txt
python app.py            # 或 streamlit run app.py
```

浏览器打开 <http://localhost:8501>。

## 部署上线

完整部署说明见 **[`gaoleda-ai-learning/DEPLOY.md`](./gaoleda-ai-learning/DEPLOY.md)**，要点：

| 事项 | 说明 |
|---|---|
| 入口脚本 | `app.py`（`streamlit run app.py` 与 `python app.py` 双兼容，自动读 `PORT`） |
| 依赖 | 仅 `streamlit` 一项，其余全为标准库 |
| 启动命令 | `python app.py`（云端/容器）；本地同一条命令 |
| 健康检查 | `GET /_stcore/health` → `ok` |
| 数据持久化 | 默认写入 `data/`；用环境变量 `GAOLEDA_DATA_DIR` 指向持久卷 |

## 功能一览

- **用户系统**：注册 / 登录 / 退出，上限 1000 人，密码为 6 位阿拉伯数字，手机号绑定
- **记住登录**：登录状态写入浏览器 Cookie（HMAC 签名），刷新页面不需要重复登录
- **管理员后台**：`William` 账户可见，查看成员名单与密码、删除成员账户
- **个人中心**：个人简介、更换头像（本地上传）、修改密码与手机号
- **AI 新闻**：聚合多个国际权威信源 RSS，只保留近一年并去重，支持点进详情与跳转原文
- **讨论区**：发帖、互赞、互关、话题筛选、活跃榜，以及**草稿箱**（存稿 / 载入 / 直接发布）
- **文件区**：按**算法 / 文章 / 语法 / 题解**四个仓库分类上传，内置站内搜索引擎

## 测试

```bash
cd gaoleda-ai-learning
python -m unittest discover -s tests -v   # 单元测试
python scripts/smoke_test.py              # 页面渲染冒烟测试
python scripts/flow_test.py               # 主链路功能测试
```

## ⚠️ 数据说明

`data/` 为运行时生成目录（SQLite 库 + 上传文件），已在 `.gitignore` 中排除，**不会**进入仓库。
托管平台若使用临时文件系统，重新部署会清空 `data/`；需要持久化时设置 `GAOLEDA_DATA_DIR`。
