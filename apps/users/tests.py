"""
Tests for the decoupled JWT scheme (ADR-0001).

apps.core.models.User/UserRole/UserName and apps.users.models.Session are all
managed=False (unmanaged legacy tables) — config/settings/test.py's sqlite DB
never creates them (Options.can_migrate() requires managed=True), so these
are mocked at the manager level, matching the established pattern in
apps/inventory/tests.py rather than hitting a real test database.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User as AuthUser
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.exceptions import ServiceException
from apps.core.models import User as DailyUser
from apps.users import services
from apps.users.authentication import (
    DailyAccessToken,
    DailyJWTAuthentication,
    DailyJWTUser,
)


def _fake_daily_user(pk=25, password="1234", role_name="Operador", role_pk=2):
    role = SimpleNamespace(pk=role_pk, name=role_name)
    return SimpleNamespace(pk=pk, password=password, role=role)


class DailyJWTAuthenticationTests(TestCase):
    """
    Covers the critical, independently-confirmed finding from /autoplan:
    this authenticator must return None (not raise) for anything that
    isn't positively identified as a daily token, so DRF's authentication
    chain can fall through to the next authenticator instead of stopping.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.auth = DailyJWTAuthentication()

    def _request(self, header_value=None):
        req = self.factory.get("/")
        if header_value is not None:
            req.META["HTTP_AUTHORIZATION"] = header_value
        return req

    def test_no_auth_header_returns_none(self):
        self.assertIsNone(self.auth.authenticate(self._request()))

    def test_non_bearer_header_returns_none(self):
        self.assertIsNone(self.auth.authenticate(self._request("Basic abc123")))

    def test_garbage_bearer_value_returns_none_not_500(self):
        # Not JWT-shaped (no two dots) -- must not raise.
        self.assertIsNone(self.auth.authenticate(self._request("Bearer garbage")))

    def test_malformed_jwt_shaped_token_returns_none_not_500(self):
        # Three dot-separated segments but not a valid/decodable token --
        # DailyAccessToken(raw) raises TokenError, which must be caught.
        self.assertIsNone(self.auth.authenticate(self._request("Bearer a.b.c")))

    def test_expired_daily_token_returns_none(self):
        token = DailyAccessToken()
        token.set_exp(from_time=token.current_time - timedelta(days=1), lifetime=timedelta(seconds=1))
        token["daily_user_id"] = 25
        self.assertIsNone(self.auth.authenticate(self._request(f"Bearer {token}")))

    def test_valid_jwt_without_daily_user_id_claim_returns_none(self):
        """
        The exact scenario the ordering bug hinges on: a syntactically valid
        access token (same SECRET_KEY, same algorithm -- e.g. one issued by
        a different JWTAuthentication consumer on this platform) that simply
        isn't a daily token. Must defer (return None), never reject.
        """
        other_token = AccessToken()
        other_token["user_id"] = 999  # generic claim, no daily_user_id
        self.assertIsNone(self.auth.authenticate(self._request(f"Bearer {other_token}")))

    def test_daily_token_authenticates_successfully(self):
        daily_user = _fake_daily_user(pk=25)
        token = DailyAccessToken()
        token["daily_user_id"] = 25
        token["role"] = "Operador"

        with patch.object(DailyUser, "objects") as mock_manager:
            mock_manager.select_related.return_value.get.return_value = daily_user
            result = self.auth.authenticate(self._request(f"Bearer {token}"))

        self.assertIsNotNone(result)
        user, returned_token = result
        self.assertIsInstance(user, DailyJWTUser)
        self.assertEqual(user.pk, 25)
        self.assertTrue(user.is_authenticated)
        self.assertEqual(returned_token.payload["daily_user_id"], 25)

    def test_daily_user_no_longer_exists_raises_authentication_failed(self):
        """
        Once daily_user_id is present, this token positively identifies as
        ours -- no other authenticator could resolve it differently, so a
        hard 401 (not a silent None) is correct here.
        """
        token = DailyAccessToken()
        token["daily_user_id"] = 404

        with patch.object(DailyUser, "objects") as mock_manager:
            mock_manager.select_related.return_value.get.side_effect = DailyUser.DoesNotExist
            with self.assertRaises(AuthenticationFailed):
                self.auth.authenticate(self._request(f"Bearer {token}"))

    def test_authenticate_header_is_bearer(self):
        self.assertEqual(self.auth.authenticate_header(self._request()), "Bearer")


class AuthenticatorOrderingTests(TestCase):
    """
    Settings-level guard for the critical finding both /autoplan reviewers
    independently surfaced: if DailyJWTAuthentication is ever moved to run
    AFTER the generic JWTAuthentication, every daily/platform login breaks
    (JWTAuthentication raises InvalidToken on the missing "user_id" claim
    before DailyJWTAuthentication gets a chance to run). This test fails
    loudly the moment someone reorders the tuple, instead of the breakage
    only surfacing as a wall of 401s in production.
    """

    def test_daily_jwt_authentication_precedes_generic_jwt_authentication(self):
        classes = list(settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"])
        daily_idx = classes.index("apps.users.authentication.DailyJWTAuthentication")
        generic_idx = classes.index("rest_framework_simplejwt.authentication.JWTAuthentication")
        self.assertLess(
            daily_idx,
            generic_idx,
            "DailyJWTAuthentication must precede the generic JWTAuthentication "
            "in DEFAULT_AUTHENTICATION_CLASSES -- see apps/users/authentication.py "
            "module docstring and docs/arc42/daily/decisions/0001-....md.",
        )


class IssueDailyAccessTokenTests(TestCase):
    def test_token_has_daily_claims_not_generic_user_id(self):
        daily_user = _fake_daily_user(pk=42, role_name="Supervisor", role_pk=3)
        token = services.issue_daily_access_token(daily_user)

        self.assertEqual(token["daily_user_id"], 42)
        self.assertEqual(token["role"], "Supervisor")
        with self.assertRaises(KeyError):
            token["user_id"]

    def test_token_lifetime_matches_daily_jwt_setting(self):
        daily_user = _fake_daily_user()
        token = services.issue_daily_access_token(daily_user)

        expected_exp = token.current_time + settings.DAILY_JWT["ACCESS_TOKEN_LIFETIME"]
        # Allow a small skew for wall-clock time elapsed during the test.
        self.assertAlmostEqual(token["exp"], int(expected_exp.timestamp()), delta=5)

    def test_extra_claims_are_set(self):
        daily_user = _fake_daily_user()
        token = services.issue_daily_access_token(daily_user, platform=True)
        self.assertTrue(token["platform"])


class LoginServiceTests(TestCase):
    """authenticate_daily_credentials() / login()'s response shape."""

    def test_authenticate_daily_credentials_success_creates_auth_user_shim(self):
        daily_user = _fake_daily_user(pk=7, password="secret")

        with patch.object(DailyUser, "objects") as mock_manager, \
             patch.object(AuthUser, "objects") as mock_auth_manager:
            mock_manager.select_related.return_value.get.return_value = daily_user
            mock_auth_manager.get_or_create.return_value = (MagicMock(), True)

            result = services.authenticate_daily_credentials(7, "secret")

        self.assertIs(result, daily_user)
        mock_auth_manager.get_or_create.assert_called_once_with(
            pk=7, defaults={"username": "daily_7", "is_active": True}
        )

    def test_authenticate_daily_credentials_wrong_password_raises(self):
        daily_user = _fake_daily_user(pk=7, password="secret")

        with patch.object(DailyUser, "objects") as mock_manager:
            mock_manager.select_related.return_value.get.return_value = daily_user
            with self.assertRaises(ServiceException):
                services.authenticate_daily_credentials(7, "wrong")

    def test_authenticate_daily_credentials_unknown_user_raises(self):
        with patch.object(DailyUser, "objects") as mock_manager:
            mock_manager.select_related.return_value.get.side_effect = DailyUser.DoesNotExist
            with self.assertRaises(ServiceException):
                services.authenticate_daily_credentials(999, "whatever")

    def test_login_response_has_refresh_null(self):
        """
        The core user-facing contract of ADR-0001: login responses never
        carry a real refresh token.
        """
        daily_user = _fake_daily_user(pk=25)
        profile = MagicMock()
        profile.user_id = 25
        session = SimpleNamespace(pk=912)

        # UserName is imported locally inside login() (from apps.core.models
        # import UserName), so it must be patched at its defining module,
        # not on apps.users.services (which never binds that name at
        # module level).
        with patch("apps.core.models.UserName") as mock_username_model, \
             patch.object(services, "authenticate_daily_credentials", return_value=daily_user), \
             patch("apps.users.services.Session") as mock_session_model, \
             patch.object(services, "_claim_station"), \
             patch.object(services, "_user_name", return_value="operador1"):
            mock_username_model.objects.get.return_value = profile
            mock_session_model.objects.filter.return_value.exists.return_value = False
            mock_session_model.objects.create.return_value = session

            result = services.login(username="operador1", password="1234", station_id=43)

        self.assertIsNone(result["refresh"])
        self.assertIn("access", result)
        self.assertEqual(result["session_id"], 912)
        self.assertEqual(result["station_id"], 43)
