"""
Factory Wi-Fi Network Design Engine

Placement strategy:
- Infrastructure (switches, LTE router) along walls, connected by short cable (≤5m)
- Wall APs wired to wall switches via PoE (≤5m cable)
- Interior APs use wireless mesh backhaul where cable cannot reach
- Fiber backbone (not LAN cable) connects distributed switches across factory
"""

import math
from typing import List, Dict, Tuple

# ---- Constants ---------------------------------------------------------------
AP_COVERAGE_RADIUS_M = 30   # Conservative for factory (metal, interference)
WALL_OFFSET_M = 2           # Equipment placed this far from wall (m)
MAX_LAN_CABLE_M = 5         # Hard limit for copper LAN cable
AP_SPACING_M = 50           # Default grid spacing for wall APs


# ---- Equipment catalog (Japanese market, indicative 2024 prices) -------------
EQUIPMENT_CATALOG = {
    "ap_enterprise": {
        "model": "Cisco Meraki MR46",
        "spec": "Wi-Fi 6 (802.11ax), 2×2:2 MIMO, 2.4/5GHz デュアルバンド",
        "coverage_radius_m": 30,
        "max_clients": 100,
        "poe_required_w": 25,
        "unit_price_jpy": 150_000,
        "note": "壁面・天井取り付け対応、工場向け",
    },
    "ap_mesh": {
        "model": "Cisco Meraki MR46 (メッシュ)",
        "spec": "Wi-Fi 6, ワイヤレスバックホール対応、天井取り付け",
        "coverage_radius_m": 30,
        "max_clients": 80,
        "poe_required_w": 0,
        "unit_price_jpy": 150_000,
        "note": "AC電源またはPoEインジェクター経由で給電",
    },
    "switch_poe": {
        "model": "Cisco Catalyst 1000-24P-4G-L",
        "spec": "24ポート PoE+ (370W), 4×SFP アップリンク, ラックマウント",
        "ports": 24,
        "poe_budget_w": 370,
        "unit_price_jpy": 130_000,
        "note": "壁面パネルボックス内設置",
    },
    "lte_router": {
        "model": "Yamaha RTX830 + LTEモジュール",
        "spec": "WAN: LTE Cat.4 (下り150Mbps), LAN: 4×GbE, UTM機能搭載",
        "unit_price_jpy": 120_000,
        "note": "外部LTEアンテナ（壁面引き出し）と組み合わせ",
    },
    "fiber_cable": {
        "model": "マルチモードファイバケーブル OM4 (LC-LC)",
        "spec": "コア径50μm, 400Gbps対応, 難燃シース",
        "unit_price_jpy_per_100m": 18_000,
        "note": "スイッチ間の長距離バックボーン配線に使用",
    },
    "sfp_module": {
        "model": "SFP+ マルチモードモジュール (1G)",
        "spec": "1000BASE-SX, LC, 550m対応",
        "unit_price_jpy": 8_000,
        "note": "スイッチのSFPポートに装着",
    },
    "lte_antenna": {
        "model": "LTE 外部アンテナ (4×4 MIMO)",
        "spec": "700MHz～2.6GHz対応, N型コネクタ, 防水IP67",
        "unit_price_jpy": 25_000,
        "note": "工場外壁に取り付け、同軸ケーブルでルーターへ",
    },
    "cable_tray": {
        "model": "壁面ケーブルトレイ (50mm幅)",
        "spec": "スチール製, 壁面固定, 2mユニット",
        "unit_price_jpy_per_2m": 3_000,
        "note": "壁際の短距離ケーブル整理に使用",
    },
}


# ---- Core placement functions ------------------------------------------------

def _place_wall_aps(
    width: float, height: float, spacing: float, wall_offset: float
) -> List[Dict]:
    """Place APs at regular intervals along all 4 walls."""
    aps = []
    ap_id = 1

    # South wall  (y = wall_offset)
    x = spacing / 2
    while x < width:
        aps.append({
            "id": f"AP-W{ap_id:02d}",
            "x": round(x, 1),
            "y": wall_offset,
            "type": "wired",
            "wall": "south",
            "coverage_radius": AP_COVERAGE_RADIUS_M,
        })
        ap_id += 1
        x += spacing

    # North wall  (y = height - wall_offset)
    x = spacing / 2
    while x < width:
        aps.append({
            "id": f"AP-W{ap_id:02d}",
            "x": round(x, 1),
            "y": round(height - wall_offset, 1),
            "type": "wired",
            "wall": "north",
            "coverage_radius": AP_COVERAGE_RADIUS_M,
        })
        ap_id += 1
        x += spacing

    # West wall  (x = wall_offset) – skip corner zones already covered
    y = spacing
    while y < height - spacing / 2:
        aps.append({
            "id": f"AP-W{ap_id:02d}",
            "x": wall_offset,
            "y": round(y, 1),
            "type": "wired",
            "wall": "west",
            "coverage_radius": AP_COVERAGE_RADIUS_M,
        })
        ap_id += 1
        y += spacing

    # East wall  (x = width - wall_offset)
    y = spacing
    while y < height - spacing / 2:
        aps.append({
            "id": f"AP-W{ap_id:02d}",
            "x": round(width - wall_offset, 1),
            "y": round(y, 1),
            "type": "wired",
            "wall": "east",
            "coverage_radius": AP_COVERAGE_RADIUS_M,
        })
        ap_id += 1
        y += spacing

    return aps


def _place_interior_mesh_aps(
    wall_aps: List[Dict], width: float, height: float,
    spacing: float, radius: float, wall_offset: float,
) -> List[Dict]:
    """Add mesh APs wherever wall APs leave coverage gaps."""
    all_aps = list(wall_aps)  # working copy
    interior_aps = []
    ap_id = len(wall_aps) + 1

    # Interior band not reached by north/south wall APs
    south_reach = wall_offset + radius
    north_reach = (height - wall_offset) - radius
    interior_height = north_reach - south_reach

    if interior_height <= 0:
        return interior_aps  # walls already cover everything

    # Rows needed: each row covers 2×radius, rows overlap slightly
    num_rows = max(1, math.ceil(interior_height / (radius * 1.8)))
    row_ys = [
        round(south_reach + (interior_height / (num_rows - 1)) * i, 1)
        if num_rows > 1
        else round((south_reach + north_reach) / 2, 1)
        for i in range(num_rows)
    ]

    for row_y in row_ys:
        x = spacing / 2
        while x < width:
            # Only add if not already covered by a walled AP
            if not _is_point_covered(x, row_y, all_aps, radius):
                ap = {
                    "id": f"AP-M{ap_id:02d}",
                    "x": round(x, 1),
                    "y": row_y,
                    "type": "mesh",
                    "wall": None,
                    "coverage_radius": AP_COVERAGE_RADIUS_M,
                }
                interior_aps.append(ap)
                all_aps.append(ap)
                ap_id += 1
            x += spacing

    return interior_aps


def _is_point_covered(x: float, y: float, aps: List[Dict], radius: float) -> bool:
    for ap in aps:
        dx, dy = x - ap["x"], y - ap["y"]
        if math.sqrt(dx * dx + dy * dy) <= radius:
            return True
    return False


def _assign_switches(wall_aps: List[Dict]) -> List[Dict]:
    """Create PoE switches and assign nearby wall APs to each."""
    APS_PER_SWITCH = 8  # conservative: leaves headroom for future ports

    by_wall: Dict[str, List[Dict]] = {"south": [], "north": [], "west": [], "east": []}
    for ap in wall_aps:
        by_wall[ap["wall"]].append(ap)

    switches = []
    sw_num = 1

    for wall, aps in by_wall.items():
        # Sort along the wall axis for natural grouping
        sort_key = "x" if wall in ("south", "north") else "y"
        sorted_aps = sorted(aps, key=lambda a: a[sort_key])

        for i in range(0, len(sorted_aps), APS_PER_SWITCH):
            group = sorted_aps[i : i + APS_PER_SWITCH]
            sw_x = round(sum(a["x"] for a in group) / len(group), 1)
            sw_y = round(sum(a["y"] for a in group) / len(group), 1)
            switches.append({
                "id": f"SW-{sw_num:02d}",
                "x": sw_x,
                "y": sw_y,
                "wall": wall,
                "port_count": 24,
                "poe": True,
                "assigned_ap_ids": [a["id"] for a in group],
            })
            sw_num += 1

    return switches


def _calculate_fiber_backbone(switches: List[Dict], lte_router: Dict) -> Tuple[List[Dict], int]:
    """Plan fiber runs connecting switches to LTE router along perimeter."""
    # Simplified: daisy-chain from LTE router in wall order
    ordered = sorted(switches, key=lambda s: (s["wall"], s["x"] if s["wall"] in ("south", "north") else s["y"]))
    nodes = [lte_router] + ordered
    runs = []
    total = 0
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        # Route along perimeter (Manhattan distance + 20% margin)
        length = round((abs(b["x"] - a["x"]) + abs(b["y"] - a["y"])) * 1.2)
        runs.append({"from": a["id"], "to": b["id"], "length_m": max(length, 5)})
        total += max(length, 5)
    return runs, total


def _calculate_coverage_pct(aps: List[Dict], width: float, height: float, step: int = 5) -> float:
    """Sample grid to estimate coverage percentage."""
    covered = total = 0
    xs = [step * i + step / 2 for i in range(int(width / step))]
    ys = [step * j + step / 2 for j in range(int(height / step))]
    for x in xs:
        for y in ys:
            total += 1
            if _is_point_covered(x, y, aps, AP_COVERAGE_RADIUS_M):
                covered += 1
    return round(covered / total * 100, 1) if total else 0.0


def _build_bom(
    wall_ap_count: int, mesh_ap_count: int,
    switch_count: int, fiber_m: int,
) -> List[Dict]:
    cat = EQUIPMENT_CATALOG
    sfp_count = switch_count * 2  # 2 SFP ports per switch (upstream + downstream)
    fiber_units = max(1, math.ceil(fiber_m / 100))
    items = [
        {
            "category": "無線アクセスポイント（有線接続）",
            "model": cat["ap_enterprise"]["model"],
            "spec": cat["ap_enterprise"]["spec"],
            "qty": wall_ap_count,
            "unit_price": cat["ap_enterprise"]["unit_price_jpy"],
            "total_price": wall_ap_count * cat["ap_enterprise"]["unit_price_jpy"],
            "note": cat["ap_enterprise"]["note"],
        },
        {
            "category": "無線アクセスポイント（メッシュ）",
            "model": cat["ap_mesh"]["model"],
            "spec": cat["ap_mesh"]["spec"],
            "qty": mesh_ap_count,
            "unit_price": cat["ap_mesh"]["unit_price_jpy"],
            "total_price": mesh_ap_count * cat["ap_mesh"]["unit_price_jpy"],
            "note": cat["ap_mesh"]["note"],
        },
        {
            "category": "PoEスイッチ",
            "model": cat["switch_poe"]["model"],
            "spec": cat["switch_poe"]["spec"],
            "qty": switch_count,
            "unit_price": cat["switch_poe"]["unit_price_jpy"],
            "total_price": switch_count * cat["switch_poe"]["unit_price_jpy"],
            "note": cat["switch_poe"]["note"],
        },
        {
            "category": "LTEルーター",
            "model": cat["lte_router"]["model"],
            "spec": cat["lte_router"]["spec"],
            "qty": 1,
            "unit_price": cat["lte_router"]["unit_price_jpy"],
            "total_price": cat["lte_router"]["unit_price_jpy"],
            "note": cat["lte_router"]["note"],
        },
        {
            "category": "LTE外部アンテナ",
            "model": cat["lte_antenna"]["model"],
            "spec": cat["lte_antenna"]["spec"],
            "qty": 1,
            "unit_price": cat["lte_antenna"]["unit_price_jpy"],
            "total_price": cat["lte_antenna"]["unit_price_jpy"],
            "note": cat["lte_antenna"]["note"],
        },
        {
            "category": "光ファイバーケーブル (100m単位)",
            "model": cat["fiber_cable"]["model"],
            "spec": f"総延長 {fiber_m}m / {cat['fiber_cable']['spec']}",
            "qty": fiber_units,
            "unit_price": cat["fiber_cable"]["unit_price_jpy_per_100m"],
            "total_price": fiber_units * cat["fiber_cable"]["unit_price_jpy_per_100m"],
            "note": cat["fiber_cable"]["note"],
        },
        {
            "category": "SFP+モジュール",
            "model": cat["sfp_module"]["model"],
            "spec": cat["sfp_module"]["spec"],
            "qty": sfp_count,
            "unit_price": cat["sfp_module"]["unit_price_jpy"],
            "total_price": sfp_count * cat["sfp_module"]["unit_price_jpy"],
            "note": cat["sfp_module"]["note"],
        },
    ]
    return items


def _build_ip_plan(switches: List[Dict], all_aps: List[Dict]) -> Dict:
    return {
        "subnet": "192.168.10.0/24",
        "gateway": "192.168.10.1",
        "lte_router": "192.168.10.1",
        "switches": {sw["id"]: f"192.168.10.{10 + i}" for i, sw in enumerate(switches)},
        "aps": {ap["id"]: f"192.168.10.{50 + i}" for i, ap in enumerate(all_aps)},
        "dhcp_range": "192.168.10.100 – 192.168.10.254",
        "dns_primary": "8.8.8.8",
        "dns_secondary": "8.8.4.4",
    }


# ---- Main entry point --------------------------------------------------------

def calculate_network_design(width: float, height: float, requirements: dict = None) -> dict:
    if requirements is None:
        requirements = {}

    spacing = float(requirements.get("ap_spacing", AP_SPACING_M))
    radius = float(requirements.get("coverage_radius", AP_COVERAGE_RADIUS_M))
    ssid = requirements.get("ssid", "FACTORY-WIFI")

    # LTE router: west wall, vertically centred
    lte_router = {"id": "LTE-ROUTER", "x": WALL_OFFSET_M, "y": round(height / 2, 1)}

    wall_aps = _place_wall_aps(width, height, spacing, WALL_OFFSET_M)
    mesh_aps = _place_interior_mesh_aps(wall_aps, width, height, spacing, radius, WALL_OFFSET_M)
    all_aps = wall_aps + mesh_aps

    switches = _assign_switches(wall_aps)
    fiber_runs, fiber_total_m = _calculate_fiber_backbone(switches, lte_router)
    coverage_pct = _calculate_coverage_pct(all_aps, width, height)
    bom = _build_bom(len(wall_aps), len(mesh_aps), len(switches), fiber_total_m)
    ip_plan = _build_ip_plan(switches, all_aps)

    total_cost = sum(item["total_price"] for item in bom)

    return {
        "factory": {"width": width, "height": height, "area_m2": width * height},
        "lte_router": lte_router,
        "access_points": all_aps,
        "switches": switches,
        "fiber_runs": fiber_runs,
        "stats": {
            "total_aps": len(all_aps),
            "wired_aps": len(wall_aps),
            "mesh_aps": len(mesh_aps),
            "switch_count": len(switches),
            "fiber_total_m": fiber_total_m,
            "coverage_percentage": coverage_pct,
        },
        "network_config": {
            "ssid": ssid,
            "frequency_bands": "2.4GHz / 5GHz デュアルバンド",
            "security": "WPA3-Enterprise (802.1X)",
            "channel_plan_24ghz": "1 / 6 / 11 (チャンネルプラン)",
            "channel_plan_5ghz": "36 / 40 / 44 / 48 / 149 / 153 / 157 / 161",
            "qos": "有効（音声・映像トラフィック優先）",
            "roaming": "802.11r (Fast BSS Transition) 有効",
        },
        "ip_plan": ip_plan,
        "equipment_bom": bom,
        "total_cost_jpy": total_cost,
    }


# ---- SVG floor plan ----------------------------------------------------------

def generate_floor_plan_svg(design: dict) -> str:
    factory = design["factory"]
    W, H = factory["width"], factory["height"]

    SCALE = 1.6          # px per meter
    PAD_LEFT = 50
    PAD_TOP = 30
    PAD_RIGHT = 20
    PAD_BOTTOM = 40

    svg_w = int(W * SCALE) + PAD_LEFT + PAD_RIGHT
    svg_h = int(H * SCALE) + PAD_TOP + PAD_BOTTOM

    def tx(x):  # transform coordinates to SVG space
        return round(PAD_LEFT + x * SCALE, 1)

    def ty(y):  # flip Y so south=bottom
        return round(PAD_TOP + (H - y) * SCALE, 1)

    elements = []

    # ---- Background grid (50m) ----
    GRID = 50
    gx = GRID
    while gx < W:
        lx = tx(gx)
        elements.append(f'<line x1="{lx}" y1="{PAD_TOP}" x2="{lx}" y2="{PAD_TOP + int(H*SCALE)}" stroke="#ddd" stroke-width="0.5"/>')
        elements.append(f'<text x="{lx}" y="{PAD_TOP - 6}" font-size="9" text-anchor="middle" fill="#aaa">{int(gx)}m</text>')
        gx += GRID
    gy = GRID
    while gy < H:
        ly = ty(gy)
        elements.append(f'<line x1="{PAD_LEFT}" y1="{ly}" x2="{PAD_LEFT + int(W*SCALE)}" y2="{ly}" stroke="#ddd" stroke-width="0.5"/>')
        elements.append(f'<text x="{PAD_LEFT - 6}" y="{ly + 4}" font-size="9" text-anchor="end" fill="#aaa">{int(gy)}m</text>')
        gy += GRID

    # ---- Factory outline ----
    elements.append(
        f'<rect x="{PAD_LEFT}" y="{PAD_TOP}" '
        f'width="{int(W*SCALE)}" height="{int(H*SCALE)}" '
        f'fill="#fafafa" stroke="#444" stroke-width="2.5"/>'
    )

    # ---- AP coverage circles ----
    for ap in design["access_points"]:
        cx, cy = tx(ap["x"]), ty(ap["y"])
        r = round(ap["coverage_radius"] * SCALE, 1)
        if ap["type"] == "wired":
            fill, stroke = "#3B82F6", "#2563EB"
        else:
            fill, stroke = "#F59E0B", "#D97706"
        elements.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="{fill}" fill-opacity="0.08" '
            f'stroke="{stroke}" stroke-width="0.8" stroke-dasharray="4,3"/>'
        )

    # ---- Fiber backbone lines ----
    sw_map = {s["id"]: s for s in design["switches"]}
    sw_map["LTE-ROUTER"] = design["lte_router"]
    for run in design.get("fiber_runs", []):
        a = sw_map.get(run["from"])
        b = sw_map.get(run["to"])
        if a and b:
            elements.append(
                f'<line x1="{tx(a["x"])}" y1="{ty(a["y"])}" '
                f'x2="{tx(b["x"])}" y2="{ty(b["y"])}" '
                f'stroke="#7C3AED" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.6"/>'
            )

    # ---- Switches ----
    for sw in design["switches"]:
        sx, sy = tx(sw["x"]), ty(sw["y"])
        elements.append(
            f'<rect x="{sx-9}" y="{sy-6}" width="18" height="12" '
            f'fill="#10B981" rx="2" stroke="#059669" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{sx}" y="{sy+4}" font-size="7" '
            f'text-anchor="middle" fill="white" font-weight="bold">{sw["id"]}</text>'
        )

    # ---- Access Points ----
    for ap in design["access_points"]:
        cx, cy = tx(ap["x"]), ty(ap["y"])
        if ap["type"] == "wired":
            color = "#2563EB"
            elements.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}" stroke="white" stroke-width="1.5"/>')
        else:
            color = "#D97706"
            elements.append(f'<rect x="{cx-5}" y="{cy-5}" width="10" height="10" fill="{color}" stroke="white" stroke-width="1.5" rx="2"/>')
        elements.append(
            f'<text x="{cx}" y="{cy+14}" font-size="6.5" '
            f'text-anchor="middle" fill="{color}">{ap["id"]}</text>'
        )

    # ---- LTE Router ----
    lte = design["lte_router"]
    lx, ly = tx(lte["x"]), ty(lte["y"])
    elements.append(
        f'<rect x="{lx-12}" y="{ly-9}" width="24" height="18" '
        f'fill="#7C3AED" rx="3" stroke="#6D28D9" stroke-width="1.5"/>'
    )
    elements.append(
        f'<text x="{lx}" y="{ly-1}" font-size="7" text-anchor="middle" fill="white" font-weight="bold">LTE</text>'
    )
    elements.append(
        f'<text x="{lx}" y="{ly+8}" font-size="6" text-anchor="middle" fill="#DDD6FE">Router</text>'
    )

    # ---- Dimension labels ----
    elements.append(
        f'<text x="{PAD_LEFT + int(W*SCALE/2)}" y="{svg_h - 8}" '
        f'font-size="11" text-anchor="middle" fill="#555">工場幅: {W}m</text>'
    )
    elements.append(
        f'<text x="10" y="{PAD_TOP + int(H*SCALE/2)}" '
        f'font-size="11" text-anchor="middle" fill="#555" '
        f'transform="rotate(-90 10 {PAD_TOP + int(H*SCALE/2)})">工場奥行: {H}m</text>'
    )

    # ---- Scale bar ----
    sb_x = PAD_LEFT + int(W * SCALE) - 10
    sb_y = svg_h - 12
    sb_len = int(50 * SCALE)
    elements.append(f'<line x1="{sb_x - sb_len}" y1="{sb_y}" x2="{sb_x}" y2="{sb_y}" stroke="#555" stroke-width="2"/>')
    elements.append(f'<line x1="{sb_x - sb_len}" y1="{sb_y-4}" x2="{sb_x - sb_len}" y2="{sb_y+4}" stroke="#555" stroke-width="2"/>')
    elements.append(f'<line x1="{sb_x}" y1="{sb_y-4}" x2="{sb_x}" y2="{sb_y+4}" stroke="#555" stroke-width="2"/>')
    elements.append(f'<text x="{sb_x - sb_len//2}" y="{sb_y - 6}" font-size="9" text-anchor="middle" fill="#555">50m</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">'
        + "".join(elements)
        + "</svg>"
    )
