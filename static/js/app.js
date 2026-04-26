"use strict";

// ===== Utility =====
const $ = id => document.getElementById(id);
const fmt = n => Number(n).toLocaleString("ja-JP");

// ===== Area display =====
function updateArea() {
  const w = parseFloat($("width").value) || 0;
  const h = parseFloat($("height").value) || 0;
  $("area-display").textContent = fmt(w * h) + " m²";
}
$("width").addEventListener("input", updateArea);
$("height").addEventListener("input", updateArea);

// ===== Current form payload (shared between submit and download) =====
function getPayload() {
  return {
    width:           parseFloat($("width").value),
    height:          parseFloat($("height").value),
    ssid:            $("ssid").value.trim() || "FACTORY-WIFI",
    ap_spacing:      parseFloat($("ap_spacing").value),
    coverage_radius: parseFloat($("coverage_radius").value),
  };
}

// ===== Excel download =====
$("excel-btn").addEventListener("click", async () => {
  const btn = $("excel-btn");
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> 生成中…';
  try {
    const res = await fetch("/api/export/excel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getPayload()),
    });
    if (!res.ok) throw new Error("サーバーエラー");
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    a.href     = url;
    a.download = `network_design_${today}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("ダウンロードエラー: " + err.message);
  } finally {
    btn.innerHTML = orig;
    btn.disabled  = false;
  }
});

// ===== Form submit =====
$("design-form").addEventListener("submit", async e => {
  e.preventDefault();
  $("loading").classList.remove("hidden");
  $("results").classList.add("hidden");
  $("excel-btn").disabled = true;
  $("submit-btn").disabled = true;

  try {
    const res = await fetch("/api/design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getPayload()),
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.error || "設計計算に失敗しました");
    renderResults(json.design);
    $("excel-btn").disabled = false;  // enable download after successful design
  } catch (err) {
    alert("エラー: " + err.message);
  } finally {
    $("loading").classList.add("hidden");
    $("submit-btn").disabled = false;
  }
});

// ===== Render all results =====
function renderResults(d) {
  renderSummary(d);
  renderFloorPlan(d);
  renderBOM(d);
  renderIPPlan(d);
  renderConfig(d);
  renderDocument(d);

  $("results").classList.remove("hidden");
  $("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ===== Summary Bar =====
function renderSummary(d) {
  const s = d.stats;
  const stats = [
    { value: s.total_aps,            unit: "台",  label: "AP 合計" },
    { value: s.wired_aps,            unit: "台",  label: "有線AP（壁面）" },
    { value: s.mesh_aps,             unit: "台",  label: "メッシュAP（内部）" },
    { value: s.switch_count,         unit: "台",  label: "PoEスイッチ" },
    { value: s.fiber_total_m,        unit: "m",   label: "光ファイバー幹線" },
    { value: s.coverage_percentage,  unit: "%",   label: "推定カバレッジ" },
    { value: fmt(d.total_cost_jpy),  unit: "円",  label: "概算費用（機器のみ）" },
  ];
  $("summary-bar").innerHTML = stats.map(s =>
    `<div class="stat-card">
       <div class="stat-value">${s.value}<span class="stat-unit">${s.unit}</span></div>
       <div class="stat-label">${s.label}</div>
     </div>`
  ).join("");
}

// ===== Floor Plan =====
function renderFloorPlan(d) {
  $("floor-plan").innerHTML = d.floor_plan_svg;
}

// ===== BOM Table =====
function renderBOM(d) {
  const rows = d.equipment_bom.map(item => `
    <tr>
      <td>${item.category}</td>
      <td><strong>${item.model}</strong></td>
      <td style="max-width:240px;word-break:break-word;">${item.spec}</td>
      <td class="num">${item.qty}</td>
      <td class="num">¥${fmt(item.unit_price)}</td>
      <td class="num">¥${fmt(item.total_price)}</td>
      <td style="color:#64748b;font-size:12px;">${item.note || ""}</td>
    </tr>`).join("");

  $("bom-tbody").innerHTML = rows;
  $("bom-tfoot").innerHTML = `
    <tr>
      <td colspan="5">合計（税抜・機器代のみ）</td>
      <td class="num">¥${fmt(d.total_cost_jpy)}</td>
      <td></td>
    </tr>`;
}

// ===== IP Plan =====
function renderIPPlan(d) {
  const ip = d.ip_plan;

  const baseCard = `
    <div class="ip-card">
      <h3>&#127760; 基本ネットワーク情報</h3>
      ${ipRow("サブネット",      ip.subnet)}
      ${ipRow("デフォルトGW",    ip.gateway)}
      ${ipRow("LTEルーター",     ip.lte_router)}
      ${ipRow("DHCPレンジ",      ip.dhcp_range)}
      ${ipRow("DNS（プライマリ）", ip.dns_primary)}
      ${ipRow("DNS（セカンダリ）", ip.dns_secondary)}
    </div>`;

  const swEntries = Object.entries(ip.switches);
  const swCard = `
    <div class="ip-card">
      <h3>&#128307; PoEスイッチ IPアドレス</h3>
      ${swEntries.map(([id, addr]) => ipRow(id, addr)).join("")}
    </div>`;

  const apEntries = Object.entries(ip.aps);
  const half = Math.ceil(apEntries.length / 2);
  const apCard1 = `
    <div class="ip-card">
      <h3>&#128225; アクセスポイント IPアドレス（1）</h3>
      ${apEntries.slice(0, half).map(([id, addr]) => ipRow(id, addr)).join("")}
    </div>`;
  const apCard2 = `
    <div class="ip-card">
      <h3>&#128225; アクセスポイント IPアドレス（2）</h3>
      ${apEntries.slice(half).map(([id, addr]) => ipRow(id, addr)).join("")}
    </div>`;

  $("ip-grid").innerHTML = baseCard + swCard + apCard1 + (apEntries.length > 1 ? apCard2 : "");
}

function ipRow(key, val) {
  return `<div class="ip-row"><span class="ip-key">${key}</span><span class="ip-val">${val}</span></div>`;
}

// ===== Network Config =====
function renderConfig(d) {
  const nc = d.network_config;
  const wifiCard = `
    <div class="config-card">
      <h3>&#128225; 無線 LAN 設定</h3>
      ${cfgRow("SSID",          nc.ssid)}
      ${cfgRow("周波数帯",       nc.frequency_bands)}
      ${cfgRow("セキュリティ",   nc.security)}
      ${cfgRow("2.4GHz CH計画", nc.channel_plan_24ghz)}
      ${cfgRow("5GHz CH計画",   nc.channel_plan_5ghz)}
      ${cfgRow("QoS",           nc.qos)}
      ${cfgRow("高速ローミング", nc.roaming)}
    </div>`;

  const topoCard = `
    <div class="config-card">
      <h3>&#127760; トポロジー概要</h3>
      ${cfgRow("WAN接続",   "LTEルーター経由（インターネット直結）")}
      ${cfgRow("幹線",      "光ファイバー（マルチモード OM4）")}
      ${cfgRow("AP給電",    "PoE+ (802.3at) / 最大 30W")}
      ${cfgRow("LANケーブル", "Cat6 最大 5m（スイッチ〜壁面AP間）")}
      ${cfgRow("内部中継",  "メッシュAPによるワイヤレスバックホール")}
      ${cfgRow("冗長性",    "LTEリンクは回線障害時に自動フェイルオーバー")}
    </div>`;

  const noteCard = `
    <div class="config-card">
      <h3>&#9888; 設計上の注意事項</h3>
      ${cfgRow("電波干渉", "金属設備・機械の多い環境では実測30m以下になる場合あり")}
      ${cfgRow("メッシュホップ数", "最大2ホップを推奨。3ホップ以上はスループット低下")}
      ${cfgRow("LTE帯域", "稼働端末数・動画利用が多い場合は5G対応ルーターを検討")}
      ${cfgRow("現地調査", "設計後、電波測定（ウォークテスト）による確認を推奨")}
    </div>`;

  $("config-content").innerHTML = wifiCard + topoCard + noteCard;
}

function cfgRow(key, val) {
  return `<div class="config-row"><span class="config-key">${key}</span><span class="config-val">${val}</span></div>`;
}

// ===== Design Document =====
function renderDocument(d) {
  const now = new Date().toLocaleDateString("ja-JP", { year:"numeric", month:"long", day:"numeric" });
  const s = d.stats;
  const ip = d.ip_plan;
  const nc = d.network_config;

  const bomRows = d.equipment_bom.map(item => `
    <tr>
      <td>${item.category}</td>
      <td>${item.model}</td>
      <td class="num">${item.qty}</td>
      <td class="num">¥${fmt(item.unit_price)}</td>
      <td class="num">¥${fmt(item.total_price)}</td>
    </tr>`).join("");

  const apRows = d.access_points.map(ap => `
    <tr>
      <td>${ap.id}</td>
      <td>${ap.type === "wired" ? "有線AP（壁面）" : "メッシュAP（内部）"}</td>
      <td>${ap.x}m</td>
      <td>${ap.y}m</td>
    </tr>`).join("");

  const swRows = d.switches.map((sw, i) => `
    <tr>
      <td>${sw.id}</td>
      <td>${sw.wall}壁</td>
      <td>${sw.x}m, ${sw.y}m</td>
      <td>${ip.switches[sw.id] || "-"}</td>
      <td>${sw.assigned_ap_ids.join(", ")}</td>
    </tr>`).join("");

  $("doc-content").innerHTML = `
    <h1>工場 Wi-Fi ネットワーク設計書</h1>

    <div class="doc-meta">
      <div class="doc-meta-row"><span class="doc-meta-key">作成日</span><span class="doc-meta-val">${now}</span></div>
      <div class="doc-meta-row"><span class="doc-meta-key">工場サイズ</span><span class="doc-meta-val">${d.factory.width}m × ${d.factory.height}m（${fmt(d.factory.area_m2)} m²）</span></div>
      <div class="doc-meta-row"><span class="doc-meta-key">SSID</span><span class="doc-meta-val">${nc.ssid}</span></div>
      <div class="doc-meta-row"><span class="doc-meta-key">推定カバレッジ</span><span class="doc-meta-val">${s.coverage_percentage}%</span></div>
      <div class="doc-meta-row"><span class="doc-meta-key">概算費用（機器）</span><span class="doc-meta-val">¥${fmt(d.total_cost_jpy)}（税抜）</span></div>
    </div>

    <h2>1. 設計コンセプト・制約条件</h2>
    <table>
      <tr><th>項目</th><th>内容</th></tr>
      <tr><td>WAN接続方式</td><td>LTEルーター経由（工場既設ネットワークとは非接続）</td></tr>
      <tr><td>有線配線</td><td>LANケーブルは最大5m（スイッチ〜AP間のみ）</td></tr>
      <tr><td>スイッチ間幹線</td><td>光ファイバー（マルチモード OM4）を使用</td></tr>
      <tr><td>機器設置場所</td><td>スイッチ・LTEルーターは壁際（パネルボックス内）</td></tr>
      <tr><td>内部カバレッジ</td><td>メッシュAPによるワイヤレスバックホールで補完</td></tr>
      <tr><td>セキュリティ</td><td>WPA3-Enterprise (802.1X 認証)</td></tr>
    </table>

    <h2>2. 機器構成サマリー</h2>
    <table>
      <tr><th>項目</th><th>数量</th></tr>
      <tr><td>AP 合計</td><td>${s.total_aps} 台</td></tr>
      <tr><td>　うち有線AP（壁面）</td><td>${s.wired_aps} 台</td></tr>
      <tr><td>　うちメッシュAP（内部）</td><td>${s.mesh_aps} 台</td></tr>
      <tr><td>PoEスイッチ</td><td>${s.switch_count} 台</td></tr>
      <tr><td>LTEルーター</td><td>1 台</td></tr>
      <tr><td>光ファイバー幹線</td><td>約 ${s.fiber_total_m} m</td></tr>
    </table>

    <h2>3. 機器一覧（BOM）</h2>
    <table>
      <thead><tr><th>カテゴリ</th><th>型番・モデル</th><th class="num">数量</th><th class="num">単価</th><th class="num">小計</th></tr></thead>
      <tbody>${bomRows}</tbody>
      <tfoot><tr><td colspan="4">合計（税抜）</td><td class="num">¥${fmt(d.total_cost_jpy)}</td></tr></tfoot>
    </table>

    <h2>4. APアドレス・配置計画</h2>
    <table>
      <thead><tr><th>ID</th><th>種別</th><th>X座標</th><th>Y座標</th></tr></thead>
      <tbody>${apRows}</tbody>
    </table>

    <h2>5. スイッチ配置・接続計画</h2>
    <table>
      <thead><tr><th>ID</th><th>設置壁</th><th>座標</th><th>管理IP</th><th>接続AP</th></tr></thead>
      <tbody>${swRows}</tbody>
    </table>

    <h2>6. IPアドレス計画</h2>
    <table>
      <tr><th>項目</th><th>アドレス</th></tr>
      <tr><td>サブネット</td><td>${ip.subnet}</td></tr>
      <tr><td>デフォルトゲートウェイ</td><td>${ip.gateway}</td></tr>
      <tr><td>LTEルーター</td><td>${ip.lte_router}</td></tr>
      <tr><td>DHCPレンジ</td><td>${ip.dhcp_range}</td></tr>
      <tr><td>DNS（プライマリ）</td><td>${ip.dns_primary}</td></tr>
      <tr><td>DNS（セカンダリ）</td><td>${ip.dns_secondary}</td></tr>
    </table>

    <h2>7. 無線 LAN 設定仕様</h2>
    <table>
      <tr><th>設定項目</th><th>値</th></tr>
      <tr><td>SSID</td><td>${nc.ssid}</td></tr>
      <tr><td>周波数帯</td><td>${nc.frequency_bands}</td></tr>
      <tr><td>セキュリティ</td><td>${nc.security}</td></tr>
      <tr><td>2.4GHz チャンネル計画</td><td>${nc.channel_plan_24ghz}</td></tr>
      <tr><td>5GHz チャンネル計画</td><td>${nc.channel_plan_5ghz}</td></tr>
      <tr><td>QoS</td><td>${nc.qos}</td></tr>
      <tr><td>高速ローミング</td><td>${nc.roaming}</td></tr>
    </table>

    <h2>8. 注意事項・推奨事項</h2>
    <ul style="padding-left:20px;line-height:2;">
      <li>本設計書の数値は試算です。実際の環境（金属構造物・機械設備）により電波特性が変わります。</li>
      <li>竣工後は必ずウォークテスト（電波測定）を実施し、カバレッジを確認してください。</li>
      <li>メッシュホップ数が3以上になる箇所はスループット低下が生じる場合があります。追加の有線APを検討してください。</li>
      <li>LTE回線の帯域は契約プランによります。接続端末数・動画利用が多い場合は5G回線または複数SIMの検討を推奨します。</li>
      <li>工場内に既存の2.4GHz機器（電動工具・センサー等）がある場合はチャンネル干渉に注意してください。</li>
    </ul>
  `;
}

// ===== Tab switching =====
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.add("hidden"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.remove("hidden");
  });
});
