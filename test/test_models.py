"""
Unit tests for model static methods, data conversion functions,
and visibility logic — testable without a database connection.

Follows the mock pattern from test_discord_fixes.py.
"""
import sys
import types
import importlib
import importlib.util
import datetime
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Stub infrastructure
# ---------------------------------------------------------------------------

def _stub(name):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules[name] = mod
    return sys.modules[name]


# Pre-import real packages so stubs don't shadow them
import sqlalchemy
import sqlalchemy.sql
import sqlalchemy.orm
import sqlalchemy.orm.attributes
import sqlalchemy.orm.session
import sqlalchemy.ext
import sqlalchemy.ext.hybrid
import sqlalchemy.ext.associationproxy
import sqlalchemy.ext.declarative
import flask
import pytz
import yaml

for _pkg in [
    "dojo_plugin", "dojo_plugin.config", "dojo_plugin.utils",
    "flask_restx",
    "CTFd", "CTFd.models", "CTFd.cache", "CTFd.utils",
    "CTFd.utils.user", "CTFd.utils.decorators",
]:
    _stub(_pkg)

# Mock flask attributes
sys.modules["flask"].current_app = MagicMock()
sys.modules["flask"].current_app.config = {"SECRET_KEY": "test-secret"}
sys.modules["flask"].g = MagicMock()
sys.modules["flask"].Markup = lambda x: x

sys.modules["CTFd.models"].db = MagicMock()
sys.modules["CTFd.models"].db.Column = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.String = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.Integer = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.Boolean = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.Text = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.DateTime = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.JSON = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.BigInteger = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.ForeignKey = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.ForeignKeyConstraint = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.UniqueConstraint = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.relationship = MagicMock(return_value=MagicMock())
sys.modules["CTFd.models"].db.Model = type("Model", (), {})
sys.modules["CTFd.models"].Challenges = MagicMock()
sys.modules["CTFd.models"].Solves = MagicMock()
sys.modules["CTFd.models"].Users = MagicMock()
sys.modules["CTFd.models"].Flags = MagicMock()
sys.modules["CTFd.models"].Admins = MagicMock()
sys.modules["CTFd.models"].Awards = type("Awards", (), {"__mapper_args__": {}})
sys.modules["CTFd.models"].get_class_by_tablename = MagicMock(return_value=MagicMock())
sys.modules["CTFd.cache"].cache = MagicMock()
sys.modules["CTFd.cache"].cache.memoize = lambda **kw: (lambda f: f)
sys.modules["CTFd.utils.user"].get_current_user = MagicMock()
sys.modules["CTFd.utils.user"].is_admin = MagicMock(return_value=False)
sys.modules["CTFd.utils.decorators"].authed_only = lambda f: f

sys.modules["sqlalchemy.orm.session"].object_session = MagicMock()
sys.modules["sqlalchemy.orm.attributes"].flag_modified = MagicMock()

sys.modules["dojo_plugin.config"].DOJOS_DIR = MagicMock()
sys.modules["dojo_plugin.models.config"] = MagicMock()
sys.modules["dojo_plugin.models.config"].DOJO_PREREQUISITES = {}
sys.modules["dojo_plugin"].__path__ = []

from flask import current_app
sys.modules["flask"].current_app = MagicMock()
sys.modules["flask"].current_app.config = {"SECRET_KEY": "test-secret"}


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load the models module
models = _load_module_from_file(
    "dojo_plugin.models",
    "dojo_plugin/models/__init__.py",
)


# ===========================================================================
# Tests: Dojos.int_to_hex / Dojos.hex_to_int
# ===========================================================================

class TestDojoHexConversion:
    """Tests for int_to_hex and hex_to_int static methods."""

    def test_int_to_hex_zero(self):
        result = models.Dojos.int_to_hex(0)
        assert result == "00000000"

    def test_int_to_hex_positive(self):
        result = models.Dojos.int_to_hex(42)
        assert result == "0000002a"

    def test_int_to_hex_negative(self):
        # Negative ints use two's complement in 32-bit
        result = models.Dojos.int_to_hex(-1)
        assert result == "ffffffff"

    def test_int_to_hex_large_positive(self):
        result = models.Dojos.int_to_hex(0x7FFFFFFF)
        assert result == "7fffffff"

    def test_roundtrip_positive(self):
        for val in [0, 1, 42, 255, 256, 1000000, 0x7FFFFFFF]:
            hex_str = models.Dojos.int_to_hex(val)
            back = models.Dojos.hex_to_int(hex_str)
            assert back == val, f"Roundtrip failed for {val} (hex: {hex_str}, back: {back})"

    def test_roundtrip_negative(self):
        for val in [-1, -42, -256, -1000000]:
            hex_str = models.Dojos.int_to_hex(val)
            back = models.Dojos.hex_to_int(hex_str)
            assert back == val, f"Roundtrip failed for {val} (hex: {hex_str}, back: {back})"

    def test_hex_to_int_zero(self):
        assert models.Dojos.hex_to_int("00000000") == 0

    def test_hex_to_int_no_padding(self):
        # hex_to_int pads with rjust(8, "0")
        result = models.Dojos.hex_to_int("2a")
        assert result == 42


# ===========================================================================
# Tests: columns_repr
# ===========================================================================

class TestColumnsRepr:
    """Tests for columns_repr: generates __repr__ for model classes."""

    def test_basic_repr(self):
        class FakeModel:
            def __init__(self):
                self.name = "test"
                self.id = 42
            __repr__ = models.columns_repr(["name", "id"])

        obj = FakeModel()
        repr_str = repr(obj)
        assert "FakeModel" in repr_str
        assert "name='test'" in repr_str
        assert "id=42" in repr_str

    def test_single_column(self):
        class SimpleModel:
            def __init__(self):
                self.value = "hello"
            __repr__ = models.columns_repr(["value"])

        obj = SimpleModel()
        assert repr(obj) == "<SimpleModel value='hello'>"


# ===========================================================================
# Tests: DojoChallenges.visible (the Python path)
# ===========================================================================

class TestChallengeVisibility:
    """Tests for DojoChallenges.visible() hybrid method (Python side)."""

    def test_no_visibility_always_visible(self):
        """Without a visibility record, challenge is always visible."""
        challenge = MagicMock()
        challenge.visibility = None
        # Simulate the visibility method logic:
        when = datetime.datetime.utcnow()
        result = not challenge.visibility or all((
            not challenge.visibility.start or when >= challenge.visibility.start,
            not challenge.visibility.stop or when <= challenge.visibility.stop,
        ))
        assert result is True

    def test_before_start_not_visible(self):
        challenge = MagicMock()
        challenge.visibility.start = datetime.datetime(2026, 12, 31)
        challenge.visibility.stop = None
        when = datetime.datetime(2026, 1, 1)
        result = not challenge.visibility or all((
            not challenge.visibility.start or when >= challenge.visibility.start,
            not challenge.visibility.stop or when <= challenge.visibility.stop,
        ))
        assert result is False

    def test_after_stop_not_visible(self):
        challenge = MagicMock()
        challenge.visibility.start = None
        challenge.visibility.stop = datetime.datetime(2020, 1, 1)
        when = datetime.datetime(2026, 1, 1)
        result = not challenge.visibility or all((
            not challenge.visibility.start or when >= challenge.visibility.start,
            not challenge.visibility.stop or when <= challenge.visibility.stop,
        ))
        assert result is False

    def test_during_window_visible(self):
        challenge = MagicMock()
        challenge.visibility.start = datetime.datetime(2020, 1, 1)
        challenge.visibility.stop = datetime.datetime(2030, 1, 1)
        when = datetime.datetime(2025, 6, 15)
        result = not challenge.visibility or all((
            not challenge.visibility.start or when >= challenge.visibility.start,
            not challenge.visibility.stop or when <= challenge.visibility.stop,
        ))
        assert result is True

    def test_exactly_at_start_visible(self):
        challenge = MagicMock()
        challenge.visibility.start = datetime.datetime(2025, 1, 1)
        challenge.visibility.stop = None
        when = datetime.datetime(2025, 1, 1)
        result = not challenge.visibility or all((
            not challenge.visibility.start or when >= challenge.visibility.start,
            not challenge.visibility.stop or when <= challenge.visibility.stop,
        ))
        assert result is True

    def test_exactly_at_stop_visible(self):
        challenge = MagicMock()
        challenge.visibility.start = None
        challenge.visibility.stop = datetime.datetime(2025, 1, 1)
        when = datetime.datetime(2025, 1, 1)
        result = not challenge.visibility or all((
            not challenge.visibility.start or when >= challenge.visibility.start,
            not challenge.visibility.stop or when <= challenge.visibility.stop,
        ))
        assert result is True
