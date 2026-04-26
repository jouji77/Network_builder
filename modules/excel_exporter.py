"""Generate an Excel workbook from a network design result dict."""

import io
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

# ---- Palette -----------------------------------------------------------------
C_HEADER_DARK  = "1E293B"   # slate-900
C_HEADER_BLUE  = "1E40AF"   # blue-800
C_HEADER_GREEN = "065F46"   # green-900
C_ACCENT       = "DBEAFE"   # blue-100
C_ALT_ROW      = "F8FAFC"   # slate-50
C_WHITE        = "FFFFFF"
C_BORDER       = "CBD5E1"   # slate-300
C_TOTAL_BG     = "EFF6FF"   # blue-50

# ---- Helpers -----------------------------------------------------------------

def _font(bold=False, color="000000", size=11):
    return Font(bold=bold, color=color, size=size)

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _border():
    s = Side(border_style="thin", color=C_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)

def _center(wrap=False):
    return Alignment(horizontal="center", vertical="center", wrap_text=wrap)

def _left(wrap=False):
    return Alignment(horizontal="left", vertical="center", wrap_text=wrap)

def _right():
    return Alignment(horizontal="right", vertical="center")

def _header_row(ws, row, values, bg=C_HEADER_DARK, fg=C_WHITE, height=18):
    ws.row_dimensions[row].height = height
    for col, val in enumerate(values, 1):
        c = ws.cell(row=row, column=col, value=val)
        c.font      = _font(bold=True, color=fg)
        c.fill      = _fill(bg)
        c.alignment = _center(wrap=True)
        c.border    = _border()

def _data_row(ws, row, values, alt=False, formats=None):
    bg = C_ALT_ROW if alt else C_WHITE
    for col, val in enumerate(values, 1):
        c = ws.cell(row=row, column=col, value=val)
        c.fill      = _fill(bg)
        c.alignment = _left(wrap=True)
        c.border    = _border()
        if formats and col - 1 < len(formats) and formats[col - 1]:
            c.number_format = formats[col - 1]

def _set_col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def _merge_title(ws, row, text, max_col, bg=C_HEADER_BLUE):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max_col)
    c = ws.cell(row=row, column=1, value=text)
    c.font      = _font(bold=True, color=C_WHITE, size=13)
    c.fill      = _fill(bg)
    c.alignment = _center()
    ws.row_dimensions[row].height = 24

def _section_title(ws, row, text, max_col, bg=C_ACCENT):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max_col)
    c = ws.cell(row=row, column=1, value=text)
    c.font      = _font(bold=True, color=C_HEADER_BLUE)
    c.fill      = _fill(bg)
    c.alignment = _left()
    ws.row_dimensions[row].height = 16

# ==== Sheet 1: サマリー =========================================================

def _sheet_summary(wb, design):
    ws = wb.create_sheet("サマリー")
    f  = design["factory"]
    s  = design["stats"]
    nc = design["network_config"]
    today = date.today().strftime("%Y年%m月%d日")

    _merge_title(ws, 1, "工場 Wi-Fi ネットワーク設計書", 3)

    rows = [
        ("作成日",           today),
        ("工場サイズ",        f"{f['width']}m × {f['height']}m"),
        ("床面積",           f"{f['area_m2']:,.0f} m²"),
        ("SSID",            nc["ssid"]),
        ("セキュリティ",      nc["security"]),
        ("AP 合計",         f"{s['total_aps']} 台"),
        ("  うち有線AP",     f"{s['wired_aps']} 台（壁面・PoE接続）"),
        ("  うちメッシュAP", f"{s['mesh_aps']} 台（内部・ワイヤレスバックホール）"),
        ("PoEスイッチ",      f"{s['switch_count']} 台"),
        ("光ファイバー幹線",  f"約 {s['fiber_total_m']:,} m"),
        ("推定カバレッジ",    f"{s['coverage_percentage']} %"),
        ("機器費用概算",      f"¥{design['total_cost_jpy']:,}（税抜・工事費別）"),
    ]

    for i, (k, v) in enumerate(rows, 3):
        ws.row_dimensions[i].height = 17
        ck = ws.cell(row=i, column=1, value=k)
        ck.font      = _font(bold=True)
        ck.fill      = _fill(C_ACCENT)
        ck.alignment = _left()
        ck.border    = _border()
        cv = ws.cell(row=i, column=2, value=v)
        cv.alignment = _left()
        cv.border    = _border()
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=3)

    _set_col_widths(ws, [28, 35, 10])
    ws.sheet_view.showGridLines = False


# ==== Sheet 2: 機器一覧 (BOM) ==================================================

def _sheet_bom(wb, design):
    ws  = wb.create_sheet("機器一覧（BOM）")
    bom = design["equipment_bom"]
    MAX = 7

    _merge_title(ws, 1, "機器一覧（部品表 / BOM）", MAX)
    _header_row(ws, 2,
        ["カテゴリ", "型番・モデル", "仕様", "数量", "単価（円）", "小計（円）", "備考"],
        height=20,
    )

    FMT_NUM  = '#,##0'
    FMT_YEN  = '¥#,##0'
    for i, item in enumerate(bom, 3):
        alt = i % 2 == 0
        _data_row(ws, i,
            [item["category"], item["model"], item["spec"],
             item["qty"], item["unit_price"], item["total_price"], item.get("note","")],
            alt=alt,
            formats=[None, None, None, FMT_NUM, FMT_YEN, FMT_YEN, None],
        )
        # right-align numeric cells
        for col in (4, 5, 6):
            ws.cell(row=i, column=col).alignment = _right()

    # Total row
    tr = len(bom) + 3
    ws.row_dimensions[tr].height = 20
    ws.merge_cells(start_row=tr, start_column=1, end_row=tr, end_column=5)
    lbl = ws.cell(row=tr, column=1, value="合計（税抜・機器代のみ）")
    lbl.font = _font(bold=True); lbl.fill = _fill(C_TOTAL_BG)
    lbl.alignment = _right(); lbl.border = _border()
    tot = ws.cell(row=tr, column=6, value=design["total_cost_jpy"])
    tot.font = _font(bold=True, color=C_HEADER_BLUE, size=12)
    tot.number_format = FMT_YEN; tot.fill = _fill(C_TOTAL_BG)
    tot.alignment = _right(); tot.border = _border()
    note = ws.cell(row=tr, column=7, value="工事費・保守費・SIM費は含まず")
    note.font = _font(color="94A3B8"); note.fill = _fill(C_TOTAL_BG)
    note.alignment = _left(); note.border = _border()

    _set_col_widths(ws, [28, 42, 55, 8, 14, 14, 42])
    ws.sheet_view.showGridLines = False


# ==== Sheet 3: AP配置 ==========================================================

def _sheet_aps(wb, design):
    ws  = wb.create_sheet("AP配置計画")
    aps = design["access_points"]
    sws = design["switches"]
    MAX = 6

    _merge_title(ws, 1, "アクセスポイント配置計画", MAX)

    # AP table
    _section_title(ws, 2, "■ アクセスポイント一覧", MAX)
    _header_row(ws, 3, ["AP-ID", "種別", "X座標(m)", "Y座標(m)", "カバー半径(m)", "接続方式"],
                bg=C_HEADER_GREEN)
    for i, ap in enumerate(aps, 4):
        kind  = "有線AP（壁面設置）" if ap["type"] == "wired" else "メッシュAP（内部天井）"
        conn  = "PoE+（LANケーブル ≤5m）" if ap["type"] == "wired" else "ワイヤレスバックホール"
        _data_row(ws, i, [ap["id"], kind, ap["x"], ap["y"], ap["coverage_radius"], conn],
                  alt=i % 2 == 0,
                  formats=[None, None, '0.0', '0.0', '0', None])
        for col in (3, 4, 5):
            ws.cell(row=i, column=col).alignment = _right()

    # Switch table
    sw_start = len(aps) + 6
    _section_title(ws, sw_start, "■ PoEスイッチ一覧", MAX)
    _header_row(ws, sw_start + 1,
                ["SW-ID", "設置壁", "X座標(m)", "Y座標(m)", "接続AP", ""],
                bg=C_HEADER_GREEN)
    for i, sw in enumerate(sws, sw_start + 2):
        _data_row(ws, i,
                  [sw["id"], f"{sw['wall']}壁", sw["x"], sw["y"],
                   ", ".join(sw["assigned_ap_ids"]), ""],
                  alt=i % 2 == 0,
                  formats=[None, None, '0.0', '0.0', None, None])
        for col in (3, 4):
            ws.cell(row=i, column=col).alignment = _right()

    _set_col_widths(ws, [14, 24, 12, 12, 16, 36])
    ws.sheet_view.showGridLines = False


# ==== Sheet 4: IPアドレス計画 ==================================================

def _sheet_ip(wb, design):
    ws = wb.create_sheet("IPアドレス計画")
    ip = design["ip_plan"]
    MAX = 3

    _merge_title(ws, 1, "IPアドレス計画", MAX)

    # Basic info
    _section_title(ws, 2, "■ 基本ネットワーク情報", MAX)
    _header_row(ws, 3, ["項目", "値", "備考"], bg=C_HEADER_BLUE)
    basics = [
        ("サブネット",          ip["subnet"],       ""),
        ("デフォルトGW",        ip["gateway"],      ""),
        ("LTEルーター",         ip["lte_router"],   "インターネット出口"),
        ("DHCPレンジ",          ip["dhcp_range"],   "端末向け動的割り当て"),
        ("DNS（プライマリ）",   ip["dns_primary"],  "Google Public DNS"),
        ("DNS（セカンダリ）",   ip["dns_secondary"], ""),
    ]
    for i, (k, v, note) in enumerate(basics, 4):
        _data_row(ws, i, [k, v, note], alt=i % 2 == 0)

    # Switches
    sw_start = len(basics) + 6
    _section_title(ws, sw_start, "■ スイッチ 固定IPアドレス", MAX)
    _header_row(ws, sw_start + 1, ["機器ID", "IPアドレス", "備考"], bg=C_HEADER_BLUE)
    sw_items = list(ip["switches"].items())
    for i, (sw_id, addr) in enumerate(sw_items, sw_start + 2):
        _data_row(ws, i, [sw_id, addr, "管理用固定IP"], alt=i % 2 == 0)

    # APs
    ap_start = sw_start + len(sw_items) + 4
    _section_title(ws, ap_start, "■ AP 固定IPアドレス", MAX)
    _header_row(ws, ap_start + 1, ["機器ID", "IPアドレス", "備考"], bg=C_HEADER_BLUE)
    ap_items = list(ip["aps"].items())
    for i, (ap_id, addr) in enumerate(ap_items, ap_start + 2):
        _data_row(ws, i, [ap_id, addr, "管理用固定IP"], alt=i % 2 == 0)

    _set_col_widths(ws, [28, 22, 34])
    ws.sheet_view.showGridLines = False


# ==== Sheet 5: ネットワーク設定 ================================================

def _sheet_config(wb, design):
    ws = wb.create_sheet("ネットワーク設定")
    nc = design["network_config"]
    MAX = 3

    _merge_title(ws, 1, "ネットワーク設定仕様", MAX)

    _section_title(ws, 2, "■ 無線LAN 設定", MAX)
    _header_row(ws, 3, ["設定項目", "値", "備考"], bg=C_HEADER_BLUE)
    wifi_rows = [
        ("SSID",                    nc["ssid"],                 ""),
        ("周波数帯",                 nc["frequency_bands"],      ""),
        ("セキュリティ方式",         nc["security"],             "RADIUSサーバー要検討"),
        ("2.4GHz チャンネル計画",   nc["channel_plan_24ghz"],  ""),
        ("5GHz チャンネル計画",     nc["channel_plan_5ghz"],   "DFS チャンネルは要確認"),
        ("QoS",                     nc["qos"],                  ""),
        ("高速ローミング",           nc["roaming"],              ""),
    ]
    for i, row in enumerate(wifi_rows, 4):
        _data_row(ws, i, list(row), alt=i % 2 == 0)

    _section_title(ws, 12, "■ 設計制約・注意事項", MAX)
    _header_row(ws, 13, ["項目", "内容", ""], bg=C_HEADER_BLUE)
    notes = [
        ("WAN接続",       "LTEルーター経由（工場既設ネットワーク非接続）"),
        ("LANケーブル上限", "5m（スイッチ〜壁面AP間のみ）"),
        ("スイッチ間幹線",  "光ファイバー OM3（LANケーブル不使用）"),
        ("機器設置場所",   "スイッチ・LTEルーターは壁際パネルボックス内"),
        ("内部カバレッジ", "メッシュAP ワイヤレスバックホール（PoEインジェクター給電）"),
        ("現地確認",      "本設計は試算。竣工後ウォークテスト（電波測定）必須"),
        ("電波干渉",      "金属設備の多い環境ではカバー半径が30m以下になる場合あり"),
        ("メッシュホップ", "推奨最大 2ホップ。3ホップ超はスループット低下の恐れあり"),
    ]
    for i, (k, v) in enumerate(notes, 14):
        _data_row(ws, i, [k, v, ""], alt=i % 2 == 0)

    _set_col_widths(ws, [26, 55, 20])
    ws.sheet_view.showGridLines = False


# ==== Public entry point =======================================================

def build_excel(design: dict) -> io.BytesIO:
    """Return an in-memory Excel workbook as a BytesIO buffer."""
    wb = Workbook()
    wb.remove(wb.active)          # remove default empty sheet

    _sheet_summary(wb, design)
    _sheet_bom(wb, design)
    _sheet_aps(wb, design)
    _sheet_ip(wb, design)
    _sheet_config(wb, design)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
