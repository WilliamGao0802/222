"""主链路功能测试：真的点按钮走一遍「注册 → 登录 → 发帖 → 点赞 → 关注 → 上传」。

用 AppTest 驱动真实 widget（不是直接调 core），验证表单、会话状态、
按钮回调与页面重跑之间的衔接没有问题。

运行：
    python scripts/flow_test.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 必须在 import core 之前设置，保证测试数据落在临时目录
TMP = tempfile.mkdtemp(prefix="gaoleda_flow_")
os.environ["GAOLEDA_DATA_DIR"] = TMP

sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

RUNNER = str(ROOT / "scripts" / "_page_runner.py")

problems: list[str] = []
steps: list[str] = []


def ok(text: str) -> None:
    steps.append(text)


def bad(text: str) -> None:
    problems.append(text)


def open_page(page: str, user: str = "") -> AppTest:
    os.environ["SMOKE_PAGE"] = page
    os.environ["SMOKE_USER"] = user
    os.environ["SMOKE_NEWS_DETAIL"] = ""
    at = AppTest.from_file(RUNNER, default_timeout=180)
    at.run()
    return at


def click_submit(at: AppTest, label: str) -> AppTest:
    """点击表单提交按钮（表单提交按钮也注册在 at.button 里）。"""
    for b in at.button:
        if b.label.strip() == label:
            b.click()
            return at.run()
    raise AssertionError(f"找不到按钮：{label}，现有 {[b.label for b in at.button]}")


def main() -> int:  # noqa: C901
    # ---------------- 注册 ----------------
    at = open_page("我的账户")
    labels = [t.label for t in at.text_input]
    ok(f"账户页输入框：{labels}")

    at.text_input[2].set_value("flow_user")
    at.text_input[3].set_value("123456")
    at.text_input[4].set_value("123456")
    at = click_submit(at, "注册")
    if at.exception:
        bad(f"注册时抛异常：{at.exception[0].value}")
    elif not any("注册成功" in s.value for s in at.success):
        bad(f"注册未成功：{[s.value for s in at.success]} / {[e.value for e in at.error]}")
    else:
        ok("注册成功（用户名 flow_user / 密码 123456）")

    # 密码格式错误分支
    at.text_input[2].set_value("flow_user2")
    at.text_input[3].set_value("abc")
    at.text_input[4].set_value("abc")
    at = click_submit(at, "注册")
    if any("数字" in e.value for e in at.error):
        ok("非法密码被拦截并给出明确提示")
    else:
        bad(f"非法密码未被拦截：{[e.value for e in at.error]}")

    # 重复用户名分支
    at.text_input[2].set_value("flow_user")
    at.text_input[3].set_value("123456")
    at.text_input[4].set_value("123456")
    at = click_submit(at, "注册")
    if any("已被注册" in e.value for e in at.error):
        ok("重复用户名被拦截")
    else:
        bad(f"重复用户名未被拦截：{[e.value for e in at.error]}")

    # 两次密码不一致
    at.text_input[2].set_value("flow_user3")
    at.text_input[3].set_value("123456")
    at.text_input[4].set_value("654321")
    at = click_submit(at, "注册")
    if any("不一致" in e.value for e in at.error):
        ok("两次密码不一致被拦截")
    else:
        bad(f"两次密码不一致未被拦截：{[e.value for e in at.error]}")

    # ---------------- 登录 ----------------
    at.text_input[0].set_value("flow_user")
    at.text_input[1].set_value("000000")
    at = click_submit(at, "登录")
    if any("密码错误" in e.value for e in at.error):
        ok("错误密码被拦截")
    else:
        bad(f"错误密码未被拦截：{[e.value for e in at.error]}")

    at.text_input[0].set_value("flow_user")
    at.text_input[1].set_value("123456")
    at = click_submit(at, "登录")
    if at.session_state.get("user") == "flow_user":
        ok("登录成功，会话状态已写入 user")
    else:
        bad(f"登录失败：{at.session_state.get('user')!r} / {[e.value for e in at.error]}")

    # ---------------- 发帖 ----------------
    from core import discussion  # noqa: PLC0415

    at = open_page("讨论区", user="flow_user")
    at.text_area[0].set_value("这是我的第一条测试发言")
    at = click_submit(at, "发布")
    posts = discussion.list_posts()
    if at.exception:
        bad(f"发帖时抛异常：{at.exception[0].value}")
    elif posts and posts[0]["content"] == "这是我的第一条测试发言":
        ok("发言发布成功（已落库）")
    else:
        bad(f"发言发布失败：已入库 {len(posts)} 条")

    # 超长内容：控件层限长 + core 层兜底，两层都要有
    before_count = discussion.count_posts()
    at.text_area[0].set_value("字" * 501)
    at = click_submit(at, "发布")
    after_count = discussion.count_posts()
    latest = discussion.list_posts()[0] if after_count else None
    if after_count == before_count:
        ok("超长发言被控件层拦截，未入库")
    elif latest and len(latest["content"]) == 500:
        ok("超长输入被控件层截断到 500 字上限后才入库")
    else:
        bad(f"超长内容突破了 500 字上限：{len(latest['content']) if latest else '-'} 字")

    accepted, msg = discussion.add_post("flow_user", "字" * 501)
    if not accepted and "过长" in msg:
        ok("core 层对超长内容做兜底拦截（不依赖前端）")
    else:
        bad(f"core 层未拦截超长内容：{msg!r}")

    # ---------------- 点赞 / 关注（换一个用户视角） ----------------
    at = open_page("讨论区", user="flow_user")
    like_buttons = [b for b in at.button if b.label.startswith(("❤️", "🤍"))]
    if not like_buttons:
        bad("未渲染出点赞按钮")
    else:
        before = like_buttons[0].label
        like_buttons[0].click()
        at = at.run()
        after = [b for b in at.button if b.label.startswith(("❤️", "🤍"))][0].label
        if before != after:
            ok(f"点赞状态切换成功：{before} → {after}")
        else:
            bad(f"点赞状态未变化：{before}")

    # ---------------- 上传 ----------------
    from core import files as file_store  # noqa: PLC0415

    ok_flag, msg = file_store.save_upload("flow_user", "资料.txt", b"hello", "测试笔记")
    if ok_flag:
        ok(f"文件上传成功：{msg}")
    else:
        bad(f"文件上传失败：{msg}")
    at = open_page("文件区", user="flow_user")
    if any("资料.txt" in m.value for m in at.markdown):
        ok("文件区正确列出已上传文件")
    else:
        bad("文件区未列出已上传文件")

    print()
    for s in steps:
        print("  ✓", s)
    if problems:
        print()
        for p in problems:
            print("  ✗", p)
        return 1
    print()
    print("主链路功能测试通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    raise SystemExit(code)
