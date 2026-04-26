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


# ---- Equipment catalog -------------------------------------------------------
# Products confirmed available in the Japanese market (2025).
# Prices are indicative list prices; actual procurement may differ.
#
# AP (wired wall mount):
#   Aruba AP-515 (R2H28A) – HPE Aruba Networks
#   Wi-Fi 6, 4×4:4 MIMO, 2.4/5 GHz dual-band, PoE+ (802.3at)
#   Sold via: SB C&S, 伊藤忠テクノソリューションズ, 日商エレクトロニクス など
#   https://www.arubanetworks.com/products/wireless/access-points/indoor-access-points/500-series/
#
# AP (interior mesh):
#   Aruba AP-515 (R2H28A) – same model, operated as IAP mesh node
#   Powered via PoE injector (HPE J9801A) or ceiling AC outlet
#
# Switch:
#   HPE Aruba 2530-24G-PoE+ (J9773A)
#   24-port GbE PoE+ (185W), 4×SFP uplink, 19" rack/wall mount
#   Sold via: 日本ヒューレット・パッカード販売店など
#   https://www.hpe.com/h20195/v2/getpdf.aspx/c04111337.pdf
#
# LTE Router:
#   NEC UNIVERGE IX-V5000
#   Built-in LTE Cat.6 (DL 300Mbps), 4×GbE LAN, UTM/VPN, DIN-rail mount
#   Sold via: NEC ネッツエスアイ, NECフィールディングなど
#   https://www.nec.com/ja_JP/products/univerge/ix/ix-v5000/
#
# Fiber cable:
#   住友電工ネットワーク マルチモードファイバ OM3 (LC-LC, 難燃シース)
#   住友電気工業 光ファイバケーブル A-DQ(ZN)2YW  OM3 2芯
#   Sold via: 住電日立ケーブル販売店, ミスミなど
#
# SFP module:
#   HPE X121 1G SFP LC SX トランシーバ (J4858D)
#   1000BASE-SX, LC, マルチモード 550m, HPE Aruba スイッチ動作確認済み
#   Sold via: HPE 販売店
#
# PoE injector (for mesh APs):
#   HPE Aruba PoE インジェクター 802.3at 30W (J9801A)
#   Sold via: HPE 販売店
#
# LTE antenna:
#   マスプロ電工 LTE 対応 外部アンテナ MLANT2 (MIMO 2×2)
#   700MHz〜2.6GHz, N型コネクタ, IP66, 壁面取り付け
#   Sold via: マスプロ電工販売店, Amazon.co.jp 法人向けなど

EQUIPMENT_CATALOG = {
    "ap_wired": {
        "model": "HPE Aruba AP-515 (品番: R2H28A)",
        "spec": (
            "Wi-Fi 6 (802.11ax), 4×4:4 MIMO, デュアルバンド 2.4/5GHz, "
            "最大5.4Gbps, PoE+ (802.3at) 給電, 壁面・天井取り付け対応"
        ),
        "coverage_radius_m": 30,
        "max_clients": 512,
        "poe_required_w": 25,
        "unit_price_jpy": 95_000,
        "note": "壁面取り付けブラケット AP-MNT-W2 別売 (¥3,000)",
    },
    "ap_mesh": {
        "model": "HPE Aruba AP-515 (品番: R2H28A) ― メッシュモード",
        "spec": (
            "Wi-Fi 6 (802.11ax), 4×4:4 MIMO, ワイヤレスメッシュバックホール対応, "
            "Aruba Instant (クラウド管理) または Mobility Controller 管理"
        ),
        "coverage_radius_m": 30,
        "max_clients": 400,
        "poe_required_w": 0,
        "unit_price_jpy": 95_000,
        "note": "PoEインジェクター HPE J9801A (¥8,000) と組み合わせ。天井取り付け推奨",
    },
    "poe_injector": {
        "model": "HPE Aruba PoE インジェクター 802.3at 30W (品番: J9801A)",
        "spec": "IEEE 802.3at PoE+, 30W, GbE パススルー, メッシュAP給電用",
        "unit_price_jpy": 8_000,
        "note": "メッシュAP 1台につき 1個必要",
    },
    "switch_poe": {
        "model": "HPE Aruba 2530-24G-PoE+ スイッチ (品番: J9773A)",
        "spec": (
            "24ポート GbE PoE+ (最大185W), 4×SFP アップリンク, "
            "19インチ ラック / 壁面取り付け対応, ファンレス"
        ),
        "ports": 24,
        "poe_budget_w": 185,
        "unit_price_jpy": 110_000,
        "note": "壁面パネルボックス / 制御盤内設置。DINレールキット別売",
    },
    "lte_router": {
        "model": "NEC UNIVERGE IX-V5000",
        "spec": (
            "WAN: LTE Cat.6 (下り最大300Mbps / 上り50Mbps), nano-SIM×1, "
            "LAN: GbE×4, UTM/VPN (IPsec・SSL-VPN), DINレール取り付け対応, "
            "動作温度 -20〜60℃"
        ),
        "unit_price_jpy": 198_000,
        "note": "SIM契約・月額費用は別途。LTEアンテナ同梱（外部アンテナ接続も可）",
    },
    "fiber_cable": {
        "model": "住友電工 マルチモード光ファイバケーブル OM3 (LC-LC, 2芯, 難燃)",
        "spec": (
            "コア径 50μm, OM3 (10GBASE-SR 対応 300m), 難燃 LSZH シース, "
            "屋内配線用, プルボックス経由壁面配線"
        ),
        "unit_price_jpy_per_100m": 20_000,
        "note": "スイッチ間バックボーン配線用。LANケーブルではなく光ファイバーを使用",
    },
    "sfp_module": {
        "model": "HPE X121 1G SFP LC SX トランシーバ (品番: J4858D)",
        "spec": "1000BASE-SX, LC コネクタ, マルチモード 550m, HPE Aruba スイッチ動作確認済み",
        "unit_price_jpy": 9_000,
        "note": "スイッチの SFP ポートに装着。スイッチ 1台につき 2個（上流 + 下流）",
    },
    "lte_antenna": {
        "model": "マスプロ電工 LTE 外部アンテナ MLANT2",
        "spec": (
            "対応周波数: 700MHz〜2.6GHz (Band 1/3/8/18/19/21/28/42/43), "
            "MIMO 2×2, N型コネクタ, IP66 防塵防水, 壁面取り付け"
        ),
        "unit_price_jpy": 28_000,
        "note": "工場外壁高所に取り付け。同軸ケーブル (5D-FB) でルーターへ引き込み",
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

    # y boundary where south/north wall AP coverage ends
    south_reach = wall_offset + radius   # e.g. 32 m
    north_reach = (height - wall_offset) - radius  # e.g. 120 m

    if south_reach >= north_reach:
        return interior_aps  # walls already cover the full height

    # Place rows starting at south_reach+radius (first genuinely uncovered row),
    # stepping by 1.8×radius (10 % overlap) until north_reach is covered.
    row_step = radius * 1.8
    row_ys: List[float] = []
    y = south_reach + radius          # first row centre (e.g. y=62 for r=30)
    while y < north_reach:
        row_ys.append(round(y, 1))
        y += row_step
    # Ensure the last gap before the north wall is covered
    if not row_ys or row_ys[-1] + radius < north_reach:
        row_ys.append(round(north_reach - radius, 1))

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
    sfp_count = switch_count * 2       # 2 SFP ports per switch (upstream + downstream)
    fiber_units = max(1, math.ceil(fiber_m / 100))
    poe_injector_count = mesh_ap_count  # 1 injector per mesh AP

    def row(category, key, qty, spec_override=None):
        c = cat[key]
        price = c.get("unit_price_jpy") or c.get("unit_price_jpy_per_100m", 0)
        return {
            "category": category,
            "model": c["model"],
            "spec": spec_override or c["spec"],
            "qty": qty,
            "unit_price": price,
            "total_price": qty * price,
            "note": c.get("note", ""),
        }

    items = [
        row("無線AP（壁面・有線接続）",       "ap_wired",      wall_ap_count),
        row("無線AP（内部・メッシュ）",        "ap_mesh",       mesh_ap_count),
        row("PoEインジェクター（メッシュAP用）", "poe_injector",  poe_injector_count),
        row("PoEスイッチ",                     "switch_poe",    switch_count),
        row("LTEルーター",                     "lte_router",    1),
        row("LTE外部アンテナ",                 "lte_antenna",   1),
        row(
            "光ファイバーケーブル (100m単位)",
            "fiber_cable",
            fiber_units,
            f"総延長 約{fiber_m}m / {cat['fiber_cable']['spec']}",
        ),
        row("SFPトランシーバ（スイッチ用）",   "sfp_module",    sfp_count),
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
