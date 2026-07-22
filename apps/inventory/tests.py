"""
Tests for apps/inventory.

CameraModel/CameraBrand live on the "sigtools" DB alias (config/settings/test.py
doesn't configure it, and SigtoolsRouter.allow_migrate blocks creating the table
there anyway) — mock them instead of hitting a real sigtools test database.
CameraSpecChangeLog lives on "default" like the rest of this app, so it uses the
real test database.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import CameraSpecChangeLog
from apps.sigtools.models import CameraBrand, CameraModel


def _fake_camera_model(**overrides):
    defaults = dict(
        id=168, name="IP2M-853E", camera_brand_id=5,
        rango_lente_mm=None, rango_fov_grados=None,
    )
    defaults.update(overrides)
    obj = SimpleNamespace(**defaults)
    obj.save = MagicMock()
    return obj


def _fake_brand(name="AMCREST"):
    return SimpleNamespace(name=name)


class CameraSpecUpdateViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("inventory-camera-specs")
        self.user = User.objects.create_user(username="tech", password="pw")
        self.client.force_authenticate(user=self.user)
        self.valid_payload = {
            "camera_model_id": 168,
            "rango_lente_mm": [2.8, 12],
            "rango_fov_grados": [104, 29],
        }

    # -- happy path ---------------------------------------------------------

    def test_valid_payload_updates_spec_and_returns_200(self):
        fake_obj = _fake_camera_model()
        with patch.object(CameraModel, "objects") as mock_manager, \
             patch.object(CameraBrand, "objects") as mock_brand_manager, \
             patch("apps.core.cache_utils.invalidate") as mock_invalidate:
            mock_manager.get.return_value = fake_obj
            mock_brand_manager.get.return_value = _fake_brand()

            resp = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["camera_model_id"], 168)
        self.assertEqual(resp.data["name"], "IP2M-853E")
        self.assertEqual(resp.data["brand"], "AMCREST")
        self.assertEqual(resp.data["rango_lente_mm"], [2.8, 12])
        self.assertEqual(resp.data["rango_fov_grados"], [104, 29])
        self.assertEqual(fake_obj.rango_lente_mm, [2.8, 12])
        self.assertEqual(fake_obj.rango_fov_grados, [104, 29])
        mock_invalidate.assert_called_once()

    # -- 404 ------------------------------------------------------------

    def test_nonexistent_camera_model_id_returns_404(self):
        with patch.object(CameraModel, "objects") as mock_manager:
            mock_manager.get.side_effect = CameraModel.DoesNotExist
            resp = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # -- 400 validation ---------------------------------------------------

    def test_missing_camera_model_id_returns_400(self):
        payload = {k: v for k, v in self.valid_payload.items() if k != "camera_model_id"}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rango_lente_mm_with_one_element_returns_400(self):
        payload = {**self.valid_payload, "rango_lente_mm": [2.8]}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rango_lente_mm_with_three_elements_returns_400(self):
        payload = {**self.valid_payload, "rango_lente_mm": [2.8, 6, 12]}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_value_returns_400(self):
        payload = {**self.valid_payload, "rango_lente_mm": [-1, 12]}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rango_lente_mm_over_1000_returns_400(self):
        payload = {**self.valid_payload, "rango_lente_mm": [2.8, 1001]}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rango_fov_grados_over_360_returns_400(self):
        payload = {**self.valid_payload, "rango_fov_grados": [104, 361]}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_numeric_value_returns_400(self):
        payload = {**self.valid_payload, "rango_lente_mm": [2.8, "twelve"]}
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # -- auth ---------------------------------------------------------------

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.url, self.valid_payload, format="json")
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # -- scope guard ----------------------------------------------------

    def test_poe_watts_bandwidth_lens_type_not_touched(self):
        fake_obj = _fake_camera_model()
        with patch.object(CameraModel, "objects") as mock_manager, \
             patch.object(CameraBrand, "objects") as mock_brand_manager, \
             patch("apps.core.cache_utils.invalidate"):
            mock_manager.get.return_value = fake_obj
            mock_brand_manager.get.return_value = _fake_brand()
            self.client.post(self.url, self.valid_payload, format="json")

        # update_fields restricts the actual SQL UPDATE columns — proves
        # poe_watts/bandwidth_mbps/lens_type were never included.
        fake_obj.save.assert_called_once_with(update_fields=["rango_lente_mm", "rango_fov_grados"])
        self.assertFalse(hasattr(fake_obj, "poe_watts"))
        self.assertFalse(hasattr(fake_obj, "bandwidth_mbps"))
        self.assertFalse(hasattr(fake_obj, "lens_type"))

    # -- audit trail ----------------------------------------------------

    def test_camera_spec_change_log_created_with_changed_by_id(self):
        fake_obj = _fake_camera_model()
        with patch.object(CameraModel, "objects") as mock_manager, \
             patch.object(CameraBrand, "objects") as mock_brand_manager, \
             patch("apps.core.cache_utils.invalidate"):
            mock_manager.get.return_value = fake_obj
            mock_brand_manager.get.return_value = _fake_brand()
            self.client.post(self.url, self.valid_payload, format="json")

        log = CameraSpecChangeLog.objects.get(camera_model_id=168)
        self.assertEqual(log.changed_by_id, self.user.id)
        self.assertEqual(log.rango_lente_mm, [2.8, 12])
        self.assertEqual(log.rango_fov_grados, [104, 29])

    def test_change_log_write_failure_does_not_break_the_response(self):
        fake_obj = _fake_camera_model()
        with patch.object(CameraModel, "objects") as mock_manager, \
             patch.object(CameraBrand, "objects") as mock_brand_manager, \
             patch("apps.core.cache_utils.invalidate"), \
             patch.object(CameraSpecChangeLog, "objects") as mock_log_manager:
            mock_manager.get.return_value = fake_obj
            mock_brand_manager.get.return_value = _fake_brand()
            mock_log_manager.create.side_effect = Exception("transient db blip")

            resp = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(fake_obj.rango_lente_mm, [2.8, 12])
