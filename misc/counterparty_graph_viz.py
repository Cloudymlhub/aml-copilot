"""
Counterparty Graph Visualization — HTML Generator

Consumes the output of build_counterparty_graph() and produces a self-contained
interactive HTML file showing the ego graph centered on the customer.

Usage:
    from counterparty_graph_compute import build_counterparty_graph, CaseContext, GraphParameters
    from counterparty_graph_viz import render_graph_html, VizConfig

    graph = build_counterparty_graph(spark, transactions, risk_scores, labels, kyc, context, params)

    customer_info = CustomerInfo(
        name="CUSTOMER",
        segment="retail",
        risk_score=0.45,
        risk_rating="low",
        nationality="Chinese",
        employer="Nova Power Real Estate",
        declared_income=9000,
        account_opened="2024-01-18",
    )

    html = render_graph_html(graph, customer_info, context, params)

    with open("case_graph.html", "w") as f:
        f.write(html)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Dict, Optional

from counterparty_graph_compute import (
    CaseContext,
    CounterpartyEntry,
    GraphParameters,
)
from pydantic import BaseModel, Field


# =============================================================================
# INPUT MODELS
# =============================================================================


class CustomerInfo(BaseModel):
    """Customer-level info for the center node display."""

    name: str = "CUSTOMER"
    segment: str = ""
    risk_score: float = 0.0
    risk_rating: str = "low"
    nationality: Optional[str] = None
    employer: Optional[str] = None
    declared_income: Optional[float] = None
    account_opened: Optional[str] = None
    total_credits: Optional[float] = None
    total_debits: Optional[float] = None
    credit_to_debit_ratio: Optional[float] = None
    credits_to_income_ratio: Optional[float] = None


class VizConfig(BaseModel):
    """Visual configuration for the graph rendering."""

    width: int = Field(default=960, description="SVG viewBox width")
    height: int = Field(default=600, description="SVG viewBox height")
    node_radius_individual: int = Field(default=26, description="Radius for individual nodes")
    node_radius_company: int = Field(default=34, description="Radius for company nodes")
    node_radius_customer: int = Field(default=30, description="Radius for center customer node")
    edge_min_width: float = Field(default=2.0, description="Minimum edge stroke width")
    edge_max_width: float = Field(default=10.0, description="Maximum edge stroke width")
    inbound_spread_radius: int = Field(default=220, description="Distance of inbound CPs from center")
    outbound_spread_radius: int = Field(default=240, description="Distance of outbound CPs from center")
    inbound_offset_x: int = Field(default=-120, description="X offset for inbound CPs")
    outbound_offset_x: int = Field(default=120, description="X offset for outbound CPs")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def render_graph_html(
    graph: Dict[str, CounterpartyEntry],
    customer: CustomerInfo,
    context: CaseContext,
    params: GraphParameters = GraphParameters(),
    viz: VizConfig = VizConfig(),
) -> str:
    """
    Render the counterparty graph as a self-contained HTML string.

    Args:
        graph: Output of build_counterparty_graph()
        customer: Customer-level info for center node
        context: Case context (dates)
        params: Graph parameters (for display in parameters panel)
        viz: Visual configuration

    Returns:
        Complete HTML string, ready to write to file.
    """

    # Serialize data for embedding in JS
    graph_json = json.dumps(
        {name: entry.model_dump() for name, entry in graph.items()},
        default=str,
        indent=2,
    )
    customer_json = json.dumps(customer.model_dump(), default=str)
    context_json = json.dumps(context.model_dump(), default=str)
    params_json = json.dumps(params.model_dump(), default=str)
    viz_json = json.dumps(viz.model_dump(), default=str)

    return _HTML_TEMPLATE.replace("__GRAPH_DATA__", graph_json) \
        .replace("__CUSTOMER_DATA__", customer_json) \
        .replace("__CONTEXT_DATA__", context_json) \
        .replace("__PARAMS_DATA__", params_json) \
        .replace("__VIZ_CONFIG__", viz_json)


# =============================================================================
# HTML TEMPLATE
# =============================================================================

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Counterparty Graph — AML Review</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    background: #0a0f1a; color: #e2e8f0;
    height: 100vh; overflow: hidden; display: flex;
  }
  .main-area { flex: 1; position: relative; overflow: hidden; }
  .header {
    position: absolute; top: 0; left: 0; right: 0;
    padding: 16px 24px; display: flex; justify-content: space-between; align-items: center;
    z-index: 10; background: linear-gradient(to bottom, rgba(10,15,26,0.95), transparent);
  }
  .header-title { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; color: #f1f5f9; }
  .header-sub { font-size: 12px; color: #64748b; margin-top: 2px; }
  .btn-params {
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
    color: #94a3b8; padding: 8px 16px; border-radius: 6px; cursor: pointer;
    font-size: 13px; font-weight: 500; font-family: inherit; transition: all 0.2s;
  }
  .btn-params.active { background: #1e40af; color: #fff; }
  .legend {
    position: absolute; bottom: 16px; left: 24px;
    display: flex; gap: 16px; align-items: center; z-index: 10;
    background: rgba(10,15,26,0.85); padding: 10px 16px; border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.06); font-size: 11px; color: #94a3b8;
  }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .legend-item { display: flex; align-items: center; gap: 5px; }
  .legend-sep { width: 1px; height: 16px; background: rgba(255,255,255,0.1); }
  svg { width: 100%; height: 100%; }
  svg text { font-family: 'IBM Plex Sans', sans-serif; pointer-events: none; }
  .edge-path { transition: all 0.2s; cursor: pointer; }
  .node-group { cursor: pointer; }

  .edge-tooltip {
    position: absolute; top: 60px; width: 290px;
    background: rgba(15,23,42,0.96); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px; padding: 16px; z-index: 20;
    backdrop-filter: blur(12px); display: none; font-size: 12px;
  }
  .edge-tooltip.visible { display: block; }
  .tt-label { font-size: 11px; color: #64748b; margin-bottom: 4px; }
  .tt-name { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
  .tt-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }
  .tt-key { color: #64748b; } .tt-val { color: #f1f5f9; font-weight: 500; }
  .tt-val.warn { color: #f97316; font-weight: 600; }

  .params-panel {
    position: absolute; top: 56px; right: 0; width: 350px; height: calc(100% - 56px);
    background: rgba(15,23,42,0.97); border-left: 1px solid rgba(255,255,255,0.08);
    padding: 20px; overflow-y: auto; z-index: 15; display: none;
  }
  .params-panel.visible { display: block; }
  .params-panel h3 { font-size: 15px; font-weight: 700; margin-bottom: 4px; color: #f1f5f9; }
  .params-sub { font-size: 11px; color: #64748b; margin-bottom: 20px; }
  .param-group { margin-bottom: 20px; }
  .param-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
  .param-label { font-size: 12px; font-weight: 600; color: #e2e8f0; }
  .param-value { font-size: 12px; font-weight: 700; color: #3b82f6; }
  .param-range { width: 100%; accent-color: #3b82f6; height: 4px; }
  .param-bounds { display: flex; justify-content: space-between; font-size: 10px; color: #475569; margin-top: 2px; }
  .param-desc { font-size: 10px; color: #64748b; margin-top: 4px; line-height: 1.4; }

  .detail-panel {
    width: 340px; border-left: 1px solid rgba(255,255,255,0.06);
    background: rgba(15,23,42,0.6); overflow-y: auto; padding: 20px;
  }
  .detail-empty {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; height: 100%; opacity: 0.5; text-align: center;
  }
  .detail-empty .icon { font-size: 32px; margin-bottom: 12px; }
  .detail-empty p { font-size: 13px; color: #64748b; }
  .section-title { font-size: 11px; font-weight: 700; color: #94a3b8; letter-spacing: 0.06em; margin-bottom: 8px; margin-top: 16px; }
  .detail-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 11px; }
  .detail-row .k { color: #64748b; } .detail-row .v { color: #e2e8f0; }
  .tag { padding: 3px 8px; border-radius: 4px; font-size: 10px; }
  .risk-bar-track { height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; }
  .risk-bar-fill { height: 100%; background: linear-gradient(to right, #22c55e, #eab308, #ef4444); border-radius: 3px; transition: width 0.3s; }
  .compliance-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
  .compliance-cell { text-align: center; padding: 8px; border-radius: 6px; }
  .compliance-cell .num { font-size: 18px; font-weight: 700; }
  .compliance-cell .lbl { font-size: 10px; color: #64748b; }
  .alert-box { margin-top: 16px; padding: 12px; border-radius: 8px; }
  .alert-box h4 { font-size: 11px; font-weight: 600; margin-bottom: 6px; }
  .alert-box p { font-size: 11px; color: #94a3b8; line-height: 1.6; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
</style>
</head>
<body>

<div class="main-area">
  <div class="header">
    <div>
      <div class="header-title">Counterparty Graph</div>
      <div class="header-sub" id="headerSub"></div>
    </div>
    <button class="btn-params" id="btnParams" onclick="toggleParams()">⚙ Parameters ▸</button>
  </div>

  <div class="legend">
    <span style="font-size:11px;color:#64748b;margin-right:4px">Risk Score:</span>
    <div class="legend-item"><span class="legend-dot" style="background:#22c55e"></span> Low</div>
    <div class="legend-item"><span class="legend-dot" style="background:#eab308"></span> Med</div>
    <div class="legend-item"><span class="legend-dot" style="background:#ef4444"></span> High</div>
    <div class="legend-sep"></div>
    <div class="legend-item">
      <svg width="20" height="10"><line x1="0" y1="5" x2="16" y2="5" stroke="#3b82f6" stroke-width="2"/><polygon points="14,2 20,5 14,8" fill="#3b82f6"/></svg> Inbound
    </div>
    <div class="legend-item">
      <svg width="20" height="10"><line x1="0" y1="5" x2="16" y2="5" stroke="#f97316" stroke-width="2"/><polygon points="14,2 20,5 14,8" fill="#f97316"/></svg> Outbound
    </div>
    <div class="legend-item">
      <span class="legend-dot" style="border:2px dashed #94a3b8;background:transparent"></span> External
    </div>
  </div>

  <svg id="graphSvg" viewBox="0 0 960 600">
    <defs>
      <marker id="arrowIn" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8Z" fill="#3b82f6" opacity="0.7"/></marker>
      <marker id="arrowOut" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8Z" fill="#f97316" opacity="0.7"/></marker>
      <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <radialGradient id="bgGrad" cx="50%" cy="50%"><stop offset="0%" stop-color="#111827"/><stop offset="100%" stop-color="#0a0f1a"/></radialGradient>
    </defs>
    <rect width="960" height="600" fill="url(#bgGrad)"/>
  </svg>

  <div class="edge-tooltip" id="edgeTooltip"></div>
  <div class="params-panel" id="paramsPanel"></div>
</div>

<div class="detail-panel" id="detailPanel">
  <div class="detail-empty">
    <div class="icon">🔍</div>
    <p>Click a node to view details<br><br>Hover an edge to view relationship</p>
  </div>
</div>

<script>
// ---- Embedded data from Python ----
const GRAPH = __GRAPH_DATA__;
const CUSTOMER = __CUSTOMER_DATA__;
const CONTEXT = __CONTEXT_DATA__;
const PARAMS = __PARAMS_DATA__;
const VIZ = __VIZ_CONFIG__;

// ---- Derived ----
const cpNames = Object.keys(GRAPH);
let selected = null;

// ---- Utilities ----
function riskColor(s) {
  if (s == null) return "#94a3b8";
  if (s < 0.3) return "#22c55e"; if (s < 0.5) return "#84cc16";
  if (s < 0.7) return "#eab308"; if (s < 0.85) return "#f97316";
  return "#ef4444";
}
function riskLabel(s) {
  if (s == null) return "Unknown";
  if (s < 0.3) return "Low"; if (s < 0.5) return "Med-Low";
  if (s < 0.7) return "Medium"; if (s < 0.85) return "Med-High";
  return "High";
}
function fmt(n) { return n == null ? "—" : n.toLocaleString("en-US", {maximumFractionDigits:0}); }
function getScore(cp) {
  const p = cp.counterparty_profile;
  if (p.is_internal_customer && p.internal) return p.internal.internal_max_score;
  if (!p.is_internal_customer && p.external) return p.external.weighted_avg_score;
  return null;
}
function isInbound(cp) { return cp.event_period.inbound_amount > 0; }
function isCompany(cp) { return cp.counterparty_profile.counterparty_type === "company"; }

// ---- Layout: position counterparties around center ----
const CX = VIZ.width / 2, CY = VIZ.height / 2;
const positions = { __customer__: { x: CX, y: CY } };

const inboundCPs = cpNames.filter(n => isInbound(GRAPH[n]));
const outboundCPs = cpNames.filter(n => !isInbound(GRAPH[n]));

function spreadPositions(names, side) {
  const count = names.length;
  if (count === 0) return;
  const angleSpread = Math.min(1.2, count * 0.3);
  const startAngle = -angleSpread / 2;
  const step = count > 1 ? angleSpread / (count - 1) : 0;
  const r = side === "left" ? VIZ.inbound_spread_radius : VIZ.outbound_spread_radius;
  const offsetX = side === "left" ? VIZ.inbound_offset_x : VIZ.outbound_offset_x;

  names.forEach((name, i) => {
    const angle = (startAngle + step * i) * Math.PI - Math.PI / 2;
    positions[name] = {
      x: CX + Math.cos(angle) * r + offsetX,
      y: CY + Math.sin(angle) * r,
    };
  });
}

spreadPositions(inboundCPs, "left");
spreadPositions(outboundCPs, "right");

// ---- Edge width scaling ----
const maxAmt = Math.max(...cpNames.map(n => {
  const cp = GRAPH[n];
  return cp.event_period.inbound_amount + cp.event_period.outbound_amount;
}), 1);

function edgeWidth(cp) {
  const v = cp.event_period.inbound_amount + cp.event_period.outbound_amount;
  return VIZ.edge_min_width + (v / maxAmt) * (VIZ.edge_max_width - VIZ.edge_min_width);
}

// ---- SVG helpers ----
function svgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

// ---- Header ----
document.getElementById("headerSub").textContent =
  `Case Review — Event Period: ${CONTEXT.event_start} to ${CONTEXT.event_end}`;

// ---- Render graph ----
function renderGraph() {
  const svg = document.getElementById("graphSvg");
  svg.querySelectorAll(".dyn").forEach(e => e.remove());

  // Grid dots
  for (let i = 0; i < 20; i++) for (let j = 0; j < 13; j++)
    svg.appendChild(svgEl("circle", { cx: i*50+5, cy: j*50+5, r: 0.5, fill: "#1e293b", class: "dyn" }));

  // Edges
  cpNames.forEach(name => {
    const cp = GRAPH[name];
    const cpP = positions[name], cuP = positions["__customer__"];
    const inb = isInbound(cp);
    const from = inb ? cpP : cuP, to = inb ? cuP : cpP;
    const w = edgeWidth(cp);
    const color = inb ? "#3b82f6" : "#f97316";

    const dx = to.x - from.x, dy = to.y - from.y;
    const len = Math.sqrt(dx*dx + dy*dy) || 1;
    const nx = dx/len, ny = dy/len;
    const sx = from.x + nx*32, sy = from.y + ny*32;
    const ex = to.x - nx*32, ey = to.y - ny*32;
    const mx = (sx+ex)/2, my = (sy+ey)/2;
    const px = -ny*30, py = nx*30;
    const d = `M${sx},${sy} Q${mx+px},${my+py} ${ex},${ey}`;

    const path = svgEl("path", { d, fill: "none", stroke: color, "stroke-width": w, opacity: "0.4", "marker-end": inb ? "url(#arrowIn)" : "url(#arrowOut)", class: "dyn edge-path", "data-cp": name });
    svg.appendChild(path);

    const hit = svgEl("path", { d, fill: "none", stroke: "transparent", "stroke-width": "20", class: "dyn", "data-cp": name });
    hit.addEventListener("mouseenter", () => showEdgeTooltip(name));
    hit.addEventListener("mouseleave", hideEdgeTooltip);
    svg.appendChild(hit);

    const amt = inb ? cp.event_period.inbound_amount : cp.event_period.outbound_amount;
    const lbl = svgEl("text", { x: mx+px*0.6, y: my+py*0.6, "text-anchor": "middle", fill: "#64748b", "font-size": "10", class: "dyn", "data-edge-label": name });
    lbl.textContent = `AED ${fmt(amt)}`;
    svg.appendChild(lbl);
  });

  // Customer node
  const cg = svgEl("g", { class: "dyn node-group" });
  cg.addEventListener("click", () => selectNode("__customer__"));
  cg.appendChild(svgEl("circle", { cx: CX, cy: CY, r: VIZ.node_radius_customer + 6, fill: riskColor(CUSTOMER.risk_score), opacity: "0.15" }));
  const ci = svgEl("circle", { cx: CX, cy: CY, r: VIZ.node_radius_customer, fill: "#0f172a", stroke: riskColor(CUSTOMER.risk_score), "stroke-width": 3 });
  if (selected === "__customer__") ci.setAttribute("filter", "url(#glow)");
  cg.appendChild(ci);
  const ct = svgEl("text", { x: CX, y: CY-4, "text-anchor": "middle", fill: "#f1f5f9", "font-size": "10", "font-weight": "700" });
  ct.textContent = CUSTOMER.name;
  cg.appendChild(ct);
  const cs = svgEl("text", { x: CX, y: CY+10, "text-anchor": "middle", fill: "#94a3b8", "font-size": "8" });
  cs.textContent = CUSTOMER.risk_score.toFixed(2);
  cg.appendChild(cs);
  svg.appendChild(cg);

  // Counterparty nodes
  cpNames.forEach(name => {
    const cp = GRAPH[name];
    const pos = positions[name];
    const score = getScore(cp);
    const color = riskColor(score);
    const co = isCompany(cp);
    const r = co ? VIZ.node_radius_company : VIZ.node_radius_individual;
    const prof = cp.counterparty_profile;

    const g = svgEl("g", { class: "dyn node-group" });
    g.addEventListener("click", () => selectNode(name));
    g.appendChild(svgEl("circle", { cx: pos.x, cy: pos.y, r: r+6, fill: color, opacity: "0.1" }));

    const main = svgEl("circle", { cx: pos.x, cy: pos.y, r, fill: "#0f172a", stroke: color, "stroke-width": "2.5", "stroke-dasharray": prof.is_internal_customer ? "none" : "4 3" });
    if (selected === name) main.setAttribute("filter", "url(#glow)");
    g.appendChild(main);

    // Badges
    if (prof.network.is_hub) {
      g.appendChild(svgEl("circle", { cx: pos.x+r-4, cy: pos.y-r+4, r: 7, fill: "#7c3aed", stroke: "#0f172a", "stroke-width": "1.5" }));
      const ht = svgEl("text", { x: pos.x+r-4, y: pos.y-r+7.5, "text-anchor": "middle", fill: "#fff", "font-size": "8", "font-weight": "700" }); ht.textContent = "H"; g.appendChild(ht);
    }
    if (cp.relationship.is_new_in_event_period) {
      g.appendChild(svgEl("circle", { cx: pos.x-r+4, cy: pos.y-r+4, r: 7, fill: "#ef4444", stroke: "#0f172a", "stroke-width": "1.5" }));
      const nt = svgEl("text", { x: pos.x-r+4, y: pos.y-r+7.5, "text-anchor": "middle", fill: "#fff", "font-size": "7", "font-weight": "700" }); nt.textContent = "N"; g.appendChild(nt);
    }
    if ((prof.compliance_own.own_sar_count || 0) > 0) {
      g.appendChild(svgEl("circle", { cx: pos.x+r-4, cy: pos.y+r-4, r: 7, fill: "#dc2626", stroke: "#0f172a", "stroke-width": "1.5" }));
      const st = svgEl("text", { x: pos.x+r-4, y: pos.y+r-0.5, "text-anchor": "middle", fill: "#fff", "font-size": "7", "font-weight": "700" }); st.textContent = "S"; g.appendChild(st);
    }

    const nameT = svgEl("text", { x: pos.x, y: pos.y-2, "text-anchor": "middle", fill: "#f1f5f9", "font-size": co ? "7.5" : "9", "font-weight": "600" });
    nameT.textContent = name.length > 18 ? name.slice(0, 16) + "…" : name;
    g.appendChild(nameT);
    const scoreT = svgEl("text", { x: pos.x, y: pos.y+10, "text-anchor": "middle", fill: "#94a3b8", "font-size": "8" });
    scoreT.textContent = score != null ? score.toFixed(2) : "??";
    g.appendChild(scoreT);
    svg.appendChild(g);
  });
}

// ---- Edge tooltip ----
function showEdgeTooltip(name) {
  const cp = GRAPH[name];
  const inb = isInbound(cp);
  const evtAmt = inb ? cp.event_period.inbound_amount : cp.event_period.outbound_amount;
  const evtCnt = inb ? cp.event_period.inbound_count : cp.event_period.outbound_count;
  const baseAmt = inb ? cp.baseline_period.inbound_amount : cp.baseline_period.outbound_amount;
  const evb = cp.event_vs_baseline;
  const volChange = evb.is_entirely_new ? "NEW" : (evb.inbound_amount_change || evb.outbound_amount_change || "—");
  const isWarn = evb.is_volume_spike || evb.is_entirely_new;

  // Highlight
  document.querySelectorAll(`.edge-path[data-cp="${name}"]`).forEach(el => { el.setAttribute("opacity", "0.9"); el.setAttribute("stroke-width", parseFloat(el.getAttribute("stroke-width")) + 2); });
  document.querySelectorAll(`[data-edge-label="${name}"]`).forEach(el => { el.setAttribute("fill", "#f1f5f9"); el.setAttribute("font-size", "12"); el.setAttribute("font-weight", "600"); });

  const tt = document.getElementById("edgeTooltip");
  tt.style.right = document.getElementById("paramsPanel").classList.contains("visible") ? "370px" : "16px";
  tt.innerHTML = `
    <div class="tt-label">EDGE — ${inb ? "INBOUND" : "OUTBOUND"}</div>
    <div class="tt-name">${name} → Customer</div>
    <div class="tt-grid">
      <div class="tt-key">Event Amount</div><div class="tt-val">AED ${fmt(evtAmt)}</div>
      <div class="tt-key">Event Txn Count</div><div class="tt-val">${evtCnt}</div>
      <div class="tt-key">Baseline Amount</div><div class="tt-val">AED ${fmt(baseAmt)}</div>
      <div class="tt-key">Volume Change</div><div class="tt-val ${isWarn ? 'warn' : ''}">${typeof volChange === 'number' ? volChange + 'x' : volChange}${isWarn ? ' ⚠' : ''}</div>
      <div class="tt-key">Round Amounts</div><div class="tt-val">${cp.event_period.round_amount_count}</div>
      <div class="tt-key">References</div><div class="tt-val">${(cp.event_period.common_references || []).join(", ") || "—"}</div>
      <div class="tt-key">Lifetime Total</div><div class="tt-val">AED ${fmt(cp.lifetime_summary.total_inbound_amount + cp.lifetime_summary.total_outbound_amount)}</div>
      <div class="tt-key">Relationship</div><div class="tt-val">${cp.relationship.relationship_duration_months}m (${cp.relationship.activity_consistency})</div>
    </div>`;
  tt.classList.add("visible");
}

function hideEdgeTooltip() {
  document.querySelectorAll(".edge-path").forEach(el => {
    const cp = GRAPH[el.dataset.cp];
    if (cp) { el.setAttribute("opacity", "0.4"); el.setAttribute("stroke-width", edgeWidth(cp)); }
  });
  document.querySelectorAll("[data-edge-label]").forEach(el => { el.setAttribute("fill", "#64748b"); el.setAttribute("font-size", "10"); el.setAttribute("font-weight", "400"); });
  document.getElementById("edgeTooltip").classList.remove("visible");
}

// ---- Node selection / detail panel ----
function selectNode(id) {
  selected = selected === id ? null : id;
  renderGraph();
  renderDetail();
}

function renderDetail() {
  const panel = document.getElementById("detailPanel");

  if (!selected) {
    panel.innerHTML = `<div class="detail-empty"><div class="icon">🔍</div><p>Click a node to view details<br><br>Hover an edge to view relationship</p></div>`;
    return;
  }

  if (selected === "__customer__") {
    const c = CUSTOMER;
    let summary = "";
    if (c.total_credits != null) {
      const ratio = c.credits_to_income_ratio ? `(${c.credits_to_income_ratio}x declared income)` : "";
      const passThrough = c.credit_to_debit_ratio ? `(${(c.credit_to_debit_ratio * 100).toFixed(1)}% pass-through)` : "";
      summary = `<div class="alert-box" style="margin-top:20px;background:rgba(234,179,8,0.08);border:1px solid rgba(234,179,8,0.15)">
        <h4 style="color:#eab308">Event Period Summary</h4>
        <p>Total credits: AED ${fmt(c.total_credits)} ${ratio}<br>Total debits: AED ${fmt(c.total_debits)} ${passThrough}<br>Unique credit CPs: ${inboundCPs.length}<br>Unique debit CPs: ${outboundCPs.length}</p>
      </div>`;
    }
    const names = cpNames.join(", ");
    panel.innerHTML = `
      <div style="font-size:10px;color:#64748b;letter-spacing:0.08em;margin-bottom:4px">SUBJECT CUSTOMER</div>
      <div style="font-size:18px;font-weight:700;margin-bottom:16px">${c.name}</div>
      <div style="display:flex;gap:8px;margin-bottom:20px">
        <span class="tag" style="background:rgba(59,130,246,0.12);color:#60a5fa">${c.segment}</span>
        <span class="tag" style="background:${riskColor(c.risk_score)}20;color:${riskColor(c.risk_score)}">${c.risk_rating} risk</span>
      </div>
      ${[["Score", c.risk_score.toFixed(2)], ["Nationality", c.nationality], ["Employer", c.employer], ["Declared Income", c.declared_income ? "AED " + fmt(c.declared_income) + "/month" : "—"], ["Account Opened", c.account_opened]].map(([k,v]) => `<div class="detail-row"><span class="k">${k}</span><span class="v">${v || "—"}</span></div>`).join("")}
      ${summary}
      <div style="margin-top:12px;padding:12px;border-radius:8px;background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.15)">
        <h4 style="font-size:11px;font-weight:600;color:#a855f7;margin-bottom:4px">🔗 Name Matching (AI-Evaluated)</h4>
        <p style="font-size:10px;color:#94a3b8;line-height:1.5">Counterparty names: <strong>${names}</strong><br><br>AI evaluates name similarity to customer and between counterparties at Node 2.</p>
      </div>`;
    return;
  }

  const cp = GRAPH[selected];
  if (!cp) return;
  const score = getScore(cp);
  const prof = cp.counterparty_profile;
  const isInt = prof.is_internal_customer;
  const scoreNote = isInt ? `Max score (${PARAMS.score_lookback_months}m lookback)` : `Weighted avg of ${prof.network.connected_customer_count} internal connections`;

  // Tags
  let tags = `<span class="tag" style="background:rgba(255,255,255,0.06);color:#94a3b8">${prof.counterparty_type}</span>`;
  tags += isInt ? `<span class="tag" style="background:rgba(59,130,246,0.12);color:#60a5fa">internal</span>` : `<span class="tag" style="background:rgba(148,163,184,0.12);color:#94a3b8;border:1px dashed rgba(148,163,184,0.3)">external</span>`;
  if (prof.network.is_hub) tags += `<span class="tag" style="background:rgba(124,58,237,0.15);color:#a78bfa">hub (${prof.network.connected_customer_count})</span>`;
  if (cp.relationship.is_new_in_event_period) tags += `<span class="tag" style="background:rgba(239,68,68,0.12);color:#f87171">NEW in event</span>`;
  tags += `<span class="tag" style="background:rgba(239,68,68,0.08);color:#f87171">no clearance</span>`;

  // Compliance section
  let complianceHTML = "";
  if (isInt) {
    const items = [["Alerts", prof.compliance_own.own_alert_count, prof.compliance_own.own_alert_count > 0 ? "#f97316" : "#22c55e"], ["SARs", prof.compliance_own.own_sar_count, prof.compliance_own.own_sar_count > 0 ? "#ef4444" : "#22c55e"], ["Cleared", prof.compliance_own.own_prior_clearance_count, "#60a5fa"]];
    complianceHTML = `<div class="section-title">COMPLIANCE HISTORY</div><div class="compliance-grid">${items.map(([l,n,c]) => `<div class="compliance-cell" style="background:${c}10;border:1px solid ${c}25"><div class="num" style="color:${c}">${n}</div><div class="lbl">${l}</div></div>`).join("")}</div>`;
  }

  // Connected compliance
  const conn = prof.compliance_connected;
  let connHTML = `<div class="section-title">1-HOP NETWORK</div>`;
  connHTML += [["Connected Customers", prof.network.connected_customer_count], ["Connected SAR Customers", conn.connected_sar_customer_count], ["Connected Alert Customers", conn.connected_alert_customer_count], ["Cases Open in Event", conn.connected_case_open_count]].map(([k,v]) => `<div class="detail-row"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("");
  if (!isInt && prof.external) connHTML += `<div class="detail-row"><span class="k">High Risk Connected</span><span class="v">${prof.external.connected_high_risk_count}</span></div>`;

  // Event vs baseline
  const evb = cp.event_vs_baseline;
  const isWarn = evb.is_volume_spike || evb.is_entirely_new;
  const volText = evb.is_entirely_new ? "Entirely new in event period — no baseline exists" : evb.inbound_amount_change ? `Inbound volume change: ${evb.inbound_amount_change}x` : evb.outbound_amount_change ? `Outbound volume change: ${evb.outbound_amount_change}x` : "No significant change";

  panel.innerHTML = `
    <div style="font-size:10px;color:#64748b;letter-spacing:0.08em;margin-bottom:4px">${isInt ? "INTERNAL" : "EXTERNAL"} COUNTERPARTY</div>
    <div style="font-size:16px;font-weight:700;margin-bottom:8px">${selected}</div>
    <div style="margin-bottom:20px">
      <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:6px">
        <span style="color:#64748b">Risk Score</span>
        <span style="color:${riskColor(score)};font-weight:700">${score != null ? score.toFixed(2) : "Unknown"} — ${riskLabel(score)}</span>
      </div>
      <div class="risk-bar-track"><div class="risk-bar-fill" style="width:${(score||0)*100}%"></div></div>
      <div style="font-size:10px;color:#475569;margin-top:4px">${scoreNote}</div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px">${tags}</div>
    <div class="section-title">RELATIONSHIP</div>
    ${[["First Transaction", cp.relationship.first_transaction_date], ["Duration", cp.relationship.relationship_duration_months + " months"], ["Months Active", cp.relationship.months_active], ["Pattern", cp.relationship.activity_consistency], ["Bidirectional", cp.relationship.is_bidirectional ? "Yes" : "No"]].map(([k,v]) => `<div class="detail-row"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("")}
    ${complianceHTML}
    ${connHTML}
    <div class="section-title">LIFETIME (${PARAMS.lifetime_lookback_months}m)</div>
    ${[["Total Inbound", `AED ${fmt(cp.lifetime_summary.total_inbound_amount)} (${cp.lifetime_summary.total_inbound_count} txns)`], ["Total Outbound", `AED ${fmt(cp.lifetime_summary.total_outbound_amount)} (${cp.lifetime_summary.total_outbound_count} txns)`], ["Net Flow", `AED ${fmt(cp.lifetime_summary.net_flow)}`]].map(([k,v]) => `<div class="detail-row"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("")}
    <div class="alert-box" style="background:${isWarn ? "rgba(249,115,22,0.08)" : "rgba(255,255,255,0.03)"};border:1px solid ${isWarn ? "rgba(249,115,22,0.2)" : "rgba(255,255,255,0.05)"}">
      <h4 style="color:${isWarn ? "#f97316" : "#94a3b8"}">Event vs Baseline ${isWarn ? "⚠" : ""}</h4>
      <p>${volText}<br>Event refs: ${(cp.event_period.common_references || []).join(", ") || "—"}<br>Round amounts: ${cp.event_period.round_amount_count} of ${cp.event_period.inbound_count + cp.event_period.outbound_count} txns</p>
    </div>`;
}

// ---- Parameters panel ----
const PARAMS_META = [
  { key: "score_lookback_months", label: "Score Lookback", unit: "months", min: 3, max: 36, step: 3 },
  { key: "lifetime_lookback_months", label: "Lifetime Window", unit: "months", min: 3, max: 60, step: 3 },
  { key: "volume_spike_threshold", label: "Spike Threshold", unit: "x", min: 1.5, max: 5, step: 0.5 },
  { key: "hub_threshold", label: "Hub Threshold", unit: "conn", min: 3, max: 50, step: 1 },
  { key: "dormancy_gap_months", label: "Dormancy Gap", unit: "months", min: 2, max: 12, step: 1 },
  { key: "new_relationship_months", label: "New Relationship", unit: "months", min: 1, max: 12, step: 1 },
  { key: "materiality_threshold", label: "Materiality", unit: "AED", min: 10000, max: 500000, step: 10000 },
  { key: "round_amount_pct_threshold", label: "Round Amt %", unit: "%", min: 0.2, max: 0.9, step: 0.05 },
];

function toggleParams() {
  const panel = document.getElementById("paramsPanel");
  const btn = document.getElementById("btnParams");
  const visible = panel.classList.toggle("visible");
  btn.classList.toggle("active", visible);
  btn.textContent = visible ? "⚙ Parameters ▾" : "⚙ Parameters ▸";
  if (visible) renderParams();
}

function renderParams() {
  const panel = document.getElementById("paramsPanel");
  panel.innerHTML = `<h3>Configurable Parameters</h3><div class="params-sub">Values used for this case. Adjust thresholds per deployment.</div>` +
    PARAMS_META.map(p => {
      const val = PARAMS[p.key];
      const display = p.unit === "AED" ? "AED " + fmt(val) : p.unit === "%" ? (val * 100).toFixed(0) + "%" : val + " " + p.unit;
      return `<div class="param-group"><div class="param-header"><span class="param-label">${p.label}</span><span class="param-value">${display}</span></div><div class="param-bounds"><span>${p.min}</span><span style="color:#64748b;font-style:italic">current: ${display}</span><span>${p.max}</span></div></div>`;
    }).join("");
}

// ---- Init ----
renderGraph();
renderDetail();
</script>
</body>
</html>"""
