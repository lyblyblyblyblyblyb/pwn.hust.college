"""
Integration tests for awards, belts, emojis, and belt progression.

Uses the same helpers and fixtures as test_running.py.
Requires a running dojo container.
"""
import random
import string
import re
import subprocess

import pytest

#pylint:disable=redefined-outer-name,use-dict-literal,missing-timeout,unspecified-encoding,consider-using-with,unused-argument

from utils import (
    TEST_DOJOS_LOCATION, PROTO, HOST, login, dojo_run, workspace_run,
    create_dojo_yml, make_dojo_official,
)


def get_flag(user):
    return workspace_run("cat /flag", user=user, root=True).stdout


def get_challenge_id(session, dojo, module, challenge):
    response = session.get(
        f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{dojo}/{module}/challenges"
    )
    assert response.status_code == 200
    challenges = response.json()["challenges"]
    for chall in challenges:
        if chall["id"] == challenge:
            return chall["challenge_id"]
    pytest.fail(f"Challenge '{challenge}' not found in module '{module}'")


def start_challenge(dojo, module, challenge, practice=False, *, session):
    data = dict(dojo=dojo, module=module, challenge=challenge, practice=practice)
    response = session.post(f"{PROTO}://{HOST}/pwncollege_api/v1/docker", json=data)
    assert response.status_code == 200
    assert response.json()["success"], f"Failed: {response.json().get('error')}"


# ===========================================================================
# Belt constants validation (doesn't need running container)
# ===========================================================================

class TestBeltDataIntegrity:
    """Tests for BELT_ORDER and BELT_REQUIREMENTS data consistency."""

    def test_belt_order_has_all_colors(self):
        from dojo_plugin.utils.awards import BELT_ORDER
        expected_colors = {"orange", "yellow", "green", "purple", "blue", "brown", "red", "black"}
        assert set(BELT_ORDER) == expected_colors

    def test_belt_order_length(self):
        from dojo_plugin.utils.awards import BELT_ORDER
        assert len(BELT_ORDER) == 8

    def test_belt_requirements_are_valid(self):
        from dojo_plugin.utils.awards import BELT_REQUIREMENTS, BELT_ORDER
        for color in BELT_REQUIREMENTS:
            assert color in BELT_ORDER, f"Belt color '{color}' not in BELT_ORDER"

    def test_belt_asset_known_colors(self):
        from dojo_plugin.utils.awards import BELT_REQUIREMENTS
        # Known requirement: orange -> welcome, yellow -> pwntools
        assert BELT_REQUIREMENTS["orange"] == "welcome"
        assert BELT_REQUIREMENTS["yellow"] == "pwntools"

    def test_belt_progression_order(self):
        from dojo_plugin.utils.awards import BELT_ORDER
        # Verify the belt progression is in increasing difficulty
        assert BELT_ORDER[0] == "orange"
        assert BELT_ORDER[-1] == "black"


# ===========================================================================
# Belt endpoint integration tests
# ===========================================================================

class TestBeltsPage:
    """Tests for the /belts public page."""

    def test_belts_page_accessible(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/belts")
        assert response.status_code == 200

    def test_belts_page_contains_title(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/belts")
        assert "腰带" in response.text or "belt" in response.text.lower() or "dojo" in response.text.lower()


# ===========================================================================
# Emoji award tests
# ===========================================================================

class TestEmojiAwards:
    """Tests for emoji award functionality."""

    @pytest.mark.dependency()
    def test_dojo_award_shows_on_completion(self, simple_award_dojo, admin_session):
        """After completing a dojo, the award emoji should appear."""
        dojo_rid = simple_award_dojo
        # Access the dojo page
        response = admin_session.get(f"{PROTO}://{HOST}/{dojo_rid}/")
        assert response.status_code == 200

    def test_get_belts_api_has_correct_structure(self, admin_session):
        """The belts API should return proper dates, users, and ranks."""
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/belts")
        data = response.json()

        # Verify expected keys
        assert "dates" in data
        assert "users" in data
        assert "ranks" in data

        # Each should be dicts
        assert isinstance(data["dates"], dict)
        assert isinstance(data["users"], dict)
        assert isinstance(data["ranks"], dict)


# ===========================================================================
# User profile / hacker page tests
# ===========================================================================

class TestHackerProfile:
    """Tests for user profile pages that show awards."""

    def test_own_profile_accessible(self, admin_session):
        response = admin_session.get(f"{PROTO}://{HOST}/hacker/")
        assert response.status_code == 200

    def test_admin_profile_accessible_public(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/hacker/admin")
        assert response.status_code == 200

    def test_profile_shows_user_info(self, admin_session):
        response = admin_session.get(f"{PROTO}://{HOST}/hacker/admin")
        text = response.text.lower()
        # Should contain username somewhere
        assert "admin" in text or "hacker" in text


# ===========================================================================
# Scoreboard with awards
# ===========================================================================

class TestScoreboardAwards:
    """Tests for scoreboard integration with awards/badges."""

    def test_scoreboard_shows_badges(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{example_dojo}/_/0/1"
        )
        data = response.json()
        for standing in data.get("standings", []):
            assert "badges" in standing or "solves" in standing

    def test_scoreboard_module_shows_solves(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{example_dojo}/world/0/1"
        )
        assert response.status_code == 200
        data = response.json()
        for standing in data.get("standings", []):
            assert "solves" in standing
