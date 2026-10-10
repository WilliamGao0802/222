"""视觉主题：一整套 CSS，深色简约 · 艺术感 · 科技感。

配色
    底色   #0A0D18 深空蓝黑
    面板   #141829 → rgba 玻璃拟态
    主色   #7C6CF6 靛紫   辅色 #22D3EE 青
    正文   #E8EAF6        次要 #9BA3C7
细节动效
    顶部极光缓慢流动、卡片入场上浮、悬停微抬与光晕、按钮渐变位移。
    全部使用 CSS 完成，零 JS 依赖，移动端自动降级。
"""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
:root {
    --g-bg: #0A0D18;
    --g-panel: rgba(20, 24, 41, 0.72);
    --g-panel-solid: #141829;
    --g-border: rgba(255, 255, 255, 0.08);
    --g-border-strong: rgba(124, 108, 246, 0.45);
    --g-text: #E8EAF6;
    --g-muted: #9BA3C7;
    --g-dim: #6E7799;
    --g-primary: #7C6CF6;
    --g-primary-deep: #5B4BD6;
    --g-cyan: #22D3EE;
    --g-mint: #6EE7B7;
    --g-amber: #FBBF24;
    --g-radius: 18px;
    --g-shadow: 0 18px 44px rgba(3, 6, 20, 0.55);
    --g-font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
              "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

/* ---------------- 全局 ---------------- */
html, body, [class*="css"], .stApp {
    font-family: var(--g-font) !important;
    -webkit-font-smoothing: antialiased;
}

.stApp {
    background: var(--g-bg);
    color: var(--g-text);
}

/* 顶部极光背景 */
.stApp::before {
    content: "";
    position: fixed;
    inset: -30% -20% auto -20%;
    height: 120vh;
    pointer-events: none;
    z-index: 0;
    background:
        radial-gradient(46% 40% at 18% 22%, rgba(124, 108, 246, 0.30), transparent 62%),
        radial-gradient(40% 36% at 82% 12%, rgba(34, 211, 238, 0.18), transparent 60%),
        radial-gradient(38% 34% at 55% 78%, rgba(110, 231, 183, 0.10), transparent 62%);
    filter: blur(28px);
    animation: g-aurora 26s ease-in-out infinite alternate;
}

@keyframes g-aurora {
    0%   { transform: translate3d(-2%, 0, 0) scale(1); }
    50%  { transform: translate3d(2%, -2%, 0) scale(1.06); }
    100% { transform: translate3d(0, 2%, 0) scale(1); }
}

@keyframes g-rise {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes g-sheen {
    0%   { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}

header[data-testid="stHeader"] {
    background: transparent !important;
    backdrop-filter: blur(6px);
}

.block-container {
    position: relative;
    z-index: 1;
    padding-top: 2.2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1120px;
}

/* ---------------- 侧边栏 ---------------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(13, 17, 32, 0.96), rgba(10, 13, 24, 0.98));
    border-right: 1px solid var(--g-border);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }

[data-testid="stSidebarNav"] ul { gap: 4px; }
[data-testid="stSidebarNav"] a {
    border-radius: 12px;
    color: var(--g-muted) !important;
    transition: all .18s ease;
}
[data-testid="stSidebarNav"] a:hover {
    background: rgba(124, 108, 246, 0.14);
    color: var(--g-text) !important;
    transform: translateX(3px);
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: linear-gradient(90deg, rgba(124,108,246,.28), rgba(34,211,238,.10));
    color: #fff !important;
    font-weight: 600;
    box-shadow: inset 0 0 0 1px var(--g-border-strong);
}

/* ---------------- 标题 / 文本 ---------------- */
h1, h2, h3, h4 { color: var(--g-text) !important; letter-spacing: .3px; }
p, li, span, label { color: var(--g-text); }
a { color: var(--g-cyan); }
hr { border-color: var(--g-border) !important; }

/* ---------------- 英雄区 ---------------- */
.g-hero {
    position: relative;
    padding: 34px 32px 30px;
    border-radius: 24px;
    margin-bottom: 22px;
    overflow: hidden;
    background:
        linear-gradient(135deg, rgba(124, 108, 246, .18), rgba(34, 211, 238, .08) 55%, rgba(20,24,41,.35)),
        rgba(20, 24, 41, .55);
    border: 1px solid var(--g-border);
    box-shadow: var(--g-shadow);
    animation: g-rise .5s ease both;
}
.g-hero::after {
    content: "";
    position: absolute;
    top: -60%; right: -10%;
    width: 340px; height: 340px;
    background: radial-gradient(circle, rgba(34,211,238,.28), transparent 68%);
    pointer-events: none;
}
.g-hero .g-kicker {
    font-size: 12px; letter-spacing: 3px; text-transform: uppercase;
    color: var(--g-cyan); font-weight: 600; margin-bottom: 10px;
}
.g-hero h1 {
    margin: 0 0 8px; font-size: 38px; line-height: 1.2; font-weight: 800;
    background: linear-gradient(100deg, #C7BEFF 0%, #7C6CF6 35%, #22D3EE 75%, #C7BEFF 100%);
    background-size: 200% auto;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: g-sheen 8s linear infinite;
}
.g-hero p { margin: 0; color: var(--g-muted); font-size: 15px; }

/* ---------------- 卡片 ---------------- */
.g-card {
    padding: 20px 22px;
    border-radius: var(--g-radius);
    background: var(--g-panel);
    border: 1px solid var(--g-border);
    backdrop-filter: blur(10px);
    transition: transform .25s ease, border-color .25s ease, box-shadow .25s ease;
    margin-bottom: 14px;
    animation: g-rise .45s ease both;
}
.g-card:hover {
    transform: translateY(-4px);
    border-color: var(--g-border-strong);
    box-shadow: 0 16px 40px rgba(124, 108, 246, .22);
}
.g-card h3 { margin: 0 0 8px; font-size: 18px; line-height: 1.45; }
.g-card .g-meta {
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
    color: var(--g-dim); font-size: 12.5px; margin-bottom: 9px;
}
.g-card .g-body { color: #C6CCE6; font-size: 14.5px; line-height: 1.85; margin: 0; }

.g-index {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; border-radius: 9px; margin-right: 9px;
    font-size: 13px; font-weight: 700; color: #fff;
    background: linear-gradient(135deg, var(--g-primary), var(--g-cyan));
}

/* ---------------- 标签 ---------------- */
.g-chip {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 11.5px; font-weight: 600; letter-spacing: .4px;
    background: rgba(124, 108, 246, .16); color: #BDB2FF;
    border: 1px solid rgba(124, 108, 246, .3);
}
.g-chip.g-cyan  { background: rgba(34,211,238,.14); color: #8BE9F9; border-color: rgba(34,211,238,.3); }
.g-chip.g-mint  { background: rgba(110,231,183,.13); color: #A7F3D0; border-color: rgba(110,231,183,.28); }
.g-chip.g-amber { background: rgba(251,191,36,.13); color: #FDE68A; border-color: rgba(251,191,36,.28); }

/* ---------------- 数据块 ---------------- */
div[data-testid="stMetric"] {
    background: var(--g-panel);
    border: 1px solid var(--g-border);
    border-radius: var(--g-radius);
    padding: 16px 18px;
    transition: transform .22s ease, border-color .22s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    border-color: var(--g-border-strong);
}
div[data-testid="stMetricLabel"] p { color: var(--g-muted) !important; font-size: 13px !important; }
div[data-testid="stMetricValue"] {
    background: linear-gradient(100deg, #C7BEFF, #22D3EE);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
}

/* ---------------- 表单控件 ---------------- */
div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {
    background: rgba(11, 14, 27, .82) !important;
    border: 1px solid var(--g-border) !important;
    border-radius: 12px !important;
    transition: border-color .2s ease, box-shadow .2s ease;
}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="textarea"]:focus-within {
    border-color: var(--g-primary) !important;
    box-shadow: 0 0 0 3px rgba(124, 108, 246, .18) !important;
}
input, textarea { color: var(--g-text) !important; }

/* ---------------- 按钮 ---------------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    border-radius: 12px !important;
    border: 1px solid rgba(124, 108, 246, .45) !important;
    background: linear-gradient(135deg, rgba(124,108,246,.92), rgba(91,75,214,.92)) !important;
    color: #fff !important;
    font-weight: 600 !important;
    transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
    transform: translateY(-2px);
    filter: brightness(1.08);
    box-shadow: 0 10px 26px rgba(124, 108, 246, .38) !important;
}
.stButton > button:active { transform: translateY(0); }
.stButton > button[kind="secondary"] {
    background: rgba(124, 108, 246, .12) !important;
    color: #C7BEFF !important;
}

/* ---------------- 标签页 ---------------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: rgba(20, 24, 41, .6);
    padding: 6px;
    border-radius: 14px;
    border: 1px solid var(--g-border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px; color: var(--g-muted); font-weight: 600; padding: 6px 16px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(124,108,246,.9), rgba(91,75,214,.9)) !important;
    color: #fff !important;
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* ---------------- 折叠 / 提示 / 上传 ---------------- */
div[data-testid="stExpander"] {
    background: var(--g-panel);
    border: 1px solid var(--g-border) !important;
    border-radius: 14px !important;
    overflow: hidden;
}

/* 带边框容器（发言卡片 / 文件卡片） */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--g-panel);
    border: 1px solid var(--g-border) !important;
    border-radius: var(--g-radius) !important;
    padding: 6px 4px;
    backdrop-filter: blur(10px);
    transition: border-color .22s ease, transform .22s ease, box-shadow .22s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--g-border-strong) !important;
    box-shadow: 0 14px 34px rgba(124, 108, 246, .16);
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { border: none !important; }
div[data-testid="stExpander"] summary { color: var(--g-text) !important; font-weight: 600; }

div[data-testid="stAlert"] {
    border-radius: 14px !important;
    border: 1px solid var(--g-border) !important;
    background: rgba(20, 24, 41, .82) !important;
}

section[data-testid="stFileUploaderDropzone"] {
    background: rgba(11, 14, 27, .6) !important;
    border: 1.5px dashed rgba(124, 108, 246, .45) !important;
    border-radius: 16px !important;
    transition: border-color .2s ease, background .2s ease;
}
section[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--g-cyan) !important;
    background: rgba(34, 211, 238, .05) !important;
}

/* ---------------- 自定义小块 ---------------- */
.g-empty {
    padding: 34px 22px; text-align: center;
    border-radius: var(--g-radius);
    border: 1px dashed var(--g-border);
    background: rgba(20, 24, 41, .4);
    color: var(--g-muted);
}
.g-empty .g-emo { font-size: 30px; display: block; margin-bottom: 8px; }

.g-list-item {
    display: flex; justify-content: space-between; gap: 12px;
    padding: 12px 14px; border-radius: 12px;
    background: rgba(11, 14, 27, .45);
    border: 1px solid var(--g-border);
    margin-bottom: 8px;
    transition: border-color .2s ease, transform .2s ease;
}
.g-list-item:hover { border-color: var(--g-border-strong); transform: translateX(3px); }
.g-list-item .g-name { font-weight: 600; color: var(--g-text); font-size: 14px; }
.g-list-item .g-sub { color: var(--g-dim); font-size: 12px; margin-top: 2px; }

.g-foot {
    margin-top: 40px; padding-top: 18px;
    border-top: 1px solid var(--g-border);
    color: var(--g-dim); font-size: 12.5px; text-align: center; line-height: 1.9;
}

.g-userbox {
    padding: 14px 14px 12px;
    border-radius: 16px;
    background: linear-gradient(135deg, rgba(124,108,246,.16), rgba(34,211,238,.07));
    border: 1px solid var(--g-border);
    margin-bottom: 12px;
}
.g-userbox .g-uname { font-weight: 700; color: #fff; font-size: 15px; }
.g-userbox .g-usub { color: var(--g-muted); font-size: 12px; margin-top: 3px; }

/* ---------------- 移动端 ---------------- */
@media (max-width: 768px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .g-hero { padding: 24px 18px; border-radius: 18px; }
    .g-hero h1 { font-size: 25px; }
    .g-hero p { font-size: 13.5px; }
    .g-card { padding: 16px; }
    .g-card h3 { font-size: 16px; }
    .g-card .g-body { font-size: 13.5px; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
}
</style>
"""


def inject() -> None:
    """注入整套主题样式（每个页面调用一次）。"""
    st.markdown(CSS, unsafe_allow_html=True)
