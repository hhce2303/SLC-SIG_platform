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
