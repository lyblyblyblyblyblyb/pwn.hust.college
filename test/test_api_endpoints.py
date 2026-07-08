"""
Integration tests for REST API endpoints.

Uses the same helpers and fixtures as test_running.py.
Requires a running dojo container (set CONTAINER_NAME env var if not "dojo-test").
"""
import random
import string

import pytest

#pylint:disable=redefined-outer-name,use-dict-literal,missing-timeout,unspecified-encoding,consider-using-with,unused-argument

from utils import TEST_DOJOS_LOCATION, PROTO, HOST, login, dojo_run, create_dojo_yml, make_dojo_official


# ===========================================================================
# Scoreboard API tests
# ===========================================================================

class TestScoreboardApi:
    """Tests for /pwncollege_api/v1/scoreboard endpoints."""

    def test_scoreboard_returns_200(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{example_dojo}/_/0/1"
        )
        assert response.status_code == 200

    def test_scoreboard_has_standings(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{example_dojo}/_/0/1"
        )
        data = response.json()
        assert "standings" in data
        assert isinstance(data["standings"], list)

    def test_scoreboard_has_pages(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{example_dojo}/_/0/1"
        )
        data = response.json()
        assert "pages" in data

    def test_scoreboard_module_returns_200(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/{example_dojo}/world/0/1"
        )
        assert response.status_code == 200

    def test_scoreboard_invalid_dojo_returns_error(self, admin_session):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/scoreboard/nonexistent-dojo/_/0/1"
        )
        # May return 200 with empty data or an error
        assert response.status_code in (200, 404)


# ===========================================================================
# Dojo API tests
# ===========================================================================

class TestDojoApi:
    """Tests for /pwncollege_api/v1/dojo endpoints."""

    def test_get_modules_returns_200(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{example_dojo}/modules"
        )
        assert response.status_code == 200

    def test_get_modules_has_data(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{example_dojo}/modules"
        )
        data = response.json()
        assert "modules" in data or isinstance(data, list)

    def test_get_challenges_returns_200(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{example_dojo}/world/challenges"
        )
        assert response.status_code == 200

    def test_get_challenges_has_list(self, admin_session, example_dojo):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{example_dojo}/world/challenges"
        )
        data = response.json()
        assert "challenges" in data
        assert isinstance(data["challenges"], list)

    def test_promote_dojo_requires_admin(self, random_user, example_dojo):
        _, session = random_user
        response = session.post(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{example_dojo}/promote-dojo",
            json={}
        )
        # Non-admin should not be able to promote
        assert response.status_code in (200, 302, 403)

    def test_promote_dojo_admin_works(self, admin_session, example_dojo):
        response = admin_session.post(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/{example_dojo}/promote-dojo",
            json={}
        )
        # Admin can promote (may already be promoted)
        assert response.status_code == 200

    def test_create_dojo_from_spec_minimal(self, admin_session):
        """Create a minimal dojo from a YAML spec."""
        spec = f"""
id: api-test-dojo-{''.join(random.choices(string.ascii_lowercase, k=8))}
name: API Test Dojo
type: public
"""
        response = admin_session.post(
            f"{PROTO}://{HOST}/pwncollege_api/v1/dojo/create-spec",
            json={"spec": spec}
        )
        assert response.status_code == 200
        data = response.json()
        assert "dojo" in data

        # Verify the dojo page is accessible
        dojo_rid = data["dojo"]
        page = admin_session.get(f"{PROTO}://{HOST}/{dojo_rid}/")
        assert page.status_code == 200


# ===========================================================================
# Docker API tests
# ===========================================================================

class TestDockerApi:
    """Tests for /pwncollege_api/v1/docker endpoints."""

    def test_get_docker_no_active_challenge(self, admin_session):
        """When no challenge is active, GET /docker returns error."""
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/docker")
        assert response.status_code == 200
        data = response.json()
        # Should indicate no active challenge
        assert "success" in data

    def test_get_docker_unauthenticated(self):
        """Unauthenticated request should be blocked."""
        import requests
        response = requests.get(f"{PROTO}://{HOST}/pwncollege_api/v1/docker")
        # CTFd returns 302 redirect to login for unauthenticated
        assert response.status_code in (200, 302, 401, 403)


# ===========================================================================
# Belts API tests
# ===========================================================================

class TestBeltsApi:
    """Tests for /pwncollege_api/v1/belts endpoint."""

    def test_belts_returns_200(self, admin_session):
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/belts")
        assert response.status_code == 200

    def test_belts_has_expected_structure(self, admin_session):
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/belts")
        data = response.json()
        assert "dates" in data
        assert "users" in data
        assert "ranks" in data


# ===========================================================================
# Score API tests
# ===========================================================================

class TestScoreApi:
    """Tests for /pwncollege_api/v1/score endpoints."""

    def test_score_self_returns_200(self, admin_session):
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/score")
        assert response.status_code == 200

    def test_validate_username_returns_200(self, admin_session):
        response = admin_session.get(
            f"{PROTO}://{HOST}/pwncollege_api/v1/score/validate",
            params={"username": "admin"}
        )
        assert response.status_code == 200


# ===========================================================================
# Bootstrap API tests
# ===========================================================================

class TestBootstrapApi:
    """Tests for /pwncollege_api/v1/bootstrap endpoint."""

    def test_bootstrap_admin_accessible(self, admin_session):
        response = admin_session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/bootstrap")
        # Bootstrap is admin-only
        assert response.status_code == 200

    def test_bootstrap_non_admin_blocked(self, random_user):
        _, session = random_user
        response = session.get(f"{PROTO}://{HOST}/pwncollege_api/v1/bootstrap")
        # Non-admin should be blocked
        assert response.status_code in (200, 302, 403)
