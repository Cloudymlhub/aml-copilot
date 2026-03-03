"""
Counterparty Graph Visualization — Interactive HTML via vis.js

Converts CounterpartyGraph results directly to vis.js JSON and renders
as a self-contained HTML file with force-directed layout, controls, and tooltips.
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Tuple

from .models import CounterpartyEntry, CustomerGraph

# =============================================================================
# VIS.JS DATA CONVERSION
# =============================================================================


def _results_to_visjs(
    results: Dict[str, CustomerGraph],
    customer_cif: Optional[str] = None,
) -> Tuple[List[dict], List[dict]]:
    """
    Convert results to vis.js nodes and edges.

    Args:
        results: Dict of CustomerGraph keyed by cif_no
        customer_cif: If set, filter to only this customer's subgraph

    Returns:
        (nodes, edges) lists for vis.js
    """
    if customer_cif and customer_cif in results:
        filtered = {customer_cif: results[customer_cif]}
    else:
        filtered = results

    nodes_map: Dict[str, dict] = {}
    edges_list: List[dict] = []
    edge_id = 0

    for cif_no, cg in filtered.items():
        # Customer node
        if cif_no not in nodes_map:
            nodes_map[cif_no] = _make_customer_node(cif_no, cg)

        # Counterparty nodes + edges
        for target_id, entry in cg.counterparties.items():
            if target_id not in nodes_map:
                nodes_map[target_id] = _make_counterparty_node(target_id, entry)

            edge_id += 1
            edges_list.append(
                _make_edge(edge_id, cif_no, target_id, entry)
            )

    return list(nodes_map.values()), edges_list


def _make_customer_node(cif_no: str, cg: CustomerGraph) -> dict:
    """Create vis.js node for a reviewed customer."""
    profile = cg.profile
    tooltip_lines = [
        f"<b>Customer: {cif_no}</b>",
        f"Segment: {profile.segment or 'N/A'}",
        f"Score: {profile.score or 'N/A'}",
        f"Alerts: {profile.alert_count}",
        f"Cases: {profile.case_count}",
        f"SARs: {profile.sar_count}",
        f"Counterparties: {cg.summary.total_counterparties}",
        f"Internal: {cg.summary.internal_count} | External: {cg.summary.external_count}",
    ]

    return {
        "id": cif_no,
        "label": cif_no,
        "title": "<br>".join(tooltip_lines),
        "color": {"background": "#4A90D9", "border": "#2C5F9E"},
        "shape": "dot",
        "size": 25,
        "font": {"color": "#FFFFFF", "size": 12},
        "group": "customer",
    }


def _make_counterparty_node(target_id: str, entry: CounterpartyEntry) -> dict:
    """Create vis.js node for a counterparty."""
    is_internal = entry.target_is_internal
    is_hub = entry.network.is_hub

    # Determine color based on type and risk
    if not is_internal:
        color = {"background": "#9B9B9B", "border": "#6B6B6B"}
        risk_label = "External"
    elif entry.internal_profile and entry.internal_profile.internal_risk_rating == "high":
        color = {"background": "#D0021B", "border": "#8B0000", "borderWidth": 3}
        risk_label = "High Risk"
    elif entry.internal_profile and entry.internal_profile.internal_risk_rating == "medium":
        color = {"background": "#F5A623", "border": "#C47F0E"}
        risk_label = "Medium Risk"
    else:
        color = {"background": "#7EC850", "border": "#4A8A2A"}
        risk_label = "Low Risk"

    shape = "star" if is_hub else ("dot" if is_internal else "diamond")

    tooltip_lines = [
        f"<b>{entry.counterparty_name}</b> ({target_id})",
        f"Account: {entry.counterparty_account}",
        f"Type: {'Internal' if is_internal else 'External'} | {risk_label}",
        f"Hub: {'Yes' if is_hub else 'No'} (connections: {entry.network.connected_customer_count})",
    ]

    if entry.internal_profile:
        ip = entry.internal_profile
        tooltip_lines.extend([
            f"Score: {ip.internal_max_score or 'N/A'}",
            f"Segment: {ip.internal_segment or 'N/A'}",
        ])

    if entry.compliance_own.own_alert_count > 0:
        tooltip_lines.append(
            f"Alerts: {entry.compliance_own.own_alert_count} | "
            f"Cases: {entry.compliance_own.own_case_count} | "
            f"SARs: {entry.compliance_own.own_sar_count}"
        )

    ls = entry.lifetime_summary
    tooltip_lines.extend([
        f"Lifetime: {ls.total_inbound_count + ls.total_outbound_count} txns, "
        f"${ls.total_inbound_amount + ls.total_outbound_amount:,.0f}",
        f"Net flow: ${ls.net_flow:,.0f}",
    ])

    return {
        "id": target_id,
        "label": entry.counterparty_name or target_id,
        "title": "<br>".join(tooltip_lines),
        "color": color,
        "shape": shape,
        "size": 15,
        "group": "internal" if is_internal else "external",
    }


def _make_edge(
    edge_id: int,
    source: str,
    target: str,
    entry: CounterpartyEntry,
) -> dict:
    """Create vis.js edge between customer and counterparty."""
    ls = entry.lifetime_summary
    total_amount = ls.total_inbound_amount + ls.total_outbound_amount

    # Width proportional to log of amount
    width = max(1.0, min(10.0, math.log10(max(total_amount, 1)) - 1))

    # Color based on spike / new relationship
    evb = entry.event_vs_baselines.get("event")
    is_spike = evb.is_volume_spike if evb else False
    is_new = entry.relationship.is_new_in_event_period

    if is_spike:
        color = "#D0021B"
        dashes = False
    elif is_new:
        color = "#F5A623"
        dashes = True
    else:
        color = "#CCCCCC"
        dashes = False

    tooltip_lines = [
        f"<b>{source} → {entry.counterparty_name}</b>",
        f"Total: ${total_amount:,.0f}",
        f"In: {ls.total_inbound_count} (${ls.total_inbound_amount:,.0f})",
        f"Out: {ls.total_outbound_count} (${ls.total_outbound_amount:,.0f})",
        f"Bidirectional: {'Yes' if entry.relationship.is_bidirectional else 'No'}",
    ]

    if evb:
        tooltip_lines.append(f"Volume spike: {'YES' if is_spike else 'No'}")
    if is_new:
        tooltip_lines.append("NEW relationship in event period")

    return {
        "id": edge_id,
        "from": source,
        "to": target,
        "title": "<br>".join(tooltip_lines),
        "width": round(width, 1),
        "color": {"color": color},
        "dashes": dashes,
        "arrows": "to" if not entry.relationship.is_bidirectional else "to,from",
    }


# =============================================================================
# HTML RENDERING
# =============================================================================

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #1a1a2e; color: #eee; }}
        #graph-container {{ width: 100%; height: 85vh; border: 1px solid #333; }}
        .controls {{ padding: 10px 20px; display: flex; gap: 20px; align-items: center; }}
        .controls label {{ cursor: pointer; font-size: 14px; }}
        .legend {{ display: flex; gap: 15px; margin-left: auto; font-size: 12px; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
        .legend-diamond {{ width: 12px; height: 12px; transform: rotate(45deg); display: inline-block; }}
        h2 {{ margin: 10px 20px 0; font-size: 18px; }}
    </style>
</head>
<body>
    <h2>{title}</h2>
    <div class="controls">
        <label><input type="checkbox" id="toggle-external" checked> Show External</label>
        <label><input type="checkbox" id="toggle-labels" checked> Show Labels</label>
        <div class="legend">
            <div class="legend-item"><span class="legend-dot" style="background:#4A90D9"></span> Customer</div>
            <div class="legend-item"><span class="legend-dot" style="background:#7EC850"></span> Internal (Low)</div>
            <div class="legend-item"><span class="legend-dot" style="background:#F5A623"></span> Internal (Medium)</div>
            <div class="legend-item"><span class="legend-dot" style="background:#D0021B"></span> Internal (High)</div>
            <div class="legend-diamond-wrap legend-item"><span class="legend-diamond" style="background:#9B9B9B"></span> External</div>
            <div class="legend-item"><span style="color:#D0021B; font-weight:bold;">—</span> Spike</div>
            <div class="legend-item"><span style="color:#F5A623;">- -</span> New</div>
        </div>
    </div>
    <div id="graph-container"></div>
    <script>
        var nodesData = {nodes_json};
        var edgesData = {edges_json};

        var nodes = new vis.DataSet(nodesData);
        var edges = new vis.DataSet(edgesData);

        var container = document.getElementById('graph-container');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            physics: {{
                forceAtlas2Based: {{
                    gravitationalConstant: -50,
                    centralGravity: 0.01,
                    springLength: 150,
                    springConstant: 0.08,
                }},
                solver: 'forceAtlas2Based',
                stabilization: {{ iterations: 200 }},
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
            }},
            nodes: {{
                borderWidth: 2,
                shadow: true,
            }},
            edges: {{
                smooth: {{ type: 'continuous' }},
                shadow: false,
            }},
        }};

        var network = new vis.Network(container, data, options);

        // Toggle external nodes
        document.getElementById('toggle-external').addEventListener('change', function() {{
            var show = this.checked;
            var updates = [];
            nodesData.forEach(function(n) {{
                if (n.group === 'external') {{
                    updates.push({{ id: n.id, hidden: !show }});
                }}
            }});
            nodes.update(updates);
        }});

        // Toggle labels
        document.getElementById('toggle-labels').addEventListener('change', function() {{
            var show = this.checked;
            var updates = [];
            nodesData.forEach(function(n) {{
                updates.push({{ id: n.id, font: {{ size: show ? 12 : 0 }} }});
            }});
            nodes.update(updates);
        }});
    </script>
</body>
</html>"""


def render_graph_html(
    results: Dict[str, CustomerGraph],
    customer_cif: Optional[str] = None,
    title: str = "Counterparty Network",
    output_path: str = "counterparty_graph.html",
) -> str:
    """Render results as interactive HTML with vis.js."""
    nodes, edges = _results_to_visjs(results, customer_cif)

    html = _HTML_TEMPLATE.format(
        title=title,
        nodes_json=json.dumps(nodes, indent=2),
        edges_json=json.dumps(edges, indent=2),
    )

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def visualize(
    results: Dict[str, CustomerGraph],
    customer_cif: Optional[str] = None,
    title: str = "Counterparty Network",
    output_path: str = "counterparty_graph.html",
) -> str:
    """Convenience wrapper. Returns file path."""
    return render_graph_html(results, customer_cif, title, output_path)
