"""
Unit tests for dojo YAML spec validation, setdefault_name,
and load_dojo_subyamls.

Follows the mock pattern from test_discord_fixes.py.
"""
import sys
import types
import importlib
import importlib.util
import tempfile
import pathlib
from unittest.mock import patch, MagicMock

import pytest
import yaml


# ---------------------------------------------------------------------------
# Stub infrastructure (same pattern as test_discord_fixes.py)
# ---------------------------------------------------------------------------

def _stub(name):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules[name] = mod
    return sys.modules[name]


# Pre-import real packages so stubs don't shadow them
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.sql
import flask

# Stub infrastructure (same pattern as test_discord_fixes.py)

def _stub(name):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules[name] = mod
    return sys.modules[name]


for _pkg in [
    "dojo_plugin", "dojo_plugin.config", "dojo_plugin.models",
    "dojo_plugin.utils", "dojo_plugin.utils.dojo",
    "dojo_plugin.api", "dojo_plugin.api.v1",
    "flask_restx",
    "CTFd", "CTFd.models", "CTFd.cache", "CTFd.utils",
    "CTFd.utils.user", "CTFd.utils.decorators",
    "requests",
]:
    _stub(_pkg)

# Mock flask attributes that dojo.py imports
sys.modules["flask"].abort = MagicMock()
sys.modules["flask"].g = MagicMock()
sys.modules["flask"].current_app = MagicMock()
sys.modules["flask"].current_app.config = {"SECRET_KEY": "test-secret"}

sys.modules["CTFd.models"].db = MagicMock()
sys.modules["CTFd.models"].Challenges = MagicMock()
sys.modules["CTFd.models"].Solves = MagicMock()
sys.modules["CTFd.models"].Users = MagicMock()
sys.modules["CTFd.models"].Flags = MagicMock()
sys.modules["CTFd.cache"].cache = MagicMock()
sys.modules["CTFd.cache"].cache.memoize = lambda **kw: (lambda f: f)
sys.modules["CTFd.utils.user"].get_current_user = MagicMock()
sys.modules["CTFd.utils.user"].is_admin = MagicMock(return_value=False)
sys.modules["CTFd.utils.decorators"].authed_only = lambda f: f

sys.modules["dojo_plugin.models"].Dojos = MagicMock()
sys.modules["dojo_plugin.models"].Dojos.from_id = MagicMock()
sys.modules["dojo_plugin.models"].DojoUsers = MagicMock()
sys.modules["dojo_plugin.models"].DojoModules = MagicMock()
sys.modules["dojo_plugin.models"].DojoChallenges = MagicMock()
sys.modules["dojo_plugin.models"].DojoResources = MagicMock()
sys.modules["dojo_plugin.models"].DojoChallengeVisibilities = MagicMock()
sys.modules["dojo_plugin.models"].DojoResourceVisibilities = MagicMock()
sys.modules["dojo_plugin.config"].DOJOS_DIR = pathlib.Path("/var/dojos")
sys.modules["dojo_plugin"].__path__ = []


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# The dojo.py imports from ..utils (the __init__.py) which we need to stub
_utils_stub = _stub("dojo_plugin.utils")
_utils_stub.get_current_container = MagicMock(return_value=None)

dojo_utils = _load_module_from_file(
    "dojo_plugin.utils.dojo",
    "dojo_plugin/utils/dojo.py",
)


# ===========================================================================
# Tests: setdefault_name
# ===========================================================================

class TestSetdefaultName:
    """Tests for setdefault_name: generates name from id if missing."""

    def test_generates_name_from_id(self):
        entry = {"id": "hello-world"}
        dojo_utils.setdefault_name(entry)
        assert entry["name"] == "Hello World"

    def test_leaves_existing_name(self):
        entry = {"id": "hello-world", "name": "Custom Name"}
        dojo_utils.setdefault_name(entry)
        assert entry["name"] == "Custom Name"

    def test_skips_when_import_present(self):
        entry = {"id": "hello-world", "import": {"dojo": "other"}}
        dojo_utils.setdefault_name(entry)
        assert "name" not in entry

    def test_skips_when_no_id(self):
        entry = {"name": "No ID Entry"}
        dojo_utils.setdefault_name(entry)
        assert entry["name"] == "No ID Entry"

    def test_skips_empty_dict(self):
        entry = {}
        dojo_utils.setdefault_name(entry)
        assert "name" not in entry

    def test_hyphen_replacement(self):
        entry = {"id": "my-cool-module"}
        dojo_utils.setdefault_name(entry)
        assert entry["name"] == "My Cool Module"

    def test_single_word_id(self):
        entry = {"id": "welcome"}
        dojo_utils.setdefault_name(entry)
        assert entry["name"] == "Welcome"


# ===========================================================================
# Tests: setdefault_subyaml
# ===========================================================================

class TestSetdefaultSubyaml:
    """Tests for setdefault_subyaml: merges sub-YAML with top-YAML override."""

    def test_top_level_overrides_subyaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subyaml_path = pathlib.Path(tmpdir) / "module.yml"
            subyaml_path.write_text("name: Sub Name\ndescription: Sub Desc\n")

            data = {"id": "test", "name": "Top Name"}
            dojo_utils.setdefault_subyaml(data, subyaml_path)

            assert data["name"] == "Top Name"  # top-level wins
            assert data["description"] == "Sub Desc"  # sub fills missing

    def test_no_file_no_change(self):
        data = {"id": "test", "name": "Original"}
        original = dict(data)
        dojo_utils.setdefault_subyaml(data, pathlib.Path("/nonexistent/path.yml"))
        assert data == original

    def test_subyaml_without_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subyaml_path = pathlib.Path(tmpdir) / "challenge.yml"
            subyaml_path.write_text("description: From sub\ntype: challenge-type\n")

            data = {"id": "chall"}
            dojo_utils.setdefault_subyaml(data, subyaml_path)

            assert data["id"] == "chall"  # preserved
            assert data["description"] == "From sub"
            assert data["type"] == "challenge-type"


# ===========================================================================
# Tests: load_dojo_subyamls
# ===========================================================================

class TestLoadDojoSubyamls:
    """Tests for load_dojo_subyamls: loads DESCRIPTION.md and module.yml files."""

    def test_loads_dojo_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dojo_dir = pathlib.Path(tmpdir)
            (dojo_dir / "DESCRIPTION.md").write_text("Dojo description text")

            data = {"id": "test-dojo", "modules": []}
            result = dojo_utils.load_dojo_subyamls(data, dojo_dir)

            assert result["description"] == "Dojo description text"

    def test_description_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dojo_dir = pathlib.Path(tmpdir)
            (dojo_dir / "DESCRIPTION.md").write_text("File description")

            data = {"id": "test-dojo", "description": "Explicit description", "modules": []}
            result = dojo_utils.load_dojo_subyamls(data, dojo_dir)

            assert result["description"] == "Explicit description"

    def test_loads_module_description_and_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dojo_dir = pathlib.Path(tmpdir)
            module_dir = dojo_dir / "my-module"
            module_dir.mkdir()
            (module_dir / "DESCRIPTION.md").write_text("Module description")
            (module_dir / "module.yml").write_text("name: Module Name\n")

            data = {
                "id": "test-dojo",
                "modules": [{"id": "my-module"}],
            }
            result = dojo_utils.load_dojo_subyamls(data, dojo_dir)

            module = result["modules"][0]
            assert module["description"] == "Module description"
            assert module["name"] == "Module Name"

    def test_loads_challenge_subyamls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dojo_dir = pathlib.Path(tmpdir)
            module_dir = dojo_dir / "mod"
            challenge_dir = module_dir / "chall"
            challenge_dir.mkdir(parents=True)
            (challenge_dir / "DESCRIPTION.md").write_text("Challenge desc")
            (challenge_dir / "challenge.yml").write_text("name: Challenge Name\nlevel: 5\n")

            data = {
                "id": "test-dojo",
                "modules": [{
                    "id": "mod",
                    "challenges": [{"id": "chall"}],
                }],
            }
            result = dojo_utils.load_dojo_subyamls(data, dojo_dir)

            challenge = result["modules"][0]["challenges"][0]
            assert challenge["description"] == "Challenge desc"
            assert challenge["name"] == "Challenge Name"
            assert challenge["level"] == 5

    def test_handles_missing_directories_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dojo_dir = pathlib.Path(tmpdir)

            data = {
                "id": "test-dojo",
                "modules": [
                    {"id": "no-dir-module"},
                    {"id": "mod-without-challenges", "challenges": []},
                ],
            }
            # Should not raise
            result = dojo_utils.load_dojo_subyamls(data, dojo_dir)
            assert len(result["modules"]) == 2


# ===========================================================================
# Tests: DOJO_SPEC validation
# ===========================================================================

class TestDojoSpecValidation:
    """Tests for DOJO_SPEC schema validation of dojo.yml data."""

    def test_minimal_valid_dojo(self):
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
            "type": "public",
        }
        result = dojo_utils.DOJO_SPEC.validate(data)
        assert result["id"] == "test-dojo"

    def test_minimal_with_modules(self):
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
            "modules": [{"id": "mod1"}],
        }
        result = dojo_utils.DOJO_SPEC.validate(data)
        assert len(result["modules"]) == 1
        assert result["modules"][0]["id"] == "mod1"

    def test_invalid_id_with_spaces(self):
        from schema import SchemaError
        data = {
            "id": "test dojo with spaces",
            "name": "Test Dojo",
        }
        with pytest.raises(SchemaError):
            dojo_utils.DOJO_SPEC.validate(data)

    def test_invalid_id_too_long(self):
        from schema import SchemaError
        data = {
            "id": "a" * 33,  # max 32
            "name": "Test Dojo",
        }
        with pytest.raises(SchemaError):
            dojo_utils.DOJO_SPEC.validate(data)

    def test_invalid_password_too_short(self):
        from schema import SchemaError
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
            "password": "short",  # min 8
        }
        with pytest.raises(SchemaError):
            dojo_utils.DOJO_SPEC.validate(data)

    def test_default_visibility(self):
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
        }
        result = dojo_utils.DOJO_SPEC.validate(data)
        assert result.get("visibility", {}) == {}

    def test_dojo_with_award(self):
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
            "award": {"emoji": "my-emoji", "award_at": 5},
        }
        result = dojo_utils.DOJO_SPEC.validate(data)
        assert result["award"]["emoji"] == "my-emoji"
        assert result["award"]["award_at"] == 5

    def test_module_with_challenges(self):
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
            "modules": [{
                "id": "mod1",
                "name": "Module One",
                "challenges": [
                    {"id": "chall1", "name": "Challenge 1"},
                    {"id": "chall2", "name": "Challenge 2", "level": 3},
                ],
            }],
        }
        result = dojo_utils.DOJO_SPEC.validate(data)
        challenges = result["modules"][0]["challenges"]
        assert len(challenges) == 2
        assert challenges[1]["level"] == 3

    def test_dojo_with_import(self):
        data = {
            "id": "test-dojo",
            "import": {"dojo": "source-dojo~abcdef01"},
        }
        result = dojo_utils.DOJO_SPEC.validate(data)
        assert result["import"]["dojo"] == "source-dojo~abcdef01"

    def test_invalid_image_name_with_spaces(self):
        from schema import SchemaError
        data = {
            "id": "test-dojo",
            "name": "Test Dojo",
            "image": "image with spaces",
        }
        with pytest.raises(SchemaError):
            dojo_utils.DOJO_SPEC.validate(data)
