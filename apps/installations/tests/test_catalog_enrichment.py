"""
Tests for catalog_enrichment.py — pure Python, no DB required.
Run with: python -m pytest apps/installations/tests/test_catalog_enrichment.py -v
"""
import unittest
from apps.installations.catalog_enrichment import (
    normalize_camera_subtype,
    normalize_static_subtype,
    enrich_camera_item,
    enrich_network_item,
    enrich_catalog_item,
    build_device_type_label,
    compute_cameras_and_views,
    DEFAULT_CAM_SPECS,
    VIEWS_PER_SUBTYPE,
)


class TestNormalizeCameraSubtype(unittest.TestCase):
    def test_known_subtypes_pass_through(self):
        for sub in ("bullet", "dome", "ptz", "5mp-dome", "dual-dome", "multi-view", "4k-dome", "hybrid-thermal"):
            self.assertEqual(normalize_camera_subtype(sub), sub)

    def test_fisheye_maps_to_multi_view(self):
        self.assertEqual(normalize_camera_subtype("fisheye 360"), "multi-view")

    def test_dual_in_name(self):
        self.assertEqual(normalize_camera_subtype("Dual Sensor Dome"), "dual-dome")

    def test_5mp_in_name(self):
        self.assertEqual(normalize_camera_subtype("5MP Outdoor Dome"), "5mp-dome")

    def test_4k_in_name(self):
        self.assertEqual(normalize_camera_subtype("4K Dome Camera"), "4k-dome")

    def test_thermal_maps_to_hybrid_thermal(self):
        self.assertEqual(normalize_camera_subtype("thermal imaging"), "hybrid-thermal")

    def test_unknown_defaults_to_bullet(self):
        self.assertEqual(normalize_camera_subtype("flycam"), "bullet")

    def test_none_defaults_to_bullet(self):
        self.assertEqual(normalize_camera_subtype(None), "bullet")


class TestNormalizeStaticSubtype(unittest.TestCase):
    def test_api_switch(self):
        self.assertEqual(normalize_static_subtype({"subtype": "switch"}), "switch")

    def test_api_da_maps_to_speaker(self):
        self.assertEqual(normalize_static_subtype({"subtype": "da"}), "speaker")

    def test_nvr_from_name(self):
        self.assertEqual(normalize_static_subtype({"subtype": "recorder", "name": "NVR 16ch"}), "nvr")

    def test_ap_from_name(self):
        self.assertEqual(normalize_static_subtype({"name": "WiFi Access Point", "subtype": ""}), "access-point")

    def test_radio_from_subtype(self):
        self.assertEqual(normalize_static_subtype({"subtype": "radio"}), "radio")

    def test_unknown_defaults_to_switch(self):
        self.assertEqual(normalize_static_subtype({"name": "mystery box"}), "switch")


class TestEnrichCameraItem(unittest.TestCase):
    def _base(self, **kw):
        return {"id": "1", "name": "Test Cam", "brand": "Axis", "category": "camera", **kw}

    def test_varifocal_defaults(self):
        result = enrich_camera_item(self._base(subtype="bullet"))
        self.assertEqual(result["lensType"], "varifocal")
        self.assertEqual(result["rango_lente_mm"], [2.8, 12])
        self.assertEqual(result["rango_fov_grados"], [104, 29])
        self.assertEqual(result["poe_watts"], 8)
        self.assertEqual(result["bandwidth_mbps"], 5)

    def test_fixed_lens_shape(self):
        result = enrich_camera_item(self._base(subtype="dual-dome"))
        self.assertEqual(result["lensType"], "fixed")
        self.assertIn("lente_mm", result)
        self.assertIn("fov_grados", result)
        self.assertNotIn("rango_lente_mm", result)

    def test_hybrid_shape(self):
        result = enrich_camera_item(self._base(subtype="bullet", lensType="hybrid"))
        self.assertIn("panoramica", result)
        self.assertIn("ptz", result)

    def test_brand_uppercased(self):
        result = enrich_camera_item(self._base(subtype="dome", brand="hikvision"))
        self.assertEqual(result["brand"], "HIKVISION")

    def test_view_name_takes_priority(self):
        result = enrich_camera_item(self._base(subtype="dome", name="Raw Name", view_name="CAM 5"))
        self.assertEqual(result["name"], "CAM 5")

    def test_qty_received_snake_case_mirrored(self):
        result = enrich_camera_item(self._base(subtype="dome", qty_received=3))
        self.assertEqual(result["qty_received"], 3)
        self.assertEqual(result["qtyReceived"], 3)

    def test_poe_from_item_overrides_default(self):
        result = enrich_camera_item(self._base(subtype="bullet", poe_watts=15))
        self.assertEqual(result["poe_watts"], 15)

    def test_labels_for_all_subtypes(self):
        for sub, specs in DEFAULT_CAM_SPECS.items():
            r = enrich_camera_item(self._base(subtype=sub))
            self.assertEqual(r["subtype"], sub)
            self.assertEqual(r["lensType"], specs["lensType"])


class TestEnrichNetworkItem(unittest.TestCase):
    def _base(self, **kw):
        return {"id": "sw1", "name": "PoE Switch 24", "brand": "Ubiquiti", "category": "static", **kw}

    def test_switch_subtype(self):
        result = enrich_network_item(self._base(subtype="switch"))
        self.assertEqual(result["subtype"], "switch")
        self.assertEqual(result["category"], "static")

    def test_resolution_always_dash(self):
        result = enrich_network_item(self._base(subtype="switch"))
        self.assertEqual(result["resolution"], "—")

    def test_poe_budget_preserved(self):
        result = enrich_network_item(self._base(subtype="switch", poe_budget_watts=250))
        self.assertEqual(result["poe_budget_watts"], 250)


class TestEnrichCatalogItem(unittest.TestCase):
    def test_dispatches_camera(self):
        item = {"id": "1", "name": "Cam", "brand": "X", "category": "camera", "subtype": "dome"}
        result = enrich_catalog_item(item)
        self.assertEqual(result["category"], "camera")
        self.assertIn("lensType", result)

    def test_dispatches_static(self):
        item = {"id": "2", "name": "Switch", "brand": "Y", "category": "static", "subtype": "switch"}
        result = enrich_catalog_item(item)
        self.assertEqual(result["category"], "static")


class TestBuildDeviceTypeLabel(unittest.TestCase):
    def test_camera_varifocal(self):
        label = build_device_type_label({"category": "camera", "subtype": "dome", "lensType": "varifocal"})
        self.assertEqual(label, "Camera (Dome - Varifocal)")

    def test_camera_fixed(self):
        label = build_device_type_label({"category": "camera", "subtype": "dual-dome", "lensType": "fixed"})
        self.assertEqual(label, "Camera (Dual Dome - Fixed)")

    def test_camera_no_lens(self):
        label = build_device_type_label({"category": "camera", "subtype": "ptz"})
        self.assertEqual(label, "Camera (PTZ)")

    def test_static_switch(self):
        self.assertEqual(build_device_type_label({"category": "static", "subtype": "switch"}), "Switch")

    def test_static_nvr(self):
        self.assertEqual(build_device_type_label({"category": "static", "subtype": "nvr"}), "NVR")

    def test_all_camera_subtypes_have_labels(self):
        for sub in ("dome", "bullet", "ptz", "5mp-dome", "dual-dome", "multi-view", "4k-dome", "hybrid-thermal"):
            label = build_device_type_label({"category": "camera", "subtype": sub})
            self.assertTrue(label.startswith("Camera ("), f"unexpected label for {sub}: {label}")


class TestComputeCamerasAndViews(unittest.TestCase):
    def test_single_standard_camera(self):
        devices = [{"category": "camera", "subtype": "dome"}]
        result = compute_cameras_and_views(devices)
        self.assertEqual(result["cameras"], 1)
        self.assertEqual(result["views"], 1)

    def test_dual_dome_counts_2_views(self):
        devices = [{"category": "camera", "subtype": "dual-dome"}]
        result = compute_cameras_and_views(devices)
        self.assertEqual(result["cameras"], 1)
        self.assertEqual(result["views"], VIEWS_PER_SUBTYPE["dual-dome"])

    def test_multi_view_counts_4_views(self):
        devices = [{"category": "camera", "subtype": "multi-view"}]
        result = compute_cameras_and_views(devices)
        self.assertEqual(result["views"], 4)

    def test_static_device_excluded(self):
        devices = [
            {"category": "camera", "subtype": "bullet"},
            {"category": "static", "subtype": "switch"},
        ]
        result = compute_cameras_and_views(devices)
        self.assertEqual(result["cameras"], 1)
        self.assertEqual(result["views"], 1)

    def test_mixed_fleet(self):
        devices = [
            {"category": "camera", "subtype": "bullet"},
            {"category": "camera", "subtype": "dual-dome"},
            {"category": "camera", "subtype": "multi-view"},
            {"category": "static", "subtype": "nvr"},
        ]
        result = compute_cameras_and_views(devices)
        self.assertEqual(result["cameras"], 3)
        self.assertEqual(result["views"], 1 + 2 + 4)

    def test_empty(self):
        result = compute_cameras_and_views([])
        self.assertEqual(result, {"cameras": 0, "views": 0})


if __name__ == "__main__":
    unittest.main()
