"""
Report generation: Text reports, Excel export, hover text.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from .core import EventWindow


def format_text_report(
    window: EventWindow,
    shifts: Dict,
    flags: List[Dict],
    drivers: Dict[str, pd.DataFrame]
) -> str:
    """Format a human-readable report for L2 reviewers"""
    
    lines = [
        "=" * 60,
        "AML EVENT CHARACTERIZATION REPORT",
        "=" * 60,
        f"User ID: {window.user_id}",
        f"Event Date: {window.event_date.strftime('%Y-%m-%d')}",
        f"Event Window: {window.event_start.strftime('%Y-%m-%d')} to {window.event_date.strftime('%Y-%m-%d')}",
        f"Baseline Window: {window.baseline_start.strftime('%Y-%m-%d')} to {window.baseline_end.strftime('%Y-%m-%d')}",
        "",
        "-" * 60,
        "SUMMARY METRICS",
        "-" * 60,
        f"Event transactions: {shifts['txn_count_event']} (${shifts['total_volume_event']:,.0f})",
        f"Baseline transactions: {shifts['txn_count_baseline']} (${shifts['total_volume_baseline']:,.0f})",
        f"New counterparties in event: {shifts['new_counterparty_count']}",
        "",
    ]
    
    # Flags
    if flags:
        lines.extend([
            "-" * 60,
            "FLAGS TRIGGERED",
            "-" * 60,
        ])
        
        for flag in flags:
            lines.append(f"\n[{flag['severity']}] {flag['flag_type']}")
            lines.append(f"  {flag['description']}")
            if flag['supporting_txns']:
                lines.append(f"  Supporting TXN IDs: {', '.join(map(str, flag['supporting_txns'][:5]))}")
    else:
        lines.append("No significant behavioral shifts detected.")
    
    # Key transactions
    lines.extend([
        "",
        "-" * 60,
        "KEY TRANSACTIONS",
        "-" * 60,
    ])
    
    if 'largest_transactions' in drivers and len(drivers['largest_transactions']) > 0:
        lines.append("\nLargest Transactions in Event Window:")
        lines.append(drivers['largest_transactions'].to_string(index=False))
    
    if 'new_counterparty_transactions' in drivers and len(drivers['new_counterparty_transactions']) > 0:
        lines.append("\nTransactions with NEW Counterparties:")
        lines.append(drivers['new_counterparty_transactions'].to_string(index=False))
    
    # Counterparty breakdown
    if 'counterparty_breakdown' in drivers and len(drivers['counterparty_breakdown']) > 0:
        lines.extend([
            "",
            "-" * 60,
            "COUNTERPARTY BREAKDOWN",
            "-" * 60,
        ])
        
        cp_df = drivers['counterparty_breakdown'].copy()
        
        # Format amounts
        for col in ['credit_amount', 'debit_amount', 'net_flow', 'total_volume']:
            if col in cp_df.columns:
                cp_df[col] = cp_df[col].apply(lambda x: f"${x:,.0f}")
        
        if 'is_new' in cp_df.columns:
            cp_df['is_new'] = cp_df['is_new'].apply(lambda x: '* NEW' if x else '')
        
        lines.append(cp_df.to_string(index=False))
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


def format_hover_text(
    event_date: pd.Timestamp,
    risk_tier: str,
    shifts: Optional[Dict] = None,
    flags: Optional[List[Dict]] = None,
    score_value: Optional[float] = None
) -> str:
    """
    Build compact hover text for visualization.
    Shows: date, risk tier, top flags, volume change %
    """
    
    date_str = event_date.strftime('%Y-%m-%d') if hasattr(event_date, 'strftime') else str(event_date)
    
    hover_lines = [
        f"<b>Event: {date_str}</b>",
        f"<b>Risk Tier: {risk_tier}</b>",
    ]
    
    if score_value is not None:
        hover_lines.append(f"Score: {score_value:.3f}")
    
    if flags:
        hover_lines.append("")
        for flag in flags[:3]:
            short_flag = flag['flag_type'].replace('_', ' ').title()
            hover_lines.append(f"• {short_flag}")
    
    if shifts:
        hover_lines.append("")
        
        vol_event = shifts.get('total_volume_event', 0)
        vol_baseline = shifts.get('total_volume_baseline', 0)
        if vol_baseline > 0:
            vol_change = (vol_event - vol_baseline) / vol_baseline * 100
            hover_lines.append(f"Volume: {vol_change:+.0f}%")
        
        txn_count = shifts.get('txn_count_event', 0)
        if txn_count:
            hover_lines.append(f"Txns in window: {int(txn_count)}")
        
        new_cp = shifts.get('new_counterparty_count', 0)
        if new_cp > 0:
            hover_lines.append(f"New counterparties: {int(new_cp)}")
    
    return '<br>'.join(hover_lines)


def export_to_excel(
    results: Dict,
    output_path: str,
    include_stats: bool = True
) -> str:
    """
    Export batch results to Excel workbook.
    
    Args:
        results: Dict with summary_df, flags_df, drivers_df, counterparty_df, failed
        output_path: Where to save Excel file
        include_stats: Whether to include stats sheet
    
    Returns:
        Path to output file
    """
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        
        # Summary
        summary_df = results.get('summary_df', pd.DataFrame())
        if len(summary_df) > 0:
            summary_df = summary_df.sort_values(
                ['high_severity_count', 'flags_count'], 
                ascending=[False, False]
            )
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Flags
        flags_df = results.get('flags_df', pd.DataFrame())
        if len(flags_df) > 0:
            flags_df.to_excel(writer, sheet_name='Flags', index=False)
        
        # Drivers/Transactions
        drivers_df = results.get('drivers_df', pd.DataFrame())
        if len(drivers_df) > 0:
            drivers_df.to_excel(writer, sheet_name='Key_Transactions', index=False)
        
        # Counterparties
        counterparty_df = results.get('counterparty_df', pd.DataFrame())
        if len(counterparty_df) > 0:
            counterparty_df.to_excel(writer, sheet_name='Counterparties', index=False)
        
        # Stats
        if include_stats and len(summary_df) > 0:
            stats = _compute_stats(results)
            stats_df = pd.DataFrame([stats]).T
            stats_df.columns = ['Value']
            stats_df.to_excel(writer, sheet_name='Stats')
        
        # Failed
        failed = results.get('failed', [])
        if failed:
            failed_df = pd.DataFrame(failed)
            failed_df.to_excel(writer, sheet_name='Failed', index=False)
    
    return output_path


def _compute_stats(results: Dict) -> Dict:
    """Compute aggregate statistics"""
    
    summary_df = results.get('summary_df', pd.DataFrame())
    flags_df = results.get('flags_df', pd.DataFrame())
    
    if len(summary_df) == 0:
        return {}
    
    stats = {
        'total_events': len(summary_df),
        'events_with_flags': (summary_df['flags_count'] > 0).sum(),
        'events_high_severity': (summary_df['high_severity_count'] > 0).sum(),
        'total_flags': len(flags_df),
        'avg_flags_per_event': summary_df['flags_count'].mean(),
        'median_txn_size_ratio': summary_df['txn_size_ratio'].replace([np.inf, -np.inf], np.nan).median(),
        'median_velocity_ratio': summary_df['velocity_ratio'].replace([np.inf, -np.inf], np.nan).median(),
        'avg_new_cp_count': summary_df['new_cp_count'].mean(),
        'total_event_volume': summary_df['volume_event'].sum(),
        'unique_users': summary_df['user_id'].nunique(),
    }
    
    # Flag type distribution
    if len(flags_df) > 0 and 'flag_type' in flags_df.columns:
        flag_counts = flags_df['flag_type'].value_counts().to_dict()
        for flag_type, count in flag_counts.items():
            stats[f'flag_{flag_type}'] = count
    
    return stats