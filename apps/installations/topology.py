"""
Pure topology validation for the installations canvas.

No DB, no Django, no third-party deps (networkx is NOT in the runtime image).
Takes the device specs and connections the frontend already holds in memory
and returns validation results, so the browser stops running DFS/BFS + PoE
summation on every interaction.

Contract
--------
devices: list of dicts. Recognised keys (all optional except ``id``):
    id                str   — node id (e.g. "switch-5", instanceId)
    type              str   — informational ("camera", "switch", ...)
    poe_draw_watts    float — power this device CONSUMES (cameras, APs)
    poe_budget_watts  float — power this device SUPPLIES; set only on PoE
                              sources (switches / injectors). Presence marks
                              the device as a "source/switch" for stats.
    bandwidth_mbps    float — this device's bandwidth demand (endpoints)
    uplink_mbps       float — uplink capacity (switches)
    port_count        int   — physical port count (switches)

connections: list of dicts:
    source, target    str   — node ids
    type              str   — "cable" | "wireless" | ...
    bandwidth_mbps    float — per-link demand (fallback when the peer device
                              carries no bandwidth_mbps)

PoE and bandwidth are accounted for *directly attached* peers (a switch powers
the devices plugged into its own ports — physically correct; downstream
switches carry their own budget). Loop detection is global across the graph.
"""
from __future__ import annotations


def _num(value) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _find(parent: dict, node):
    """Union-find root with path compression."""
    root = node
    while parent[root] != root:
        root = parent[root]
    while parent[node] != root:
        parent[node], node = root, parent[node]
    return root


def detect_loops(node_ids, connections) -> list[tuple]:
    """
    Return the list of (source, target) edges that close a cycle, using
    undirected union-find. Edges referencing unknown nodes are tolerated
    (the node is added on the fly).
    """
    parent = {n: n for n in node_ids}
    cycle_edges = []
    for c in connections:
        s, t = c.get("source"), c.get("target")
        if s is None or t is None:
            continue
        parent.setdefault(s, s)
        parent.setdefault(t, t)
        if s == t:  # self-loop
            cycle_edges.append((s, t))
            continue
        rs, rt = _find(parent, s), _find(parent, t)
        if rs == rt:
            cycle_edges.append((s, t))
        else:
            parent[rs] = rt
    return cycle_edges


def validate(devices, connections) -> dict:
    """
    Validate a canvas topology. Returns:
        {
          "is_valid": bool,
          "errors":   [{code, message, device_id, nodes}],
          "switches": [{device_id, poe_used_watts, poe_budget_watts,
                        poe_remaining_watts, bandwidth_used_mbps, uplink_mbps,
                        ports_used, port_count}],
        }
    """
    by_id = {d["id"]: d for d in devices if d.get("id") is not None}
    errors: list[dict] = []

    # 1) Loops --------------------------------------------------------------
    for s, t in detect_loops(by_id.keys(), connections):
        errors.append({
            "code": "loop_detected",
            "message": f"Connection between '{s}' and '{t}' closes a loop.",
            "device_id": None,
            "nodes": [s, t],
        })

    # 2) Per-device direct-neighbour load ----------------------------------
    agg = {nid: {"poe_used": 0.0, "bw_used": 0.0, "ports_used": 0} for nid in by_id}
    for c in connections:
        s, t = c.get("source"), c.get("target")
        link_bw = _num(c.get("bandwidth_mbps"))
        for near, far in ((s, t), (t, s)):
            dev = by_id.get(near)
            if dev is None:
                continue
            a = agg[near]
            a["ports_used"] += 1
            peer = by_id.get(far)
            # PoE the source supplies to a directly-attached powered device.
            if dev.get("poe_budget_watts") is not None and peer is not None:
                a["poe_used"] += _num(peer.get("poe_draw_watts"))
            # Bandwidth demand of the attached peer (fallback to the link's).
            peer_bw = _num(peer.get("bandwidth_mbps")) if peer is not None else 0.0
            a["bw_used"] += peer_bw or link_bw

    # 3) Per-switch stats + budget checks ----------------------------------
    switches: list[dict] = []
    for nid, dev in by_id.items():
        budget = dev.get("poe_budget_watts")
        uplink = dev.get("uplink_mbps")
        ports = dev.get("port_count")
        is_source = budget is not None or uplink is not None or ports is not None
        if not is_source:
            continue

        a = agg[nid]
        switches.append({
            "device_id": nid,
            "poe_used_watts": round(a["poe_used"], 3),
            "poe_budget_watts": budget,
            "poe_remaining_watts": round(budget - a["poe_used"], 3) if budget is not None else None,
            "bandwidth_used_mbps": round(a["bw_used"], 3),
            "uplink_mbps": uplink,
            "ports_used": a["ports_used"],
            "port_count": ports,
        })

        if budget is not None and a["poe_used"] > budget:
            errors.append({
                "code": "poe_budget_exceeded",
                "message": (f"Switch '{nid}' draws {round(a['poe_used'], 1)}W "
                            f"but its PoE budget is {budget}W."),
                "device_id": nid,
                "nodes": [],
            })
        if uplink is not None and a["bw_used"] > uplink:
            errors.append({
                "code": "bandwidth_exceeded",
                "message": (f"Switch '{nid}' carries {round(a['bw_used'], 1)} Mbps "
                            f"but its uplink is {uplink} Mbps."),
                "device_id": nid,
                "nodes": [],
            })
        if ports is not None and a["ports_used"] > ports:
            errors.append({
                "code": "ports_exceeded",
                "message": (f"Switch '{nid}' uses {a['ports_used']} ports "
                            f"but only has {ports}."),
                "device_id": nid,
                "nodes": [],
            })

    return {"is_valid": not errors, "errors": errors, "switches": switches}


# ─── Extended topology: tree + cascade + connection check ─────────────────────

# Port of DEFAULT_NET_RULES (rules.ts)
CONNECTION_RULES: dict[str, dict] = {
    "router":         {"can_connect_to": ["switch", "firewall", "router", "nvr", "ap", "camera", "speaker", "radio", "pdu", "access-control", "other"]},
    "switch":         {"can_connect_to": ["switch", "router", "camera", "ap", "speaker", "nvr", "firewall", "radio", "pdu", "access-control", "other"]},
    "nvr":            {"can_connect_to": ["switch", "router", "camera", "radio"]},
    "firewall":       {"can_connect_to": ["switch", "router"]},
    "camera":         {"can_connect_to": []},
    "ap":             {"can_connect_to": ["camera", "speaker", "access-control", "radio", "ap"]},
    "speaker":        {"can_connect_to": []},
    "pdu":            {"can_connect_to": []},
    "radio":          {"can_connect_to": ["switch", "router", "camera", "ap", "radio", "other"]},
    "access-control": {"can_connect_to": []},
    "other":          {"can_connect_to": ["switch", "router", "camera", "ap", "speaker", "nvr", "firewall", "pdu", "radio", "access-control", "other"]},
}

# Subtype → topology node type (port of TopologyEngine.determineNodeType)
_SUBTYPE_TO_NODE: dict[str, str] = {
    "switch":            "switch",
    "router":            "router",
    "nvr":               "nvr",
    "access-point":      "ap",
    "speaker":           "speaker",
    "pdu":               "pdu",
    "radio":             "radio",
    "subscriber-module": "radio",
    "access-control":    "access-control",
    "keyper":            "other",
    "safe":              "other",
    "viewing-station":   "other",
}
_CAMERA_SUBTYPES = {
    "dome", "bullet", "ptz", "5mp-dome", "dual-dome", "multi-view", "4k-dome", "hybrid-thermal"
}
# BFS priority: lower = closer to root
_NODE_PRIORITY = {
    "router": 1, "firewall": 1, "nvr": 1,
    "switch": 2,
    "pdu": 3, "ap": 3, "radio": 3,
}


def node_type_of(device: dict) -> str:
    """Map a device dict (with 'category' and 'subtype') to a topology node type."""
    sub = (device.get("subtype") or "").lower()
    cat = (device.get("category") or "").lower()
    if cat == "camera" or sub in _CAMERA_SUBTYPES:
        return "camera"
    return _SUBTYPE_TO_NODE.get(sub, "other")


def build_tree(devices: list[dict], connections: list[dict]) -> dict[str, dict]:
    """
    BFS spanning tree. Returns {node_id: {parent_id: str|None, children: list[str]}}.
    Port of TopologyEngine.computeTree (TopologyEngine.ts:121-181).
    """
    by_id = {d["id"]: d for d in devices if d.get("id") is not None}
    tree: dict[str, dict] = {nid: {"parent_id": None, "children": []} for nid in by_id}

    adj: dict[str, list[str]] = {nid: [] for nid in by_id}
    for c in connections:
        s, t = c.get("source"), c.get("target")
        if s in adj and t in adj:
            adj[s].append(t)
            adj[t].append(s)

    visited: set[str] = set()
    sorted_nodes = sorted(by_id.keys(), key=lambda nid: _NODE_PRIORITY.get(node_type_of(by_id[nid]), 4))

    for root_id in sorted_nodes:
        if root_id in visited:
            continue
        queue = [root_id]
        visited.add(root_id)
        while queue:
            cur = queue.pop(0)
            for nb in adj.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    tree[nb]["parent_id"] = cur
                    tree[cur]["children"].append(nb)
                    queue.append(nb)

    return tree


def _cascade_dfs(node_id: str, tree: dict, by_id: dict, result: dict) -> dict:
    """DFS post-order: accumulate totals for node_id's subtree (excluding itself)."""
    total_poe = 0.0
    total_mbps = 0.0
    downstream_ips = 0
    total_devices = 0

    for child_id in tree.get(node_id, {}).get("children", []):
        child = by_id.get(child_id, {})
        child_subtree = _cascade_dfs(child_id, tree, by_id, result)

        total_poe += _num(child.get("poe_draw_watts")) + child_subtree["total_poe"]
        total_mbps += _num(child.get("bandwidth_mbps")) + child_subtree["total_mbps"]
        downstream_ips += (1 if child.get("ip") else 0) + child_subtree["downstream_ips"]
        total_devices += 1 + child_subtree["total_devices"]

    result[node_id] = {
        "total_poe": round(total_poe, 3),
        "total_mbps": round(total_mbps, 3),
        "downstream_ips": downstream_ips,
        "total_devices": total_devices,
    }
    return result[node_id]


def cascade(devices: list[dict], connections: list[dict]) -> dict[str, dict]:
    """
    Compute downstream aggregates for every node in the tree.
    Returns {node_id: {total_poe, total_mbps, downstream_ips, total_devices}}.
    """
    by_id = {d["id"]: d for d in devices if d.get("id") is not None}
    tree = build_tree(devices, connections)
    result: dict[str, dict] = {}
    roots = [nid for nid, node in tree.items() if node["parent_id"] is None]
    for root_id in roots:
        _cascade_dfs(root_id, tree, by_id, result)
    return result


def check_connection(
    source_id: str,
    target_id: str,
    devices: list[dict],
    connections: list[dict],
) -> dict | None:
    """
    Check whether adding a connection source→target is valid.
    Port of TopologyEngine.validateNewConnection (TopologyEngine.ts:60-101).
    Returns {'type': 'invalid_rule'|'duplicate'|'cycle', 'message': str} or None.
    """
    by_id = {d["id"]: d for d in devices if d.get("id") is not None}
    src = by_id.get(source_id)
    tgt = by_id.get(target_id)

    if src is None or tgt is None:
        return {"type": "invalid_rule", "message": "One or both devices do not exist."}

    src_type = node_type_of(src)
    tgt_type = node_type_of(tgt)

    # 1. Rule check
    allowed = CONNECTION_RULES.get(src_type, CONNECTION_RULES["other"])["can_connect_to"]
    if tgt_type != "other" and tgt_type not in allowed:
        return {
            "type": "invalid_rule",
            "message": f"A {src_type.upper()} cannot provide connection to a {tgt_type.upper()}.",
        }

    # 2. Duplicate check
    for c in connections:
        s, t = c.get("source"), c.get("target")
        if (s == source_id and t == target_id) or (s == target_id and t == source_id):
            return {"type": "duplicate", "message": "These devices are already connected."}

    # 3. Cycle check — build the tree with existing connections and walk upward from source
    tree = build_tree(devices, connections)
    current = source_id
    visited: set[str] = set()
    while current:
        if current == target_id:
            return {"type": "cycle", "message": "This connection creates a network loop (cycle)."}
        if current in visited:
            break
        visited.add(current)
        current = tree.get(current, {}).get("parent_id")  # type: ignore[assignment]

    return None


def analyze(devices: list[dict], connections: list[dict], check: dict | None = None) -> dict:
    """
    Full topology analysis.
    Returns validate() result + 'tree' + 'cascades' + optional 'connection_check'.
    """
    result = validate(devices, connections)
    result["tree"] = build_tree(devices, connections)
    result["cascades"] = cascade(devices, connections)
    if check is not None:
        result["connection_check"] = check_connection(
            check.get("source", ""),
            check.get("target", ""),
            devices,
            connections,
        )
    return result
