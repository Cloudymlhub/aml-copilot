"""
Shared assembly logic: dict rows → Pydantic models.

Used by both spark.py and pandas.py to avoid duplicating ~150 lines
of dict→Pydantic conversion code.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from ..models import (
    BaselinePeriodAggregates,
    CaseContext,
    ComplianceConnected,
    ComplianceOwn,
    CounterpartyEntry,
    CustomerGraph,
    CustomerProfile,
    CustomerSummary,
    EventPeriodAggregates,
    EventVsBaseline,
    ExternalProfile,
    GraphParameters,
    InternalProfile,
    LifetimeSummary,
    NetworkPosition,
    RelationshipProfile,
)


def _is_missing(val) -> bool:
    """Check if value is None or NaN (pandas uses NaN for missing)."""
    if val is None:
        return True
    try:
        import math
        return math.isnan(val)
    except (TypeError, ValueError):
        return False


def _int(val):
    return int(val) if not _is_missing(val) else 0


def _float(val):
    return round(float(val), 2) if not _is_missing(val) else 0.0


def _float_or_none(val):
    return round(float(val), 4) if not _is_missing(val) else None


def _date_str(val):
    if val is None:
        return None
    # pandas NaT
    try:
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        return str(val)
    except (ValueError, AttributeError):
        return None


def _assemble_from_rows(
    rows: List[dict],
    node_rows: List[dict],
    contexts: List[CaseContext],
    params: GraphParameters,
) -> Dict[str, CustomerGraph]:
    """
    Build CustomerGraph objects from row dicts. Engine-agnostic.

    Args:
        rows: Joined first+second degree rows as list of dicts.
        node_rows: Node attribute rows as list of dicts.
        contexts: Original CaseContext list.
        params: Graph parameters (for thresholds).

    Returns:
        Dict mapping cif_no → CustomerGraph.
    """
    # Build node lookup
    node_lookup: Dict[str, dict] = {}
    for d in node_rows:
        cif = d.get("node_cif")
        if cif:
            node_lookup[cif] = d

    # Group rows by customer
    customer_rows: Dict[str, list] = {}
    for r in rows:
        cif = r.get("cif_no")
        if cif:
            customer_rows.setdefault(cif, []).append(r)

    results: Dict[str, CustomerGraph] = {}

    for ctx in contexts:
        cif = ctx.cif_no

        # Customer profile from node attributes
        na = node_lookup.get(cif, {})
        profile = CustomerProfile(
            cif_no=cif,
            segment=na.get("node_segment"),
            declared_income=_float_or_none(na.get("node_declared_income")),
            alert_count=_int(na.get("node_alert_count")),
            case_count=_int(na.get("node_case_count")),
            sar_count=_int(na.get("node_sar_count")),
            has_open_case=bool(na.get("node_has_open_case")),
        )

        counterparties: Dict[str, CounterpartyEntry] = {}
        hub_count = 0
        high_risk_count = 0
        internal_count = 0
        external_count = 0

        for r in customer_rows.get(cif, []):
            target = r.get("target")
            if not target:
                continue

            is_internal = bool(r.get("target_is_internal"))
            if is_internal:
                internal_count += 1
            else:
                external_count += 1

            relationship = RelationshipProfile(
                first_transaction_date=_date_str(r.get("first_txn_date")),
                last_transaction_date=_date_str(r.get("last_txn_date")),
                relationship_duration_months=_int(r.get("months_active")),
                months_active=_int(r.get("months_active")),
                is_new_in_event_period=bool(r.get("is_new_in_event_period")),
                is_bidirectional=bool(r.get("is_bidirectional")),
            )

            lifetime = LifetimeSummary(
                total_inbound_count=_int(r.get("lt_in_count")),
                total_inbound_amount=_float(r.get("lt_in_amt")),
                total_outbound_count=_int(r.get("lt_out_count")),
                total_outbound_amount=_float(r.get("lt_out_amt")),
                net_flow=_float(r.get("lt_net")),
            )

            event_period = EventPeriodAggregates(
                inbound_count=_int(r.get("ev_in_count")),
                inbound_amount=_float(r.get("ev_in_amt")),
                outbound_count=_int(r.get("ev_out_count")),
                outbound_amount=_float(r.get("ev_out_amt")),
                round_amount_count=_int(r.get("ev_round_count")),
            )

            baseline = BaselinePeriodAggregates(
                inbound_count=_int(r.get("bl_in_count")),
                inbound_amount=_float(r.get("bl_in_amt")),
                outbound_count=_int(r.get("bl_out_count")),
                outbound_amount=_float(r.get("bl_out_amt")),
            )

            evb = EventVsBaseline(
                inbound_amount_change=_float_or_none(r.get("evb_in_change")),
                outbound_amount_change=_float_or_none(r.get("evb_out_change")),
                is_volume_spike=bool(r.get("evb_is_spike")),
                is_entirely_new=bool(r.get("evb_is_new")),
            )

            network = NetworkPosition(
                connected_customer_count=_int(r.get("net_cust_count")),
                is_hub=bool(r.get("net_is_hub")),
                hub_score=_float(r.get("net_hub_score")),
            )

            if bool(r.get("net_is_hub")):
                hub_count += 1

            compliance_own = ComplianceOwn(
                own_alert_count=_int(r.get("cm_own_alert")),
                own_case_count=_int(r.get("cm_own_case")),
                own_sar_count=_int(r.get("cm_own_sar")),
                own_has_open_case=bool(r.get("cm_own_has_open")),
                own_prior_clearance_count=_int(r.get("cm_own_clearance")),
                own_last_clearance_date=_date_str(r.get("cm_own_last_clear")),
            )

            compliance_connected = ComplianceConnected(
                connected_alert_customer_count=_int(r.get("cm_conn_alert")),
                connected_case_customer_count=_int(r.get("cm_conn_case")),
                connected_sar_customer_count=_int(r.get("cm_conn_sar")),
                connected_case_open_count=_int(r.get("cm_conn_open")),
            )

            # Internal vs external profile
            internal_profile = None
            external_profile = None

            if is_internal:
                sc_max = _float_or_none(r.get("sc_internal_max"))
                internal_profile = InternalProfile(
                    internal_customer_id=target,
                    internal_max_score=sc_max,
                    internal_risk_rating=r.get("sc_internal_rating"),
                    internal_segment=r.get("kyc_segment"),
                    internal_declared_income=_float_or_none(
                        r.get("kyc_declared_income")
                    ),
                )
                if sc_max is not None and sc_max >= params.rating_high_threshold:
                    high_risk_count += 1
            else:
                external_profile = ExternalProfile(
                    weighted_avg_score=_float_or_none(
                        r.get("sc_external_weighted_avg")
                    ),
                )

            is_self = bool(r.get("is_self_transfer"))

            entry = CounterpartyEntry(
                counterparty_account=r.get("target_account", target),
                counterparty_name=r.get("target_name", target),
                target_is_internal=is_internal,
                is_self_transfer=is_self,
                relationship=relationship,
                lifetime_summary=lifetime,
                event_periods={"event": event_period},
                baseline_period=baseline,
                event_vs_baselines={"event": evb},
                network=network,
                compliance_own=compliance_own,
                compliance_connected=compliance_connected,
                internal_profile=internal_profile,
                external_profile=external_profile,
            )

            counterparties[target] = entry

        summary = CustomerSummary(
            total_counterparties=len(counterparties),
            internal_count=internal_count,
            external_count=external_count,
            hub_counterparties=hub_count,
            high_risk_counterparties=high_risk_count,
        )

        results[cif] = CustomerGraph(
            profile=profile,
            counterparties=counterparties,
            summary=summary,
        )

    return results
