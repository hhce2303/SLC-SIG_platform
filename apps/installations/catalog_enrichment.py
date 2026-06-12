"""
catalog_enrichment.py
Port of catalogService.ts + catalog.ts enrichment helpers.
Pure Python — no DB, no Django, no side effects.
"""
from __future__ import annotations

import re
from typing import Any


# ── Default lens specs per camera subtype ─────────────────────────────────────
DEFAULT_CAM_SPECS: dict[str, dict] = {
    "bullet":         {"lensType": "varifocal", "rango_lente_mm": [2.8, 12],  "rango_fov_grados": [104, 29], "poe_watts": 8,  "bandwidth_mbps": 5},
    "dome":           {"lensType": "varifocal", "rango_lente_mm": [2.8, 12],  "rango_fov_grados": [104, 27], "poe_watts": 7,  "bandwidth_mbps": 4},
    "ptz":            {"lensType": "varifocal", "rango_lente_mm": [5,   100], "rango_fov_grados": [57,   3], "poe_watts": 25, "bandwidth_mbps": 5},
    "5mp-dome":       {"lensType": "varifocal", "rango_lente_mm": [3,    9],  "rango_fov_grados": [106, 36], "poe_watts": 9,  "bandwidth_mbps": 6},
    "dual-dome":      {"lensType": "fixed",     "lente_mm": 4,   "fov_grados": 180, "poe_watts": 12, "bandwidth_mbps": 8},
    "multi-view":     {"lensType": "fixed",     "lente_mm": 1.8, "fov_grados": 360, "poe_watts": 10, "bandwidth_mbps": 8},
    "4k-dome":        {"lensType": "varifocal", "rango_lente_mm": [2.8, 12],  "rango_fov_grados": [104, 27], "poe_watts": 8,  "bandwidth_mbps": 8},
    "hybrid-thermal": {"lensType": "varifocal", "rango_lente_mm": [7.5, 7.5], "rango_fov_grados": [40,  40], "poe_watts": 15, "bandwidth_mbps": 6},
}

# ── API subtype → canonical StaticSubtype ────────────────────────────────────
API_TO_STATIC_SUBTYPE: dict[str, str] = {
    "switch":         "switch",
    "router":         "router",
    "pdu":            "pdu",
    "da":             "speaker",
    "radio":          "radio",
    "access_control": "access-control",
    "access control": "access-control",
}

# ── Views per multi-lens camera subtype ──────────────────────────────────────
VIEWS_PER_SUBTYPE: dict[str, int] = {
    "dual-dome":      2,
    "multi-view":     4,
    "hybrid-thermal": 2,
}

# ── Label maps (port of buildDeviceTypeLabel from catalog.ts:373) ─────────────
_CAMERA_SUBTYPE_LABEL: dict[str, str] = {
    "dome":           "Dome",
    "bullet":         "Bullet",
    "ptz":            "PTZ",
    "5mp-dome":       "5MP Dome",
    "dual-dome":      "Dual Dome",
    "multi-view":     "Multi View",
    "4k-dome":        "4K Dome",
    "hybrid-thermal": "Hybrid Thermal",
}
_LENS_LABEL: dict[str, str] = {
    "fixed":    "Fixed",
    "varifocal": "Varifocal",
    "hybrid":   "Hybrid",
}
_STATIC_LABEL: dict[str, str] = {
    "speaker":         "Speaker",
    "access-point":    "Access Point",
    "keyper":          "KEYper",
    "pdu":             "Power Dist.",
    "radio":           "Wireless Radio",
    "access-control":  "Access Ctrl",
    "safe":            "Safe",
    "viewing-station": "Viewing Station",
    "nvr":             "NVR",
    "switch":          "Switch",
}


# ── Normalizers ───────────────────────────────────────────────────────────────

def normalize_camera_subtype(raw: str | None) -> str:
    """Map a raw API subtype string to one of the 8 canonical camera subtypes."""
    sub = (raw or "bullet").lower()
    if "fisheye" in sub or "panoview" in sub or "multi" in sub or "4 lens" in sub:
        return "multi-view"
    if "dual" in sub:
        return "dual-dome"
    if "5mp" in sub or "5 mp" in sub:
        return "5mp-dome"
    if "4k" in sub or "4 k" in sub:
        return "4k-dome"
    if "dome" in sub:
        return "dome"
    if "bullet" in sub:
        return "bullet"
    if "ptz" in sub or "pan" in sub or "tilt" in sub:
        return "ptz"
    if "thermal" in sub:
        return "hybrid-thermal"
    if sub in DEFAULT_CAM_SPECS:
        return sub
    return "bullet"


def normalize_static_subtype(item: dict) -> str:
    """Map a raw API item dict to one of the canonical static subtypes."""
    raw_sub = (item.get("subtype") or "").lower()
    if raw_sub in API_TO_STATIC_SUBTYPE:
        return API_TO_STATIC_SUBTYPE[raw_sub]

    text = " ".join([
        item.get("name") or "",
        item.get("type") or "",
        item.get("subtype") or "",
        item.get("brand") or "",
    ]).lower()

    if "nvr" in text or "recorder" in text or "dvr" in text:
        return "nvr"
    if "viewing" in text or "workstation" in text or " pc " in text or "desktop" in text:
        return "viewing-station"
    if "pdu" in text:
        return "pdu"
    if "speaker" in text or "audio" in text or "horn" in text or " da " in text:
        return "speaker"
    if "radio" in text or "subscriber" in text or "ptmp" in text or "ptp" in text or "antenna" in text or "bridge" in text:
        return "subscriber-module"
    if " ap " in text or "access point" in text or "wifi" in text or "wi-fi" in text:
        return "access-point"
    if "keyper" in text or "access control" in text or "reader" in text:
        return "keyper"
    if "safe" in text or "vault" in text:
        return "safe"
    return "switch"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_view_numero(view_name: str | None) -> int | None:
    """Port of parseViewNumero (catalog.ts): trailing integer from 'CAM 03' → 3."""
    if not view_name:
        return None
    m = re.search(r"(\d+)\s*$", str(view_name))
    return int(m.group(1)) if m else None


def _to_pair(raw: Any, fallback: list) -> list:
    """Coerce a list/None to a 2-element [float, float] list."""
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return [float(raw[0]), float(raw[1])]
    if isinstance(raw, (list, tuple)) and len(raw) == 1:
        return [float(raw[0]), float(raw[0])]
    return [float(x) for x in fallback]


# ── Enrichers ─────────────────────────────────────────────────────────────────

def enrich_camera_item(cam: dict) -> dict:
    """
    Port of enrichCameraModel (catalogService.ts).
    Accepts a raw camera row (from DB or API) and returns a fully-shaped CatalogItem dict.
    """
    sub = normalize_camera_subtype(cam.get("subtype"))
    specs = DEFAULT_CAM_SPECS.get(sub, DEFAULT_CAM_SPECS["bullet"])
    lens_type = cam.get("lensType") or cam.get("lens_type") or specs["lensType"]

    final_name = (
        cam.get("view_name") or cam.get("View_name") or cam.get("viewName") or cam.get("name") or ""
    )
    brand = (cam.get("brand") or "").upper()
    qty = cam.get("qty_received") if cam.get("qty_received") is not None else cam.get("qtyReceived", 0)
    _vn = cam.get("view_name") or cam.get("viewName")
    _num = _parse_view_numero(_vn)

    base: dict = {
        "id": cam.get("id"),
        "name": final_name,
        "brand": brand,
        "resolution": cam.get("resolution") or "1080p",
        "type": cam.get("type") or f"{brand} {cam.get('subtype') or 'Camera'}",
        "category": "camera",
        "subtype": sub,
        "lensType": lens_type,
        "serial": cam.get("serial") or cam.get("serial_number") or cam.get("serialNumber"),
        "ip": cam.get("ip") or cam.get("ip_address") or cam.get("ipAddress"),
        "poe_watts": cam.get("poe_watts") if cam.get("poe_watts") is not None else specs.get("poe_watts", 8),
        "bandwidth_mbps": cam.get("bandwidth_mbps") if cam.get("bandwidth_mbps") is not None else specs.get("bandwidth_mbps", 5),
        # Physical status (site mode)
        "installed": bool(cam.get("installed")),
        "qty_received": qty,
        "qtyReceived": qty,
        "view_name": _vn,
        "viewName": _vn,
        "device_id": cam.get("device_id"),
        "deviceId": cam.get("device_id"),
        "isExistingInventory": cam.get("isExistingInventory", True),
        "physical_status": cam.get("physical_status"),
        "status_key": f"camera:{_num}" if _num is not None else None,
    }

    if lens_type == "fixed":
        raw_lente = cam.get("rango_lente_mm")
        lente = (
            float(raw_lente[0]) if isinstance(raw_lente, (list, tuple)) and raw_lente
            else specs.get("lente_mm", 4)
        )
        raw_fov = cam.get("rango_fov_grados")
        fov = (
            float(raw_fov[0]) if isinstance(raw_fov, (list, tuple)) and raw_fov
            else specs.get("fov_grados", 180)
        )
        return {**base, "lente_mm": lente, "fov_grados": fov}

    if lens_type == "hybrid":
        lente_pair = _to_pair(cam.get("rango_lente_mm"), [4.8, 120])
        fov_pair = _to_pair(cam.get("rango_fov_grados"), [60, 3])
        return {
            **base,
            "panoramica": {"fov_grados": 180, "alcance_metros": 20},
            "ptz": {
                "rango_lente_mm": lente_pair,
                "rango_fov_grados": fov_pair,
                "alcance_metros": 150,
                "pan_max": 180,
            },
        }

    # varifocal (default)
    lente_pair = _to_pair(cam.get("rango_lente_mm"), specs.get("rango_lente_mm", [2.8, 12]))
    fov_pair = _to_pair(cam.get("rango_fov_grados"), specs.get("rango_fov_grados", [104, 29]))
    return {**base, "rango_lente_mm": lente_pair, "rango_fov_grados": fov_pair}


def enrich_network_item(item: dict) -> dict:
    """
    Port of enrichNetworkDevice (catalogService.ts).
    Accepts a raw network device row and returns a fully-shaped CatalogItem dict.
    """
    sub = normalize_static_subtype(item)
    qty = item.get("qty_received") if item.get("qty_received") is not None else item.get("qtyReceived", 0)
    _vn = item.get("view_name") or item.get("viewName")
    _num = _parse_view_numero(_vn)
    return {
        "id": item.get("id"),
        "name": _vn or item.get("name") or "",
        "brand": item.get("brand") or "",
        "resolution": "—",
        "type": "CORE",
        "category": "static",
        "subtype": sub,
        "serial": item.get("serial") or item.get("serial_number") or item.get("serialNumber"),
        "ip": item.get("ip") or item.get("ip_address") or item.get("ipAddress"),
        "poe_watts": item.get("poe_watts") if item.get("poe_watts") is not None else 0,
        "bandwidth_mbps": item.get("bandwidth_mbps") if item.get("bandwidth_mbps") is not None else 0,
        "poe_budget_watts": item.get("poe_budget_watts"),
        "uplink_mbps": item.get("uplink_mbps"),
        # Physical status
        "installed": bool(item.get("installed")),
        "qty_received": qty,
        "qtyReceived": qty,
        "view_name": _vn,
        "viewName": _vn,
        "device_id": item.get("device_id"),
        "deviceId": item.get("device_id"),
        "isExistingInventory": item.get("isExistingInventory", True),
        "physical_status": item.get("physical_status"),
        "status_key": f"static:{_num}" if _num is not None else None,
    }


def enrich_catalog_item(item: dict) -> dict:
    """Dispatch to enrich_camera_item or enrich_network_item based on 'category' field."""
    if (item.get("category") or "").lower() == "camera":
        return enrich_camera_item(item)
    return enrich_network_item(item)


# ── Reporting helpers ─────────────────────────────────────────────────────────

def build_device_type_label(item: dict) -> str:
    """
    Port of buildDeviceTypeLabel (catalog.ts:373).
    Returns e.g. 'Camera (Dome - Varifocal)' or 'Switch'.
    """
    if (item.get("category") or "").lower() == "camera":
        sub = _CAMERA_SUBTYPE_LABEL.get(item.get("subtype", ""), item.get("subtype", ""))
        lens = _LENS_LABEL.get(item.get("lensType", ""), "")
        details = f"{sub} - {lens}" if lens else sub
        return f"Camera ({details})"
    return _STATIC_LABEL.get(item.get("subtype", ""), item.get("subtype", ""))


def compute_cameras_and_views(devices: list[dict]) -> dict:
    """
    Port of computeCamerasAndViews (OnboardingModal.tsx:14-26).
    Each dict must have 'category' and 'subtype'.
    Returns {'cameras': int, 'views': int}.
    """
    cameras = 0
    views = 0
    for dev in devices:
        if (dev.get("category") or "").lower() != "camera":
            continue
        cameras += 1
        views += VIEWS_PER_SUBTYPE.get(dev.get("subtype") or "", 1)
    return {"cameras": cameras, "views": views}
