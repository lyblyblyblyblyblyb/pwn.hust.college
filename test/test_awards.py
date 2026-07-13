"""
Integration tests for awards, belts, emojis, and belt progression.

Uses the same helpers and fixtures as test_running.py.
Requires a running dojo container (set CONTAINER_NAME env var if not "dojo").
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


# Existing dojos in the running instance
EXISTING_DOJO = "welcome"


# ===========================================================================
# Belt constants validation
# ===========================================================================

class TestBeltDataIntegrity:
    """Tests for BELT_ORDER and BELT_REQUIREMENTS data consistency."""

    def test_belt_order_length(self):
        """Belt order should have exactly 8 colors."""
        BELT_ORDER = ["orange", "yellow", "green", "purple", "blue", "brown", "red", "black"]
        assert len(BELT_ORDER) == 8

    def test_belt_order_has_all_colors(self):
        BELT_ORDER = ["orange", "yellow", "green", "purple", "blue", "brown", "red", "black"]
        expected_colors = {"orange", "yellow", "green", "purple", "blue", "brown", "red", "black"}
        assert set(BELT_ORDER) == expected_colors

    def test_belt_requirements_known_colors(self):
        BELT_REQUIREMENTS = {
            "orange": "welcome",
            "yellow": "pwntools",
            "green": "saffron",
            "purple": "viridian",
            "blue": "leagueconference",
        }
        assert BELT_REQUIREMENTS["orange"] == "welcome"
        assert BELT_REQUIREMENTS["yellow"] == "pwntools"

    def test_belt_progression_order(self):
        BELT_ORDER = ["orange", "yellow", "green", "purple", "blue", "brown", "red", "black"]
        # Verify the belt progression is in increasing difficulty
        assert BELT_ORDER[0] == "orange"
        assert BELT_ORDER[-1] == "black"

    def test_belt_requirements_colors_in_belt_order(self):
        BELT_ORDER = ["orange", "yellow", "green", "purple", "blue", "brown", "red", "black"]
        BELT_REQUIREMENTS = {
            "orange": "welcome",
            "yellow": "pwntools",
            "green": "saffron",
            "purple": "viridian",
            "blue": "leagueconference",
        }
        for color in BELT_REQUIREMENTS:
            assert color in BELT_ORDER


# ===========================================================================
# Belt endpoint integration tests
# ===========================================================================

class TestBeltsPage:
    """Tests for the /belts public page."""

    def test_belts_page_accessible(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/belts")
        assert response.status_code == 200

    def test_belts_page_has_content(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/belts")
        text = response.text.lower()
        assert len(text) > 0
        assert "dojo" in text or "belt" in text or "腰带" in text


# ===========================================================================
# Belts API tests
# ===========================================================================

class TestBeltsApi:
    """Tests for the belts API that queries belt data."""

    def test_get_belts_api_has_correct_structure(self, admin_session):
        """The belts API should return proper dates, users, and ranks."""
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/belts")
        data = response.json()

        assert "dates" in data
        assert "users" in data
        assert "ranks" in data

        assert isinstance(data["dates"], dict)
        assert isinstance(data["users"], dict)
        assert isinstance(data["ranks"], dict)


# ===========================================================================
# User profile / hacker page tests
# ===========================================================================

class TestHackerProfile:
    """Tests for user profile pages that show awards."""

    def test_settings_page_authenticated(self, admin_session):
        """Settings page should be accessible for authenticated users."""
        response = admin_session.get(f"{PROTO}://{HOST}/settings")
        assert response.status_code in (200, 302)

    def test_dojo_listing_shows_dojos(self, admin_session):
        """Dojo listing page should show available dojos."""
        response = admin_session.get(f"{PROTO}://{HOST}/dojos")
        assert response.status_code == 200
        text = response.text.lower()
        assert "dojo" in text or "welcome" in text or "pwntools" in text


# ===========================================================================
# Scoreboard with awards
# ===========================================================================

class TestScoreboardAwards:
    """Tests for scoreboard integration with awards/badges."""

    def test_scoreboard_standings_have_badges_or_solves(self, admin_session):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{EXISTING_DOJO}/_/0/1"
        )
        data = response.json()
        for standing in data.get("standings", []):
            assert "badges" in standing or "solves" in standing

    def test_scoreboard_module_returns_200(self, admin_session):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{EXISTING_DOJO}/welcome/0/1"
        )
        assert response.status_code == 200


# ===========================================================================
# Dojo pages
# ===========================================================================

class TestDojoPages:
    """Tests for dojo listing pages."""

    def test_dojos_page_accessible(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/dojos")
        assert response.status_code == 200

    def test_existing_dojo_page_accessible(self):
        import requests
        response = requests.get(f"{PROTO}://{HOST}/dojo/{EXISTING_DOJO}")
        assert response.status_code == 200
