"""
Unit tests for flag serialization, ID validation, user_ipv4,
and random_home_path utilities.

Follows the mock pattern from test_discord_fixes.py — loads target modules
via importlib to avoid the heavy dojo_plugin dependency chain.
"""
import sys
import types
import importlib
import importlib.util
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers: load individual .py files without triggering package __init__.py
# ---------------------------------------------------------------------------

def _stub(name):
    """Register a stub module so imports of `name` don't fail."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules[name] = mod
    return sys.modules[name]


# Pre-import real packages so stubs don't shadow them
import sqlalchemy
import sqlalchemy.sql
import sqlalchemy.orm
import flask

# Stub the top-level packages/subpackages that would trigger heavy imports.
# sqlalchemy, flask, itsdangerous are installed and imported above.
for _pkg in [
    "dojo_plugin", "dojo_plugin.config", "dojo_plugin.models",
    "dojo_plugin.utils", "dojo_plugin.utils.dojo",
    "flask_restx",
    "CTFd", "CTFd.models", "CTFd.cache",
    "CTFd.utils", "CTFd.utils.decorators", "CTFd.utils.user",
    "CTFd.utils.modes", "CTFd.utils.config", "CTFd.utils.config.pages",
    "CTFd.utils.security", "CTFd.utils.security.sanitize",
    "docker", "bleach", "pytz",
]:
    _stub(_pkg)

sys.modules["CTFd.models"].db = MagicMock()
sys.modules["CTFd.models"].Challenges = MagicMock()
sys.modules["CTFd.models"].Solves = MagicMock()
sys.modules["CTFd.models"].Users = MagicMock()
sys.modules["CTFd.cache"].cache = MagicMock()
sys.modules["CTFd.cache"].cache.memoize = lambda **kw: (lambda f: f)
sys.modules["CTFd.utils.user"].get_current_user = MagicMock()
sys.modules["CTFd.utils.modes"].get_model = MagicMock()
sys.modules["CTFd.utils.config.pages"].build_markdown = MagicMock(return_value="<p>mock</p>")
sys.modules["CTFd.utils.security.sanitize"].sanitize_html = MagicMock(side_effect=lambda x: x)

sys.modules["flask"].current_app = MagicMock()
sys.modules["flask"].current_app.config = {"SECRET_KEY": "test-secret-key-for-unit-tests"}
sys.modules["flask"].g = MagicMock()
sys.modules["flask"].request = MagicMock()
sys.modules["flask"].session = MagicMock()
sys.modules["flask"].Markup = lambda x: x
sys.modules["flask"].Response = MagicMock()
sys.modules["flask"].abort = MagicMock()

sys.modules["dojo_plugin.models"].Dojos = MagicMock()
sys.modules["dojo_plugin.models"].DojoMembers = MagicMock()
sys.modules["dojo_plugin.models"].DojoAdmins = MagicMock()
sys.modules["dojo_plugin.models"].DojoChallenges = MagicMock()
sys.modules["dojo_plugin"].__path__ = []


def _load_module_from_file(mod_name, file_path):
    """Load a single .py file as a module, skipping __init__.py chains."""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load the target module
dojo_utils = _load_module_from_file(
    "dojo_plugin.utils",
    "dojo_plugin/utils/__init__.py",
)


# ===========================================================================
# Tests: id_regex
# ===========================================================================

class TestIdRegex:
    """Tests for id_regex: validates ^[A-Za-z0-9_.-]+$ and rejects '..'."""

    def test_simple_alphanumeric(self):
        assert dojo_utils.id_regex("hello123")

    def test_with_dots_and_dashes(self):
        assert dojo_utils.id_regex("my-id.v1_0")

    def test_with_underscore(self):
        assert dojo_utils.id_regex("hello_world")

    def test_rejects_double_dot(self):
        assert not dojo_utils.id_regex("hello..world")

    def test_rejects_spaces(self):
        assert not dojo_utils.id_regex("hello world")

    def test_rejects_slash(self):
        assert not dojo_utils.id_regex("hello/world")

    def test_rejects_backslash(self):
        assert not dojo_utils.id_regex("hello\\world")

    def test_rejects_special_chars(self):
        assert not dojo_utils.id_regex("hello@world")

    def test_empty_string(self):
        assert not dojo_utils.id_regex("")

    def test_only_dot(self):
        assert dojo_utils.id_regex(".")


# ===========================================================================
# Tests: serialize_user_flag / unserialize_user_flag
# ===========================================================================

TEST_SECRET = "test-secret-key-for-unit-tests"


class TestFlagSerialization:
    """Tests for serialize_user_flag and unserialize_user_flag."""

    def test_serialize_returns_string(self):
        result = dojo_utils.serialize_user_flag(1, 42, secret=TEST_SECRET)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_serialize_deterministic(self):
        a = dojo_utils.serialize_user_flag(1, 42, secret=TEST_SECRET)
        b = dojo_utils.serialize_user_flag(1, 42, secret=TEST_SECRET)
        assert a == b

    def test_serialize_different_accounts_different_flags(self):
        a = dojo_utils.serialize_user_flag(1, 42, secret=TEST_SECRET)
        b = dojo_utils.serialize_user_flag(2, 42, secret=TEST_SECRET)
        assert a != b

    def test_serialize_different_challenges_different_flags(self):
        a = dojo_utils.serialize_user_flag(1, 42, secret=TEST_SECRET)
        b = dojo_utils.serialize_user_flag(1, 99, secret=TEST_SECRET)
        assert a != b

    def test_serialize_different_secret_different_flags(self):
        a = dojo_utils.serialize_user_flag(1, 42, secret="secret-a")
        b = dojo_utils.serialize_user_flag(1, 42, secret="secret-b")
        assert a != b

    def test_unserialize_roundtrip(self):
        flag = dojo_utils.serialize_user_flag(7, 13, secret=TEST_SECRET)
        account_id, challenge_id = dojo_utils.unserialize_user_flag(
            flag, secret=TEST_SECRET
        )
        assert account_id == 7
        assert challenge_id == 13

    def test_unserialize_with_wrapper(self):
        flag = dojo_utils.serialize_user_flag(7, 13, secret=TEST_SECRET)
        wrapped = f"pwn.college{{{flag}}}"
        account_id, challenge_id = dojo_utils.unserialize_user_flag(
            wrapped, secret=TEST_SECRET
        )
        assert account_id == 7
        assert challenge_id == 13

    def test_unserialize_no_braces_raises(self):
        """Without {braces}, the regex won't extract anything, causing BadSignature."""
        from itsdangerous.exc import BadSignature
        flag = dojo_utils.serialize_user_flag(3, 5, secret=TEST_SECRET)
        raw = f"pwn.college{flag}"
        with pytest.raises(BadSignature):
            dojo_utils.unserialize_user_flag(raw, secret=TEST_SECRET)

    def test_roundtrip_large_ids(self):
        flag = dojo_utils.serialize_user_flag(99999, 88888, secret=TEST_SECRET)
        account_id, challenge_id = dojo_utils.unserialize_user_flag(
            flag, secret=TEST_SECRET
        )
        assert account_id == 99999
        assert challenge_id == 88888

    def test_serialize_not_empty(self):
        flag = dojo_utils.serialize_user_flag(0, 0, secret=TEST_SECRET)
        assert len(flag) > 0


# ===========================================================================
# Tests: user_ipv4
# ===========================================================================

class TestUserIpv4:
    """Tests for user_ipv4: computes IP from user ID in 10.114.0.0/16 subnet."""

    def test_user_1_ip(self):
        user = MagicMock()
        user.id = 1
        ip = dojo_utils.user_ipv4(user)
        assert ip == "10.114.1.1"

    def test_user_256_ip(self):
        user = MagicMock()
        user.id = 256
        ip = dojo_utils.user_ipv4(user)
        assert ip == "10.114.2.0"

    def test_ip_starts_with_10_114(self):
        user = MagicMock()
        user.id = 100
        ip = dojo_utils.user_ipv4(user)
        assert ip.startswith("10.114.")

    def test_ip_not_in_reserved_range(self):
        for uid in [1, 100, 1000, 10000]:
            user = MagicMock()
            user.id = uid
            ip = dojo_utils.user_ipv4(user)
            # Reserved: 10.114.0.0/24 and 10.114.255.0/24
            second_octet = int(ip.split(".")[2])
            assert second_octet != 0, f"UID {uid} got reserved IP {ip}"
            assert second_octet != 255, f"UID {uid} got reserved IP {ip}"

    def test_known_values(self):
        test_cases = [
            (1, "10.114.1.1"),
            (256, "10.114.2.0"),
            (257, "10.114.2.1"),
            (511, "10.114.2.255"),
            (512, "10.114.3.0"),
        ]
        for uid, expected in test_cases:
            user = MagicMock()
            user.id = uid
            assert dojo_utils.user_ipv4(user) == expected


# ===========================================================================
# Tests: random_home_path
# ===========================================================================

class TestRandomHomePath:
    """Tests for random_home_path: deterministic SHA256 hash of secret + user ID."""

    def test_returns_16_char_hex(self):
        user = MagicMock()
        user.id = 1
        path = dojo_utils.random_home_path(user, secret=TEST_SECRET)
        assert isinstance(path, str)
        assert len(path) == 16
        # Should be hex
        assert all(c in "0123456789abcdef" for c in path)

    def test_deterministic(self):
        user = MagicMock()
        user.id = 42
        a = dojo_utils.random_home_path(user, secret=TEST_SECRET)
        b = dojo_utils.random_home_path(user, secret=TEST_SECRET)
        assert a == b

    def test_different_users_different_paths(self):
        u1 = MagicMock()
        u1.id = 1
        u2 = MagicMock()
        u2.id = 2
        assert dojo_utils.random_home_path(u1, secret=TEST_SECRET) != \
               dojo_utils.random_home_path(u2, secret=TEST_SECRET)

    def test_different_secret_different_paths(self):
        user = MagicMock()
        user.id = 1
        a = dojo_utils.random_home_path(user, secret="secret-a")
        b = dojo_utils.random_home_path(user, secret="secret-b")
        assert a != b
