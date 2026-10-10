"""core 层单元测试（不依赖 streamlit，可离线运行）。

运行：
    python -m unittest discover -s tests -v
测试数据全部写入临时目录，绝不污染 data/。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import auth, discussion, news, storage  # noqa: E402
from core import files as file_store  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="gaoleda_test_"))


def setUpModule() -> None:  # noqa: N802
    """把持久化路径重定向到临时目录。"""
    storage.DB_PATH = _TMP / "test.db"
    storage._initialized = False
    file_store.UPLOAD_DIR = _TMP / "uploads"
    file_store.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    news.NEWS_CACHE_PATH = _TMP / "news_cache.json"


def tearDownModule() -> None:  # noqa: N802
    import shutil

    shutil.rmtree(_TMP, ignore_errors=True)


class TestPasswordValidation(unittest.TestCase):
    def test_accepts_exactly_six_ascii_digits(self):
        ok, msg = auth.validate_password("123456")
        self.assertTrue(ok, msg)

    def test_rejects_empty(self):
        ok, msg = auth.validate_password("")
        self.assertFalse(ok)
        self.assertIn("不能为空", msg)

    def test_rejects_too_short(self):
        ok, msg = auth.validate_password("12345")
        self.assertFalse(ok)
        self.assertIn("6", msg)

    def test_rejects_too_long(self):
        ok, _ = auth.validate_password("1234567")
        self.assertFalse(ok)

    def test_rejects_letters(self):
        ok, msg = auth.validate_password("12a456")
        self.assertFalse(ok)
        self.assertIn("数字", msg)

    def test_rejects_fullwidth_digits(self):
        ok, _ = auth.validate_password("１２３４５６")
        self.assertFalse(ok)

    def test_rejects_whitespace_and_symbols(self):
        for bad in ("123 56", "12345!", "  1234"):
            ok, _ = auth.validate_password(bad)
            self.assertFalse(ok, f"{bad!r} 不应通过校验")


class TestUsernameValidation(unittest.TestCase):
    def test_accepts_normal(self):
        ok, _ = auth.validate_username("gaoleda")
        self.assertTrue(ok)

    def test_accepts_chinese(self):
        ok, _ = auth.validate_username("高乐达")
        self.assertTrue(ok)

    def test_rejects_empty_and_whitespace(self):
        for bad in ("", "   "):
            ok, _ = auth.validate_username(bad)
            self.assertFalse(ok)

    def test_rejects_too_short_and_too_long(self):
        self.assertFalse(auth.validate_username("a")[0])
        self.assertFalse(auth.validate_username("a" * 21)[0])

    def test_rejects_special_chars(self):
        for bad in ("a b", "a@b", "a/b"):
            self.assertFalse(auth.validate_username(bad)[0], bad)


class TestAuthFlow(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()

    def test_register_then_login(self):
        ok, msg = auth.register("alice", "123456")
        self.assertTrue(ok, msg)
        self.assertEqual(auth.user_count(), 1)

        ok, msg = auth.login("alice", "123456")
        self.assertTrue(ok, msg)

    def test_register_duplicate_username(self):
        auth.register("bob", "111111")
        ok, msg = auth.register("bob", "222222")
        self.assertFalse(ok)
        self.assertIn("已被注册", msg)
        self.assertEqual(auth.user_count(), 1)

    def test_login_wrong_password(self):
        auth.register("carol", "123456")
        ok, msg = auth.login("carol", "654321")
        self.assertFalse(ok)
        self.assertIn("密码错误", msg)

    def test_login_unknown_user(self):
        ok, msg = auth.login("nobody", "123456")
        self.assertFalse(ok)
        self.assertIn("用户不存在", msg)

    def test_register_rejects_bad_password(self):
        ok, msg = auth.register("dave", "abcdef")
        self.assertFalse(ok)
        self.assertEqual(auth.user_count(), 0)

    def test_password_not_stored_in_plaintext(self):
        auth.register("erin", "123456")
        with storage.db() as conn:
            stored = conn.execute(
                "SELECT password_hash FROM users WHERE username = 'erin'"
            ).fetchone()["password_hash"]
        self.assertNotIn("123456", stored)
        self.assertIn("$", stored)

    def test_user_limit_enforced(self):
        original = auth.MAX_USERS
        auth.MAX_USERS = 2
        try:
            self.assertTrue(auth.register("u1", "123456")[0])
            self.assertTrue(auth.register("u2", "123456")[0])
            ok, msg = auth.register("u3", "123456")
            self.assertFalse(ok)
            self.assertIn("上限", msg)
            self.assertEqual(auth.remaining_slots(), 0)
        finally:
            auth.MAX_USERS = original

    def test_change_password(self):
        auth.register("frank", "123456")
        ok, msg = auth.change_password("frank", "000000", "654321")
        self.assertFalse(ok)
        ok, msg = auth.change_password("frank", "123456", "654321")
        self.assertTrue(ok, msg)
        self.assertTrue(auth.login("frank", "654321")[0])
        self.assertFalse(auth.login("frank", "123456")[0])

    def test_set_bio(self):
        auth.register("gina", "123456")
        ok, _ = auth.set_bio("gina", "AI 学习者")
        self.assertTrue(ok)
        self.assertEqual(auth.get_user("gina")["bio"], "AI 学习者")


class TestDiscussion(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()
        auth.register("host", "123456")
        auth.register("guest", "123456")

    def test_add_post_requires_login_and_content(self):
        self.assertFalse(discussion.add_post("", "hi")[0])
        self.assertFalse(discussion.add_post("host", "   ")[0])
        self.assertTrue(discussion.add_post("host", "第一条发言")[0])
        self.assertEqual(discussion.count_posts(), 1)

    def test_post_length_limit(self):
        ok, msg = discussion.add_post("host", "字" * 501)
        self.assertFalse(ok)
        self.assertIn("过长", msg)

    def test_like_toggle(self):
        discussion.add_post("host", "hello")
        post_id = discussion.list_posts()[0]["id"]

        ok, msg, count = discussion.toggle_like(post_id, "guest")
        self.assertTrue(ok)
        self.assertEqual(count, 1)

        ok, msg, count = discussion.toggle_like(post_id, "guest")
        self.assertTrue(ok)
        self.assertEqual(count, 0)

    def test_like_requires_login(self):
        discussion.add_post("host", "hello")
        post_id = discussion.list_posts()[0]["id"]
        ok, msg, _ = discussion.toggle_like(post_id, "")
        self.assertFalse(ok)

    def test_list_posts_reflects_viewer_state(self):
        discussion.add_post("host", "hello")
        post_id = discussion.list_posts()[0]["id"]
        discussion.toggle_like(post_id, "guest")

        as_guest = discussion.list_posts(viewer="guest")[0]
        self.assertTrue(as_guest["liked_by_me"])
        self.assertEqual(as_guest["like_count"], 1)

        as_host = discussion.list_posts(viewer="host")[0]
        self.assertFalse(as_host["liked_by_me"])

    def test_follow_toggle_and_self_guard(self):
        ok, msg, state = discussion.toggle_follow("guest", "guest")
        self.assertFalse(ok)

        ok, msg, state = discussion.toggle_follow("guest", "host")
        self.assertTrue(ok)
        self.assertTrue(state)
        self.assertIn("host", discussion.following_of("guest"))
        self.assertIn("guest", discussion.followers_of("host"))
        self.assertTrue(discussion.is_following("guest", "host"))

        ok, msg, state = discussion.toggle_follow("guest", "host")
        self.assertTrue(ok)
        self.assertFalse(state)
        self.assertEqual(discussion.following_of("guest"), [])

    def test_delete_post_only_by_owner(self):
        discussion.add_post("host", "hello")
        pid = discussion.list_posts()[0]["id"]
        self.assertFalse(discussion.delete_post(pid, "guest")[0])
        self.assertTrue(discussion.delete_post(pid, "host")[0])
        self.assertEqual(discussion.count_posts(), 0)

    def test_active_users_board(self):
        discussion.add_post("host", "a")
        discussion.add_post("host", "b")
        board = discussion.active_users(5)
        self.assertEqual(board[0]["username"], "host")
        self.assertEqual(board[0]["posts"], 2)


class TestFiles(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()
        auth.register("uploader", "123456")

    def test_save_and_list(self):
        ok, msg = file_store.save_upload("uploader", "note.txt", b"hello world", "笔记")
        self.assertTrue(ok, msg)
        items = file_store.list_files()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["filename"], "note.txt")
        self.assertEqual(items[0]["size"], 11)
        self.assertTrue(items[0]["path"].exists())

    def test_rejects_bad_extension(self):
        ok, msg = file_store.save_upload("uploader", "virus.exe", b"MZ")
        self.assertFalse(ok)
        self.assertIn("不支持", msg)

    def test_rejects_empty_file(self):
        ok, msg = file_store.save_upload("uploader", "empty.txt", b"")
        self.assertFalse(ok)

    def test_rejects_oversize(self):
        big = b"x" * (file_store.MAX_UPLOAD_MB * 1024 * 1024 + 1)
        ok, msg = file_store.save_upload("uploader", "big.txt", big)
        self.assertFalse(ok)
        self.assertIn("过大", msg)

    def test_path_traversal_is_neutralised(self):
        ok, _ = file_store.save_upload("uploader", "../../../etc/passwd.txt", b"x")
        self.assertTrue(ok)
        stored = file_store.list_files()[0]["path"]
        self.assertEqual(stored.parent.resolve(), file_store.UPLOAD_DIR.resolve())

    def test_delete_only_by_owner(self):
        file_store.save_upload("uploader", "a.txt", b"x")
        fid = file_store.list_files()[0]["id"]
        self.assertFalse(file_store.delete_file(fid, "other")[0])
        self.assertTrue(file_store.delete_file(fid, "uploader")[0])
        self.assertEqual(file_store.count_files(), 0)

    def test_human_size(self):
        self.assertEqual(file_store.human_size(512), "512 B")
        self.assertEqual(file_store.human_size(2048), "2.0 KB")


class TestNews(unittest.TestCase):
    def test_clean_strips_tags_and_entities(self):
        out = news._clean("<p>Hello &amp; <b>world</b></p>")
        self.assertEqual(out, "Hello & world")

    def test_clean_truncates(self):
        out = news._clean("x" * 500, limit=50)
        self.assertTrue(out.endswith("…"))
        self.assertEqual(len(out), 50)

    def test_parse_date_variants(self):
        self.assertIsNotNone(news._parse_date("Wed, 08 Oct 2026 10:00:00 GMT"))
        self.assertIsNotNone(news._parse_date("2026-10-08T10:00:00Z"))
        self.assertIsNone(news._parse_date("not a date"))

    def test_parse_feed_rss(self):
        raw = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item>
            <title>Test Item</title>
            <link>https://example.com/a</link>
            <description>&lt;p&gt;Body text&lt;/p&gt;</description>
            <pubDate>Wed, 08 Oct 2026 10:00:00 GMT</pubDate>
          </item>
        </channel></rss>"""
        items = news._parse_feed(raw, "测试源")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Test Item")
        self.assertEqual(items[0]["link"], "https://example.com/a")
        self.assertEqual(items[0]["published"], "2026-10-08")
        self.assertEqual(items[0]["source"], "测试源")

    def test_parse_feed_atom(self):
        raw = b"""<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Atom Item</title>
            <link href="https://example.com/b"/>
            <summary>Summary</summary>
            <updated>2026-09-01T00:00:00Z</updated>
          </entry>
        </feed>"""
        items = news._parse_feed(raw, "Atom源")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["published"], "2026-09-01")

    def test_parse_feed_broken_xml_returns_empty(self):
        self.assertEqual(news._parse_feed(b"<rss", "坏源"), [])

    def test_fallback_has_five_items(self):
        items = news._fallback(5)
        self.assertEqual(len(items), 5)
        for item in items:
            self.assertTrue(item["title"])
            self.assertTrue(item["link"].startswith("http"))
            self.assertTrue(item["fallback"])

    def test_fetch_news_is_resilient(self):
        """即使所有外网信源都不可达，也必须返回 5 条可用内容。"""
        original = news.FEEDS
        news.FEEDS = [{"name": "不存在", "url": "http://127.0.0.1:9/none.xml"}]
        try:
            news.NEWS_CACHE_PATH.unlink(missing_ok=True)
            data = news.fetch_news(5, force=True)
            self.assertEqual(len(data["items"]), 5)
            self.assertFalse(data["live"])
            self.assertTrue(data["note"])
        finally:
            news.FEEDS = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
