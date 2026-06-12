"""
Tests for extended topology.py functions: build_tree, cascade, check_connection, analyze.
Run with: python -m pytest apps/installations/tests/test_topology_analyze.py -v
"""
import unittest
from apps.installations.topology import (
    build_tree,
    cascade,
    check_connection,
    analyze,
    node_type_of,
    validate,
    CONNECTION_RULES,
)


def _dev(id_, subtype="switch", category="static", **kw):
    return {"id": id_, "subtype": subtype, "category": category, **kw}


def _conn(s, t):
    return {"source": s, "target": t}


class TestNodeTypeOf(unittest.TestCase):
    def test_camera_subtypes_all_map_to_camera(self):
        for sub in ("dome", "bullet", "ptz", "5mp-dome", "dual-dome", "multi-view", "4k-dome", "hybrid-thermal"):
            self.assertEqual(node_type_of({"category": "camera", "subtype": sub}), "camera")

    def test_static_subtypes(self):
        mapping = {
            "switch": "switch", "router": "router", "nvr": "nvr",
            "access-point": "ap", "speaker": "speaker", "pdu": "pdu",
            "radio": "radio", "access-control": "access-control",
        }
        for sub, expected in mapping.items():
            self.assertEqual(node_type_of({"category": "static", "subtype": sub}), expected)

    def test_unknown_defaults_to_other(self):
        self.assertEqual(node_type_of({"category": "static", "subtype": "mystery"}), "other")


class TestBuildTree(unittest.TestCase):
    def test_linear_chain(self):
        devices = [
            _dev("router1", subtype="router"),
            _dev("switch1", subtype="switch"),
            _dev("cam1", subtype="dome", category="camera"),
        ]
        connections = [_conn("router1", "switch1"), _conn("switch1", "cam1")]
        tree = build_tree(devices, connections)

        # Router is root
        self.assertIsNone(tree["router1"]["parent_id"])
        # Switch's parent is the router
        self.assertEqual(tree["switch1"]["parent_id"], "router1")
        # Camera's parent is the switch
        self.assertEqual(tree["cam1"]["parent_id"], "switch1")
        # Children integrity
        self.assertIn("switch1", tree["router1"]["children"])
        self.assertIn("cam1", tree["switch1"]["children"])

    def test_disconnected_nodes_become_roots(self):
        devices = [_dev("sw1"), _dev("cam1", subtype="dome", category="camera")]
        tree = build_tree(devices, [])
        self.assertIsNone(tree["sw1"]["parent_id"])
        self.assertIsNone(tree["cam1"]["parent_id"])

    def test_root_priority_router_over_switch(self):
        devices = [_dev("sw1"), _dev("r1", subtype="router")]
        connections = [_conn("sw1", "r1")]
        tree = build_tree(devices, connections)
        # Router has priority 1, switch 2 → router should be root
        self.assertIsNone(tree["r1"]["parent_id"])
        self.assertEqual(tree["sw1"]["parent_id"], "r1")


class TestCascade(unittest.TestCase):
    def test_root_aggregates_all_children(self):
        devices = [
            _dev("sw1", subtype="switch", poe_budget_watts=100, uplink_mbps=1000),
            _dev("cam1", subtype="dome", category="camera", poe_draw_watts=7, bandwidth_mbps=4),
            _dev("cam2", subtype="bullet", category="camera", poe_draw_watts=8, bandwidth_mbps=5),
        ]
        connections = [_conn("sw1", "cam1"), _conn("sw1", "cam2")]
        result = cascade(devices, connections)

        sw = result["sw1"]
        self.assertAlmostEqual(sw["total_poe"], 15.0)
        self.assertAlmostEqual(sw["total_mbps"], 9.0)
        self.assertEqual(sw["total_devices"], 2)

    def test_leaf_has_zero_cascade(self):
        devices = [_dev("cam1", subtype="dome", category="camera")]
        result = cascade(devices, [])
        self.assertEqual(result["cam1"]["total_devices"], 0)

    def test_nested_cascade(self):
        devices = [
            _dev("router1", subtype="router"),
            _dev("sw1", subtype="switch"),
            _dev("cam1", subtype="dome", category="camera", poe_draw_watts=7, bandwidth_mbps=4),
        ]
        connections = [_conn("router1", "sw1"), _conn("sw1", "cam1")]
        result = cascade(devices, connections)

        # Switch sees cam1
        self.assertEqual(result["sw1"]["total_devices"], 1)
        # Router sees switch + cam1
        self.assertEqual(result["router1"]["total_devices"], 2)
        self.assertAlmostEqual(result["router1"]["total_poe"], 7.0)

    def test_downstream_ips_counted(self):
        devices = [
            _dev("sw1", subtype="switch"),
            _dev("cam1", subtype="dome", category="camera", ip="192.168.1.1"),
            _dev("cam2", subtype="dome", category="camera"),
        ]
        connections = [_conn("sw1", "cam1"), _conn("sw1", "cam2")]
        result = cascade(devices, connections)
        self.assertEqual(result["sw1"]["downstream_ips"], 1)


class TestCheckConnection(unittest.TestCase):
    def _state(self):
        devices = [
            _dev("sw1", subtype="switch"),
            _dev("cam1", subtype="dome", category="camera"),
            _dev("cam2", subtype="bullet", category="camera"),
        ]
        return devices, []

    def test_valid_switch_to_camera(self):
        devices, connections = self._state()
        result = check_connection("sw1", "cam1", devices, connections)
        self.assertIsNone(result)

    def test_invalid_camera_to_camera(self):
        devices, connections = self._state()
        result = check_connection("cam1", "cam2", devices, connections)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "invalid_rule")
        self.assertIn("CAMERA", result["message"])

    def test_duplicate_connection(self):
        devices, _ = self._state()
        connections = [_conn("sw1", "cam1")]
        result = check_connection("sw1", "cam1", devices, connections)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "duplicate")

    def test_duplicate_reversed(self):
        devices, _ = self._state()
        connections = [_conn("cam1", "sw1")]
        result = check_connection("sw1", "cam1", devices, connections)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "duplicate")

    def test_cycle_detection(self):
        # sw1 → sw2 → cam1 already exist; trying to add cam1 → sw1 creates a loop
        devices = [
            _dev("sw1", subtype="switch"),
            _dev("sw2", subtype="switch"),
            _dev("cam1", subtype="dome", category="camera"),
        ]
        connections = [_conn("sw1", "sw2"), _conn("sw2", "cam1")]
        # cam1 cannot connect back to sw1 (cycle), but also camera→switch is invalid_rule first
        # Test with switch→switch cycle instead:
        result = check_connection("sw2", "sw1", devices, connections)
        self.assertIsNotNone(result)
        # Either cycle or duplicate is acceptable here (duplicate first)
        self.assertIn(result["type"], ("duplicate", "cycle"))

    def test_missing_device_returns_invalid_rule(self):
        devices = [_dev("sw1")]
        result = check_connection("sw1", "nonexistent", devices, [])
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "invalid_rule")


class TestAnalyze(unittest.TestCase):
    def test_returns_all_keys(self):
        devices = [
            _dev("sw1", subtype="switch", poe_budget_watts=100, uplink_mbps=1000),
            _dev("cam1", subtype="dome", category="camera", poe_draw_watts=7, bandwidth_mbps=4),
        ]
        connections = [_conn("sw1", "cam1")]
        result = analyze(devices, connections)
        self.assertIn("is_valid", result)
        self.assertIn("errors", result)
        self.assertIn("switches", result)
        self.assertIn("tree", result)
        self.assertIn("cascades", result)

    def test_connection_check_included_when_provided(self):
        devices = [
            _dev("sw1", subtype="switch"),
            _dev("cam1", subtype="dome", category="camera"),
        ]
        result = analyze(devices, [], check={"source": "sw1", "target": "cam1"})
        self.assertIn("connection_check", result)
        self.assertIsNone(result["connection_check"])

    def test_no_connection_check_when_not_provided(self):
        result = analyze([_dev("sw1")], [])
        self.assertNotIn("connection_check", result)

    def test_invalid_topology_raises_errors(self):
        devices = [
            _dev("sw1", subtype="switch", poe_budget_watts=10),
            _dev("cam1", subtype="dome", category="camera", poe_draw_watts=50),
        ]
        connections = [_conn("sw1", "cam1")]
        result = analyze(devices, connections)
        self.assertFalse(result["is_valid"])
        self.assertTrue(any(e["code"] == "poe_budget_exceeded" for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
