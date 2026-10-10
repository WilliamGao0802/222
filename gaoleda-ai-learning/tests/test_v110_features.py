"""v1.1.0 新增功能的单元测试。

覆盖：加密与会话令牌、手机号校验、管理员后台、头像、草稿箱、文件仓库与搜索引擎、数据库迁移。
测试数据全部重定向到临时目录，绝不污染 data/。

运行：
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import admin, auth, avatars, crypto, drafts, session, storage  # noqa: E402
from core import files as file_store  # noqa: E402
from core.config import ADMIN_USERNAMES, SESSION_DAYS  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="gaoleda_v110_"))

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000100ffff03000006000557bfabd4"
    "0000000049454e44ae426082"
)


def setUpModule() -> None:  # noqa: N802
    """把持久化路径与密钥路径全部重定向到临时目录。"""
    storage.DB_PATH = _TMP / "test.db"
    storage._initialized = False

    file_store.UPLOAD_DIR = _TMP / "uploads"
    file_store.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    avatars.AVATAR_DIR = _TMP / "avatars"
    avatars.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    avatars._CACHE.clear()

    crypto.SECRET_PATH = _TMP / ".secret"
    crypto._KEY = None


def tearDownModule() -> None:  # noqa: N802
    import shutil

    shutil.rmtree(_TMP, ignore_errors=True)


# ================================================================ 加密
class TestCrypto(unittest.TestCase):
    def test_roundtrip(self):
        for plain in ("123456", "abcXYZ🔐", "", "很长的一段密码" * 20):
            token = crypto.encrypt(plain)
            self.assertEqual(crypto.decrypt(token), plain)

    def test_ciphertext_differs_each_time(self):
        """同一明文两次加密结果不同（每次随机 nonce）。"""
        self.assertNotEqual(crypto.encrypt("123456"), crypto.encrypt("123456"))

    def test_tampered_ciphertext_rejected(self):
        token = crypto.encrypt("123456")
        broken = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        self.assertEqual(crypto.decrypt(broken), "")

    def test_garbage_rejected(self):
        for bad in ("", "not-base64!!", "YWJj"):
            self.assertEqual(crypto.decrypt(bad), "")

    def test_signature_verify(self):
        sig = crypto.sign("hello")
        self.assertTrue(crypto.verify_signature("hello", sig))
        self.assertFalse(crypto.verify_signature("hello!", sig))
        self.assertFalse(crypto.verify_signature("hello", "deadbeef"))


# ================================================================ 会话令牌
class TestSessionToken(unittest.TestCase):
    def test_issue_and_verify(self):
        token = session.issue("William", 3)
        self.assertEqual(session.verify(token), ("William", 3))

    def test_empty_username_rejected(self):
        self.assertEqual(session.issue(""), "")

    def test_tampered_username_rejected(self):
        token = session.issue("alice", 0)
        encoded, issued, epoch, sig = token.split("|")
        forged = "|".join((session._encode_name("bob"), issued, epoch, sig))
        self.assertIsNone(session.verify(forged))

    def test_tampered_epoch_rejected(self):
        token = session.issue("alice", 0)
        encoded, issued, _, sig = token.split("|")
        self.assertIsNone(session.verify("|".join((encoded, issued, "7", sig))))

    def test_malformed_tokens_rejected(self):
        for bad in ("", "a|b", "a|b|c", "a|b|c|d|e", "onlyname"):
            self.assertIsNone(session.verify(bad))

    def test_non_numeric_issued_rejected(self):
        encoded, _, epoch, sig = session.issue("alice", 0).split("|")
        self.assertIsNone(session.verify("|".join((encoded, "abc", epoch, sig))))

    def test_future_token_rejected(self):
        import time

        issued = int(time.time()) + 9999
        token = "|".join((
            session._encode_name("alice"), str(issued), "0",
            crypto.sign(f"alice\n{issued}\n0"),
        ))
        self.assertIsNone(session.verify(token))

    def test_cookie_roundtrip(self):
        """令牌经浏览器 Cookie → 标准库 SimpleCookie 往返后仍能校验通过。

        回归背景：曾经在写 Cookie 时用 encodeURIComponent，`|` 变成 `%7C`，
        SimpleCookie 不解码导致刷新后永远登录不上。
        """
        from http.cookies import SimpleCookie

        for name in ("William", "e2e_login_user", "张三丰", "a-b_c.9"):
            with self.subTest(name=name):
                token = session.issue(name, 2)
                jar = SimpleCookie()
                jar.load(f"gaoleda_session={token}")
                read_back = jar["gaoleda_session"].value
                self.assertEqual(read_back, token)
                self.assertEqual(session.verify(read_back), (name, 2))

    def test_token_is_cookie_safe_ascii(self):
        """令牌本身必须是纯 ASCII，且不含 Cookie 分隔符（保证原样往返）。"""
        token = session.issue("张三丰·测试", 1)
        self.assertTrue(token.isascii())
        for ch in ' ;,\t\r\n"\\':
            self.assertNotIn(ch, token)
        self.assertNotIn("=", token)

    def test_max_age_matches_config(self):
        self.assertEqual(session.max_age(), SESSION_DAYS * 86400)


# ================================================================ 会话世代号
class TestSessionEpoch(unittest.TestCase):
    """退出登录 → 旧令牌立即失效（服务端确定性，不依赖浏览器删 Cookie）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_db = storage.DB_PATH
        storage.DB_PATH = Path(self.tmp.name) / "app.db"
        storage._initialized = False
        with storage.db():          # 打开一次连接即触发建表
            pass

    def tearDown(self):
        storage.DB_PATH = self._old_db
        storage._initialized = False
        self.tmp.cleanup()

    def test_default_epoch_is_zero(self):
        ok, _ = auth.register("epoch_user", "123456", "13800000001")
        self.assertTrue(ok)
        self.assertEqual(auth.session_epoch("epoch_user"), 0)

    def test_bump_increments(self):
        auth.register("epoch_user", "123456", "13800000001")
        self.assertEqual(auth.bump_session_epoch("epoch_user"), 1)
        self.assertEqual(auth.bump_session_epoch("epoch_user"), 2)
        self.assertEqual(auth.session_epoch("epoch_user"), 2)

    def test_epoch_of_unknown_user_is_none(self):
        self.assertIsNone(auth.session_epoch("nobody"))
        self.assertEqual(auth.bump_session_epoch("nobody"), 0)

    def test_old_token_dies_after_logout(self):
        auth.register("epoch_user", "123456", "13800000001")
        token = session.issue("epoch_user", auth.session_epoch("epoch_user"))
        self.assertIsNotNone(session.verify(token))
        auth.bump_session_epoch("epoch_user")          # 等价于退出登录
        name, epoch = session.verify(token)
        self.assertNotEqual(auth.session_epoch(name), epoch)

    def test_new_token_survives_after_relogin(self):
        auth.register("epoch_user", "123456", "13800000001")
        auth.bump_session_epoch("epoch_user")
        token = session.issue("epoch_user", auth.session_epoch("epoch_user"))
        name, epoch = session.verify(token)
        self.assertEqual(auth.session_epoch(name), epoch)


# ================================================================ 手机号
class TestPhoneValidation(unittest.TestCase):
    def test_accepts_valid(self):
        for good in ("13800000000", "19912345678", "15012345678", "18888888888"):
            ok, msg = auth.validate_phone(good)
            self.assertTrue(ok, f"{good} 应通过：{msg}")

    def test_rejects_empty(self):
        ok, msg = auth.validate_phone("")
        self.assertFalse(ok)
        self.assertIn("手机号", msg)

    def test_rejects_wrong_length(self):
        self.assertFalse(auth.validate_phone("1380000000")[0])
        self.assertFalse(auth.validate_phone("138000000000")[0])

    def test_rejects_bad_prefix(self):
        self.assertFalse(auth.validate_phone("12800000000")[0])
        self.assertFalse(auth.validate_phone("10800000000")[0])

    def test_rejects_non_digits(self):
        for bad in ("1380000000a", "138 0000 0000", "+8613800000000", "１３８００００００００"):
            self.assertFalse(auth.validate_phone(bad)[0], bad)


# ================================================================ 管理员
class TestAdminConsole(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()
        for path in file_store.UPLOAD_DIR.glob("*"):
            path.unlink()
        auth.register("William", "888888", "13800000000")
        auth.register("member", "123456", "13900000000")
        # 给 member 造点内容，用来验证级联删除
        discussion_post = __import__("core.discussion", fromlist=["add_post"])
        self.post_id = discussion_post.add_post("member", "这是一条测试发言", "大模型")[0]
        discussion_post.toggle_like(self.post_id, "William")
        discussion_post.toggle_follow("William", "member")
        file_store.save_upload("member", "note.md", b"hello", "笔记", "文章")
        drafts.save_draft("member", "半截草稿", "综合")

    def test_reserved_name_gets_admin_role(self):
        self.assertTrue(admin.is_admin("William"))
        self.assertFalse(admin.is_admin("member"))

    def test_admin_usernames_config_not_empty(self):
        self.assertIn("william", ADMIN_USERNAMES)

    def test_sync_admin_roles_promotes_legacy_account(self):
        with storage.db() as conn:
            conn.execute("UPDATE users SET role = 'member' WHERE username = 'William'")
        self.assertFalse(admin.is_admin("William"))
        admin.sync_admin_roles()
        self.assertTrue(admin.is_admin("William"))

    def test_member_list_exposes_decrypted_password(self):
        rows = {m["username"]: m for m in admin.list_members()}
        self.assertEqual(rows["William"]["password"], "888888")
        self.assertEqual(rows["member"]["password"], "123456")
        self.assertEqual(rows["member"]["phone"], "13900000000")

        # 落库的是密文而非明文，且能被正确解密
        with storage.db() as conn:
            stored = conn.execute(
                "SELECT password_enc FROM users WHERE username = 'William'"
            ).fetchone()["password_enc"]
        self.assertNotIn("888888", stored)
        self.assertEqual(crypto.decrypt(stored), "888888")

    def test_member_list_keyword_filter(self):
        self.assertEqual([m["username"] for m in admin.list_members("13900000000")], ["member"])
        self.assertEqual([m["username"] for m in admin.list_members("will")], ["William"])
        self.assertEqual(admin.list_members("不存在"), [])

    def test_stats(self):
        stats = admin.stats()
        self.assertEqual(stats["members"], 2)
        self.assertEqual(stats["admins"], 1)
        self.assertEqual(stats["posts"], 1)
        self.assertEqual(stats["files"], 1)
        self.assertEqual(stats["drafts"], 1)

    def test_non_admin_cannot_delete(self):
        ok, msg = admin.delete_member("member", "William")
        self.assertFalse(ok)
        self.assertIn("管理员", msg)
        self.assertTrue(auth.user_exists("William"))

    def test_cannot_delete_self(self):
        ok, _ = admin.delete_member("William", "William")
        self.assertFalse(ok)

    def test_cannot_delete_admin(self):
        auth.register("William2", "888888", "13800000001")
        with storage.db() as conn:
            conn.execute("UPDATE users SET role = 'admin' WHERE username = 'William2'")
        ok, msg = admin.delete_member("William", "William2")
        self.assertFalse(ok)
        self.assertIn("管理员", msg)

    def test_delete_member_cascades(self):
        self.assertTrue(admin.delete_member("William", "member")[0])
        self.assertFalse(auth.user_exists("member"))
        with storage.db() as conn:
            for table in ("posts", "likes", "follows", "files", "drafts"):
                left = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table}"  # noqa: S608  表名来自固定白名单
                ).fetchone()["c"]
                self.assertEqual(left, 0, f"{table} 未被级联清理")
        self.assertEqual(list(file_store.UPLOAD_DIR.glob("*")), [])

    def test_reset_member_password(self):
        ok, msg = admin.reset_member_password("William", "member", "654321")
        self.assertTrue(ok, msg)
        self.assertTrue(auth.login("member", "654321")[0])

    def test_reset_password_needs_admin_and_valid_format(self):
        self.assertFalse(admin.reset_member_password("member", "William", "111111")[0])
        self.assertFalse(admin.reset_member_password("William", "member", "abc")[0])

    def test_delete_missing_member(self):
        self.assertFalse(admin.delete_member("William", "ghost")[0])


# ================================================================ 头像
class TestAvatars(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()
        avatars._CACHE.clear()
        auth.register("avatar_user", "123456", "13700000000")

    def test_save_and_read(self):
        ok, msg = avatars.save_avatar("avatar_user", "me.png", _PNG)
        self.assertTrue(ok, msg)
        uri = avatars.avatar_data_uri("avatar_user")
        self.assertTrue(uri.startswith("data:image/png;base64,"))

    def test_replacing_removes_old_file(self):
        avatars.save_avatar("avatar_user", "a.png", _PNG)
        first = avatars.avatar_file("avatar_user")
        avatars.save_avatar("avatar_user", "b.jpg", _PNG)
        second = avatars.avatar_file("avatar_user")
        self.assertNotEqual(first, second)
        self.assertFalse((avatars.AVATAR_DIR / first).exists())

    def test_clear_restores_default(self):
        avatars.save_avatar("avatar_user", "a.png", _PNG)
        self.assertTrue(avatars.clear_avatar("avatar_user")[0])
        self.assertEqual(avatars.avatar_data_uri("avatar_user"), "")

    def test_rejects_oversize(self):
        ok, msg = avatars.save_avatar("avatar_user", "big.png", b"0" * 400 * 1024)
        self.assertFalse(ok)
        self.assertIn("过大", msg)

    def test_rejects_bad_suffix_and_empty(self):
        self.assertFalse(avatars.save_avatar("avatar_user", "x.txt", _PNG)[0])
        self.assertFalse(avatars.save_avatar("avatar_user", "x.png", b"")[0])

    def test_requires_login_and_existing_user(self):
        self.assertFalse(avatars.save_avatar("", "x.png", _PNG)[0])
        self.assertFalse(avatars.save_avatar("ghost", "x.png", _PNG)[0])

    def test_missing_file_returns_blank(self):
        avatars.save_avatar("avatar_user", "a.png", _PNG)
        (avatars.AVATAR_DIR / avatars.avatar_file("avatar_user")).unlink()
        avatars._CACHE.clear()
        self.assertEqual(avatars.avatar_data_uri("avatar_user"), "")


# ================================================================ 草稿箱
class TestDrafts(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()

    def test_save_update_list(self):
        ok, msg, did = drafts.save_draft("alice", "第一版", "大模型")
        self.assertTrue(ok, msg)
        ok, msg, same = drafts.save_draft("alice", "第二版", "智能体", did)
        self.assertTrue(ok)
        self.assertEqual(same, did)
        rows = drafts.list_drafts("alice")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "第二版")
        self.assertEqual(rows[0]["topic"], "智能体")

    def test_empty_and_oversize_rejected(self):
        self.assertFalse(drafts.save_draft("alice", "   ")[0])
        self.assertFalse(drafts.save_draft("alice", "字" * 501)[0])

    def test_unknown_topic_falls_back(self):
        _, _, did = drafts.save_draft("alice", "内容", "不存在的话题")
        self.assertEqual(drafts.get_draft(did, "alice")["topic"], "综合")

    def test_isolation_between_users(self):
        _, _, did = drafts.save_draft("alice", "私有草稿", "综合")
        self.assertIsNone(drafts.get_draft(did, "bob"))
        self.assertFalse(drafts.delete_draft(did, "bob")[0])
        self.assertEqual(drafts.list_drafts("bob"), [])

    def test_requires_login(self):
        self.assertFalse(drafts.save_draft("", "内容")[0])
        self.assertFalse(drafts.count_drafts("") == 1)

    def test_delete_and_clear(self):
        _, _, first = drafts.save_draft("alice", "A", "综合")
        drafts.save_draft("alice", "B", "综合")
        self.assertTrue(drafts.delete_draft(first, "alice")[0])
        self.assertEqual(drafts.count_drafts("alice"), 1)
        self.assertTrue(drafts.clear_drafts("alice")[0])
        self.assertEqual(drafts.count_drafts("alice"), 0)

    def test_delete_missing_draft(self):
        self.assertFalse(drafts.delete_draft(9999, "alice")[0])


# ================================================================ 文件仓库与搜索
class TestFileReposAndSearch(unittest.TestCase):
    def setUp(self):
        storage.reset_for_tests()
        with storage.db() as conn:
            conn.execute("DELETE FROM files")
        for name in file_store.UPLOAD_DIR.glob("*"):
            name.unlink()

        file_store.save_upload("alice", "transformer论文笔记.md", b"x" * 300, "Transformer 精读", "文章")
        file_store.save_upload("alice", "two-sum题解.py", b"y" * 100, "双指针解法", "题解")
        file_store.save_upload("bob", "快速排序.cpp", b"z" * 200, "分治算法", "算法")
        file_store.save_upload("bob", "英语语法总结.pdf", b"w" * 400, "时态笔记", "语法")

    def test_repo_counts(self):
        counts = file_store.repo_counts()
        self.assertEqual(counts["文章"], 1)
        self.assertEqual(counts["题解"], 1)
        self.assertEqual(counts["算法"], 1)
        self.assertEqual(counts["语法"], 1)

    def test_invalid_repo_falls_back_to_default(self):
        self.assertEqual(file_store.normalize_repo("不存在"), file_store.normalize_repo(""))

    def test_code_suffixes_allowed(self):
        ok, msg = file_store.save_upload("alice", "solution.java", b"code", "", "题解")
        self.assertTrue(ok, msg)

    def test_search_single_keyword(self):
        found = [f["filename"] for f in file_store.search_files("论文")]
        self.assertEqual(found, ["transformer论文笔记.md"])

    def test_search_multi_keyword_is_and(self):
        self.assertEqual(len(file_store.search_files("论文 transformer")), 1)
        self.assertEqual(file_store.search_files("论文 不存在"), [])

    def test_search_scope_filename(self):
        self.assertEqual(
            [f["filename"] for f in file_store.search_files("语法", scope="filename")],
            ["英语语法总结.pdf"],
        )
        self.assertEqual(file_store.search_files("双指针", scope="filename"), [])

    def test_search_scope_note_and_uploader(self):
        self.assertEqual(
            [f["filename"] for f in file_store.search_files("双指针", scope="note")],
            ["two-sum题解.py"],
        )
        self.assertEqual(len(file_store.search_files("bob", scope="uploader")), 2)

    def test_search_by_repo(self):
        self.assertEqual(
            [f["filename"] for f in file_store.search_files(repo="文章")],
            ["transformer论文笔记.md"],
        )
        self.assertEqual(len(file_store.search_files(repo="题解")), 1)

    def test_search_all_repos_returns_everything(self):
        from core.config import ALL_REPOS

        self.assertEqual(len(file_store.search_files(repo=ALL_REPOS)), 4)

    def test_ordering(self):
        by_name = [f["filename"] for f in file_store.search_files(order="name")]
        self.assertEqual(by_name, sorted(by_name, key=str.lower))
        by_size = [f["size"] for f in file_store.search_files(order="size")]
        self.assertEqual(by_size, sorted(by_size, reverse=True))
        by_old = [f["filename"] for f in file_store.search_files(order="old")]
        by_new = [f["filename"] for f in file_store.search_files(order="new")]
        self.assertEqual(by_old, list(reversed(by_new)))

    def test_search_restricted_to_user(self):
        self.assertEqual(len(file_store.search_files(username="bob")), 2)

    def test_empty_keyword_returns_all(self):
        self.assertEqual(len(file_store.search_files()), 4)

    def test_delete_only_own_file(self):
        target = file_store.search_files("论文")[0]["id"]
        self.assertFalse(file_store.delete_file(target, "bob")[0])
        self.assertTrue(file_store.delete_file(target, "alice")[0])


# ================================================================ 数据库迁移
class TestStorageMigration(unittest.TestCase):
    def test_new_columns_present(self):
        with storage.db() as conn:
            users = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
            files = {r["name"] for r in conn.execute("PRAGMA table_info(files)")}
        self.assertTrue(
            {"role", "phone", "avatar", "password_enc", "session_epoch"} <= users
        )
        self.assertIn("repo", files)

    def test_drafts_table_present(self):
        with storage.db() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='drafts'"
            ).fetchone()
        self.assertIsNotNone(row)

    def test_migration_adds_missing_column(self):
        """模拟老库：删掉列后再跑迁移，应被补回来。"""
        import sqlite3

        legacy = _TMP / "legacy.db"
        conn = sqlite3.connect(str(legacy))
        conn.execute(
            "CREATE TABLE users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, "
            "created_at TEXT NOT NULL, last_login TEXT, bio TEXT NOT NULL DEFAULT '')"
        )
        conn.execute(
            "CREATE TABLE files (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, "
            "filename TEXT NOT NULL, stored_name TEXT NOT NULL, size INTEGER NOT NULL DEFAULT 0, "
            "note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)"
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        storage._migrate(conn)
        users = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        files = {r["name"] for r in conn.execute("PRAGMA table_info(files)")}
        conn.close()
        self.assertTrue(
            {"role", "phone", "avatar", "password_enc", "session_epoch"} <= users
        )
        self.assertIn("repo", files)


if __name__ == "__main__":
    unittest.main()
