"""AI 新闻模块：多源 RSS 聚合 + 近一年筛选 + 30 分钟缓存 + 精选兜底。

为什么不用 streamlit 的 st.cache_data
    缓存放在 core 层，桌面版 / API 版可直接复用；且落盘缓存能跨进程重启存活。
数据来源
    主：5 个国际权威 AI 信源 RSS（实时更新）。
    备：内置「近一年最具影响力 AI 事件」精选条目，网络不可用时保证页面不空白，
        每条都带来源标注，不会被误认为实时新闻。
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

from .config import NEWS_CACHE_PATH, NEWS_LIMIT, NEWS_TTL_SECONDS, NEWS_WINDOW_DAYS

USER_AGENT = "Mozilla/5.0 (compatible; GaoLedaAILearning/1.0; +rss-reader)"

FEEDS: list[dict[str, str]] = [
    {"name": "MIT Technology Review · AI",
     "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    {"name": "VentureBeat · AI",
     "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "WIRED · AI",
     "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "Ars Technica · Technology Lab",
     "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"name": "Google DeepMind · Blog",
     "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "OpenAI · News",
     "url": "https://openai.com/news/rss.xml"},
]

# ---------------------------------------------------------------- 精选兜底
# 来源：公开报道（求是网、世界人工智能大会官方、企业官方发布）。
FALLBACK_NEWS: list[dict[str, Any]] = [
    {
        "title": "全球四家头部 AI 企业签署《白宫超级智能协议：前沿责任联合承诺》",
        "summary": "谷歌、Anthropic、OpenAI 与英伟达等公司负责人共同签署前沿责任承诺文件，"
                   "就前沿模型的安全评估、透明度与风险沟通作出联合表态，被视为行业自律与"
                   "公共治理衔接的标志性一步。",
        "link": "https://www.whitehouse.gov/",
        "published": "2026-09-29",
        "source": "白宫 / 公开报道",
        "fallback": True,
    },
    {
        "title": "OpenAI 宣布取消发布下一代模型 GPT-6.1 Astra",
        "summary": "公司称内部测试发现该模型未达到既定的「安全与对齐标准」，因此决定取消原定"
                   "发布计划。这是头部实验室首次因安全评估不达标而主动取消一次重要版本发布，"
                   "引发业界对「能力—安全」取舍的广泛讨论。",
        "link": "https://www.qstheory.cn/20261002/38a5c3a4eb764771b1554548ef6b486c/c.html",
        "published": "2026-09-30",
        "source": "求是网",
        "fallback": True,
    },
    {
        "title": "联合国安理会就「人工智能与国际安全」举行高级别会议",
        "summary": "联合国秘书长在会上表示 AI 技术发展速度已超出人类理解其全部后果的能力，呼吁"
                   "AI 强国承担更大责任、加强对话与透明度。全球 AI 治理正从原则讨论走向实质性"
                   "的风险沟通机制建设。",
        "link": "https://www.un.org/",
        "published": "2026-09-23",
        "source": "联合国",
        "fallback": True,
    },
    {
        "title": "阿里巴巴云栖大会发布真武 V900 AI 芯片并公布下一代大模型计划",
        "summary": "真武 V900 性能较上一代大幅提升；同时提出研发参数规模 5 万亿至 10 万亿级的新"
                   "模型，并计划到 2032 年将阿里云数据中心规模扩大到 20 吉瓦以上。算力与模型"
                   "纵深布局成为新一轮竞争的焦点。",
        "link": "https://www.alibabacloud.com/",
        "published": "2026-09-22",
        "source": "阿里云栖大会",
        "fallback": True,
    },
    {
        "title": "WAIC 2026 世界人工智能大会：智能体、算力基建、具身智能、AI 安全治理成四大核心赛道",
        "summary": "大会集中展示新一代智能体操作系统与多模态大模型矩阵，AI 从被动应答转向主动"
                   "服务；具身智能与人人形机器人量产方案首次公开，业内将 2026 年视为具身智能"
                   "商业化落地关键元年。",
        "link": "https://www.worldaic.com.cn/",
        "published": "2026-07-08",
        "source": "世界人工智能大会",
        "fallback": True,
    },
]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------- 工具
def _clean(text: str, limit: int = 260) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        if _local_name(child.tag) in names:
            if _local_name(child.tag) == "link" and child.get("href"):
                return child.get("href", "")
            if child.text:
                return child.text
    return ""


def _parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except Exception:
        dt = None
    if dt is None:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw.replace("Z", "+0000"), fmt)
                break
            except Exception:
                continue
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _fetch_bytes(url: str, timeout: int = 6) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _fetch_all_feeds() -> tuple[list[dict[str, Any]], list[str]]:
    """并行抓取所有信源，把总耗时压到「单源超时」级别。"""
    collected: list[dict[str, Any]] = []
    errors: list[str] = []

    def one(feed: dict[str, str]) -> list[dict[str, Any]]:
        return _parse_feed(_fetch_bytes(feed["url"]), feed["name"])

    with ThreadPoolExecutor(max_workers=len(FEEDS)) as pool:
        futures = {pool.submit(one, f): f for f in FEEDS}
        for fut in as_completed(futures):
            feed = futures[fut]
            try:
                collected.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{feed['name']}: {type(exc).__name__}")
    return collected, errors


def _parse_feed(raw: bytes, source: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for node in root.iter():
        if _local_name(node.tag) not in ("item", "entry"):
            continue
        title = _clean(_child_text(node, ("title",)), 160)
        link = _child_text(node, ("link", "guid", "id"))
        summary = _clean(
            _child_text(node, ("summary", "description", "content", "encoded")), 300
        )
        published = _parse_date(
            _child_text(node, ("pubdate", "published", "updated", "date", "created"))
        )
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": summary or "（该条目未提供摘要，点击查看原文）",
                "link": link or "",
                "published": (published or datetime.now()).strftime("%Y-%m-%d"),
                "_ts": (published or datetime.now()).timestamp(),
                "source": source,
                "fallback": False,
            }
        )
    return items


# ---------------------------------------------------------------- 缓存
def _read_cache() -> dict[str, Any] | None:
    try:
        if not NEWS_CACHE_PATH.exists():
            return None
        return json.loads(NEWS_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(items: list[dict[str, Any]]) -> None:
    try:
        NEWS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": time.time(),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "items": [{k: v for k, v in it.items() if not k.startswith("_")} for it in items],
        }
        NEWS_CACHE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _fallback(limit: int) -> list[dict[str, Any]]:
    now = datetime.now()
    out = []
    for i, item in enumerate(FALLBACK_NEWS[:limit]):
        copy = dict(item)
        copy.setdefault("_ts", (now - timedelta(days=i)).timestamp())
        out.append(copy)
    return out


# ---------------------------------------------------------------- 对外接口
def fetch_news(limit: int = NEWS_LIMIT, force: bool = False) -> dict[str, Any]:
    """返回 {items, updated_at, live, note}。

    live=True  表示条目来自实时 RSS；
    live=False 表示网络不可用、使用了精选兜底（note 里说明原因）。
    """
    cache = _read_cache()
    if (
        not force
        and cache
        and (time.time() - float(cache.get("fetched_at", 0))) < NEWS_TTL_SECONDS
        and cache.get("items")
    ):
        items = cache["items"][:limit]
        return {
            "items": items,
            "updated_at": cache.get("updated_at", ""),
            "live": any(not it.get("fallback") for it in items),
            "note": "缓存命中（30 分钟自动刷新）" if not items[0].get("fallback") else "精选归档",
        }

    cutoff = datetime.now() - timedelta(days=NEWS_WINDOW_DAYS)
    collected, errors = _fetch_all_feeds()

    # 近一年 + 去重（标题归一化）
    seen: set[str] = set()
    fresh: list[dict[str, Any]] = []
    for item in collected:
        try:
            ts = datetime.strptime(item["published"], "%Y-%m-%d")
        except Exception:
            ts = None
        if ts is None or ts < cutoff:
            continue
        key = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", item["title"].lower())[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        fresh.append(item)

    fresh.sort(key=lambda x: x.get("_ts", 0), reverse=True)

    if len(fresh) >= limit:
        items = fresh[:limit]
    else:
        # 实时条目不足：用精选补齐，保证永远有 5 条可看
        pad = [dict(x) for x in _fallback(limit - len(fresh))]
        items = fresh + pad

    live = bool(fresh)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    for it in items:
        it.pop("_ts", None)
    # 无论成败都写缓存：避免外网不可达时每次重跑都干等一轮超时
    _write_cache(items)

    if live:
        note = "实时抓取完成"
    else:
        note = "外部信源当前不可达，已展示精选归档内容" + (
            f"（{len(errors)} 个信源失败）" if errors else ""
        )

    return {"items": items, "updated_at": updated_at, "live": live, "note": note}


def get_news_by_title(title: str) -> dict[str, Any] | None:
    for item in fetch_news(limit=NEWS_LIMIT)["items"]:
        if item["title"] == title:
            return item
    for item in FALLBACK_NEWS:
        if item["title"] == title:
            return item
    return None


def cached_at() -> str | None:
    cache = _read_cache()
    return cache.get("updated_at") if cache else None
