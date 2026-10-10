"""端到端冒烟测试：用 Streamlit 官方 AppTest 真正执行每个页面，捕获异常。

为什么不用无头浏览器 dump-dom：Streamlit 是 SPA，静态 DOM 里只有骨架，
无法反映 Python 端是否抛错。AppTest 会把脚本真实跑一遍。

运行：
    python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

RUNNER = str(ROOT / "scripts" / "_page_runner.py")
APP = str(ROOT / "app.py")

failures: list[str] = []
passes: list[str] = []


def run_case(label: str, page: str, user: str = "", detail: str = "") -> None:
    os.environ["SMOKE_PAGE"] = page
    os.environ["SMOKE_USER"] = user
    os.environ["SMOKE_NEWS_DETAIL"] = detail
    try:
        at = AppTest.from_file(RUNNER, default_timeout=180)
        at.run()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"[{label}] 运行期异常：{type(exc).__name__}: {exc}")
        return

    if at.exception:
        for e in at.exception:
            failures.append(f"[{label}] 页面报错：{e.value}")
        return

    passes.append(
        f"[{label}] 正常（markdown {len(at.markdown)} · 按钮 {len(at.button)}"
        f" · 输入框 {len(at.text_input)}）"
    )


def main() -> int:
    print("① 应用外壳（app.py 默认页 + 侧边栏）…")
    try:
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
        if at.exception:
            for e in at.exception:
                failures.append(f"[应用外壳] 页面报错：{e.value}")
        else:
            passes.append(
                f"[应用外壳] 正常（侧边栏按钮 {len(at.sidebar.button)} 个）"
            )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"[应用外壳] 运行期异常：{type(exc).__name__}: {exc}")

    print("② 游客视角逐页渲染…")
    for page in ("首页", "AI 新闻", "讨论区", "文件区", "我的账户"):
        run_case(f"游客 · {page}", page, user="")

    print("③ 登录用户视角逐页渲染…")
    for page in ("首页", "讨论区", "文件区", "我的账户"):
        run_case(f"已登录 · {page}", page, user="smoke_tester")

    print("④ 新闻详情视图…")
    from core import news as news_store  # noqa: PLC0415

    items = news_store.fetch_news(5)["items"]
    run_case("新闻详情", "AI 新闻", user="", detail=items[0]["title"])

    print("⑤ 管理后台（游客 / 普通成员 / 管理员）…")
    run_case("游客 · 管理后台", "管理后台", user="")
    run_case("普通成员 · 管理后台", "管理后台", user="smoke_tester")

    from core import auth  # noqa: PLC0415

    if not auth.user_exists("William"):
        auth.register("William", "888888", "13800000001")
    run_case("管理员 · 管理后台", "管理后台", user="William")

    print()
    for line in passes:
        print("  ✓", line)
    if failures:
        print()
        for line in failures:
            print("  ✗", line)
        return 1
    print()
    print("全部页面渲染通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
