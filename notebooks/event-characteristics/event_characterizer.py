"""
AML Event Characterization Module
Computes behavioral shifts between baseline and event windows
Surfaces transaction IDs that drove the behavior change
"""

import pandas as pd
import numpy as np
from scipy.stats import entropy
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple


@dataclass
class EventWindow:
    """Defines an event and its baseline period"""
    user_id: str
    event_date: pd.Timestamp
    event_start: pd.Timestamp
    baseline_start: pd.Timestamp
    baseline_end: pd.Timestamp  # Same as event_start
    
    @classmethod
    def from_dates(cls, user_id: str, event_date: str, lookback_days: int = 30, baseline_days: int = 90):
        event_date = pd.to_datetime(event_date)
        event_start = event_date - pd.Timedelta(days=lookback_days)
        baseline_end = event_start
        baseline_start = baseline_end - pd.Timedelta(days=baseline_days)
        
        return cls(
            user_id=user_id,
            event_date=event_date,
            event_start=event_start,
            baseline_start=baseline_start,
            baseline_end=baseline_end
        )


def load_transactions(filepath: str) -> pd.DataFrame:
    """
    Load transaction CSV and standardize columns.
    Adjust column mappings to match your actual data.
    """
    df = pd.read_csv(filepath)
    
    # Standardize column names - ADJUST THESE TO YOUR ACTUAL COLUMNS
    column_mapping = {
        # 'your_column_name': 'standard_name'
        # Example:
        # 'TRANSACTION_ID': 'txn_id',
        # 'USER_ID': 'user_id',
        # 'TRANSACTION_DATE': 'tran_date',
        # 'TRANSACTION_TYPE': 'tran_type',
        # 'AMOUNT': 'amount',
        # 'COUNTERPARTY_ID': 'counterparty_id',
        # 'IS_CREDIT': 'is_credit',  # or derive from DEBIT_CREDIT column
    }
    
    # Apply mapping if needed
    if column_mapping:
        df = df.rename(columns=column_mapping)
    
    # Ensure date parsing
    df['tran_date'] = pd.to_datetime(df['tran_date'])
    
    # Ensure is_credit is boolean
    if df['is_credit'].dtype == 'object':
        df['is_credit'] = df['is_credit'].str.upper().isin(['CREDIT', 'C', 'CR', 'TRUE', '1'])
    
    return df


def split_windows(txns: pd.DataFrame, window: EventWindow) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split transactions into baseline and event windows for a user"""
    
    user_txns = txns[txns['user_id'] == window.user_id].copy()
    
    baseline = user_txns[
        (user_txns['tran_date'] >= window.baseline_start) & 
        (user_txns['tran_date'] < window.baseline_end)
    ]
    
    event = user_txns[
        (user_txns['tran_date'] >= window.event_start) & 
        (user_txns['tran_date'] <= window.event_date)
    ]
    
    return baseline, event


def top_n_share(df: pd.DataFrame, n: int = 3) -> float:
    """Calculate share of volume from top N counterparties"""
    if len(df) == 0 or df['amount'].sum() == 0:
        return 0.0
    
    top_volume = df.groupby('counterparty_id')['amount'].sum().nlargest(n).sum()
    return top_volume / df['amount'].sum()


def type_entropy(df: pd.DataFrame) -> float:
    """Calculate entropy of transaction type distribution"""
    if len(df) == 0:
        return 0.0
    
    type_counts = df['tran_type'].value_counts(normalize=True)
    return entropy(type_counts)


def get_new_counterparties(baseline: pd.DataFrame, event: pd.DataFrame) -> set:
    """Identify counterparties in event window not seen in baseline"""
    baseline_cps = set(baseline['counterparty_id'].unique())
    event_cps = set(event['counterparty_id'].unique())
    return event_cps - baseline_cps


def compute_behavior_shifts(baseline: pd.DataFrame, event: pd.DataFrame, window: EventWindow) -> Dict:
    """
    Compute all behavioral shift metrics between baseline and event windows.
    Returns dict of metrics with baseline, event, and delta values.
    """
    
    baseline_days = (window.baseline_end - window.baseline_start).days
    event_days = (window.event_date - window.event_start).days
    
    # Handle empty dataframes
    if len(baseline) == 0:
        baseline_avg_txn = 0
        baseline_velocity = 0
        baseline_credit_ratio = 0.5
        baseline_unique_ratio = 0
        baseline_top3_share = 0
        baseline_entropy = 0
    else:
        baseline_avg_txn = baseline['amount'].mean()
        baseline_velocity = len(baseline) / max(baseline_days, 1)
        baseline_credit_ratio = baseline['is_credit'].mean()
        baseline_unique_ratio = baseline['counterparty_id'].nunique() / len(baseline)
        baseline_top3_share = top_n_share(baseline, 3)
        baseline_entropy = type_entropy(baseline)
    
    if len(event) == 0:
        event_avg_txn = 0
        event_velocity = 0
        event_credit_ratio = 0.5
        event_unique_ratio = 0
        event_top3_share = 0
        event_entropy = 0
    else:
        event_avg_txn = event['amount'].mean()
        event_velocity = len(event) / max(event_days, 1)
        event_credit_ratio = event['is_credit'].mean()
        event_unique_ratio = event['counterparty_id'].nunique() / len(event)
        event_top3_share = top_n_share(event, 3)
        event_entropy = type_entropy(event)
    
    # New counterparty analysis
    new_cps = get_new_counterparties(baseline, event)
    if len(event) > 0 and event['amount'].sum() > 0:
        new_cp_volume = event[event['counterparty_id'].isin(new_cps)]['amount'].sum()
        new_cp_volume_share = new_cp_volume / event['amount'].sum()
        new_cp_count = len(new_cps)
    else:
        new_cp_volume_share = 0
        new_cp_count = 0
    
    return {
        # Volume behavior
        'avg_txn_size_baseline': baseline_avg_txn,
        'avg_txn_size_event': event_avg_txn,
        'txn_size_ratio': event_avg_txn / baseline_avg_txn if baseline_avg_txn > 0 else np.inf,
        
        # Velocity
        'txns_per_day_baseline': baseline_velocity,
        'txns_per_day_event': event_velocity,
        'velocity_ratio': event_velocity / baseline_velocity if baseline_velocity > 0 else np.inf,
        
        # Directionality
        'credit_ratio_baseline': baseline_credit_ratio,
        'credit_ratio_event': event_credit_ratio,
        'credit_shift': event_credit_ratio - baseline_credit_ratio,
        
        # Counterparty diversity
        'unique_cp_ratio_baseline': baseline_unique_ratio,
        'unique_cp_ratio_event': event_unique_ratio,
        
        # Concentration
        'top3_share_baseline': baseline_top3_share,
        'top3_share_event': event_top3_share,
        'concentration_shift': event_top3_share - baseline_top3_share,
        
        # Transaction type entropy
        'type_entropy_baseline': baseline_entropy,
        'type_entropy_event': event_entropy,
        'entropy_shift': event_entropy - baseline_entropy,
        
        # New counterparties
        'new_counterparty_count': new_cp_count,
        'new_counterparty_volume_share': new_cp_volume_share,
        'new_counterparty_ids': new_cps,
        
        # Totals
        'total_volume_baseline': baseline['amount'].sum() if len(baseline) > 0 else 0,
        'total_volume_event': event['amount'].sum() if len(event) > 0 else 0,
        'txn_count_baseline': len(baseline),
        'txn_count_event': len(event),
    }


def get_driving_transactions(event: pd.DataFrame, shifts: Dict, top_n: int = 5) -> Dict[str, pd.DataFrame]:
    """
    Identify specific transactions that drove each behavioral shift.
    Returns dict mapping flag type to relevant transaction IDs.
    """
    
    drivers = {}
    
    if len(event) == 0:
        return drivers
    
    # Largest transactions (driving size increase)
    drivers['largest_transactions'] = (
        event.nlargest(top_n, 'amount')[['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id', 'is_credit']]
        .copy()
    )
    
    # Credits driving credit shift
    if shifts['credit_shift'] > 0:
        credits = event[event['is_credit'] == True]
        drivers['top_credits'] = (
            credits.nlargest(top_n, 'amount')[['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id']]
            .copy()
        )
    
    # Debits driving debit shift
    if shifts['credit_shift'] < 0:
        debits = event[event['is_credit'] == False]
        drivers['top_debits'] = (
            debits.nlargest(top_n, 'amount')[['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id']]
            .copy()
        )
    
    # New counterparty transactions
    new_cps = shifts.get('new_counterparty_ids', set())
    if new_cps:
        new_cp_txns = event[event['counterparty_id'].isin(new_cps)]
        drivers['new_counterparty_transactions'] = (
            new_cp_txns.nlargest(top_n, 'amount')[['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id']]
            .copy()
        )
    
    # Top counterparty transactions (concentration)
    top_cp = event.groupby('counterparty_id')['amount'].sum().nlargest(3).index.tolist()
    drivers['top_counterparty_transactions'] = (
        event[event['counterparty_id'].isin(top_cp)]
        .nlargest(top_n, 'amount')[['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id']]
        .copy()
    )
    
    return drivers


def generate_flags(shifts: Dict, drivers: Dict, thresholds: Optional[Dict] = None) -> List[Dict]:
    """
    Generate human-readable flags with supporting transaction IDs.
    Returns list of flag dicts with description and evidence.
    """
    
    if thresholds is None:
        thresholds = {
            'txn_size_ratio': 1.5,
            'velocity_ratio': 2.0,
            'credit_shift': 0.15,
            'new_cp_volume_share': 0.3,
            'top3_share_event': 0.7,
            'concentration_shift': 0.15,
            'entropy_shift': -0.3,  # Negative means less diverse
        }
    
    flags = []
    
    # Transaction size increase
    if shifts['txn_size_ratio'] > thresholds['txn_size_ratio']:
        flag = {
            'flag_type': 'TRANSACTION_SIZE_INCREASE',
            'description': f"Transaction sizes {shifts['txn_size_ratio']:.1f}x baseline average "
                          f"(${shifts['avg_txn_size_event']:,.0f} vs ${shifts['avg_txn_size_baseline']:,.0f})",
            'severity': 'HIGH' if shifts['txn_size_ratio'] > 3 else 'MEDIUM',
            'supporting_txns': drivers.get('largest_transactions', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    # Velocity increase
    if shifts['velocity_ratio'] > thresholds['velocity_ratio']:
        flag = {
            'flag_type': 'VELOCITY_INCREASE',
            'description': f"Transaction frequency {shifts['velocity_ratio']:.1f}x baseline "
                          f"({shifts['txns_per_day_event']:.1f}/day vs {shifts['txns_per_day_baseline']:.1f}/day)",
            'severity': 'HIGH' if shifts['velocity_ratio'] > 4 else 'MEDIUM',
            'supporting_txns': drivers.get('largest_transactions', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    # Credit shift (inflows)
    if shifts['credit_shift'] > thresholds['credit_shift']:
        flag = {
            'flag_type': 'CREDIT_HEAVY',
            'description': f"Credit-heavy activity: {shifts['credit_ratio_event']:.0%} credits vs "
                          f"{shifts['credit_ratio_baseline']:.0%} baseline (+{shifts['credit_shift']:.0%} shift)",
            'severity': 'HIGH' if shifts['credit_shift'] > 0.3 else 'MEDIUM',
            'supporting_txns': drivers.get('top_credits', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    # Debit shift (outflows)
    if shifts['credit_shift'] < -thresholds['credit_shift']:
        flag = {
            'flag_type': 'DEBIT_HEAVY',
            'description': f"Debit-heavy activity: {1-shifts['credit_ratio_event']:.0%} debits vs "
                          f"{1-shifts['credit_ratio_baseline']:.0%} baseline",
            'severity': 'HIGH' if shifts['credit_shift'] < -0.3 else 'MEDIUM',
            'supporting_txns': drivers.get('top_debits', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    # New counterparties
    if shifts['new_counterparty_volume_share'] > thresholds['new_cp_volume_share']:
        flag = {
            'flag_type': 'NEW_COUNTERPARTY_VOLUME',
            'description': f"{shifts['new_counterparty_volume_share']:.0%} of volume to "
                          f"{shifts['new_counterparty_count']} NEW counterparties",
            'severity': 'HIGH' if shifts['new_counterparty_volume_share'] > 0.5 else 'MEDIUM',
            'supporting_txns': drivers.get('new_counterparty_transactions', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    # Concentration
    if shifts['top3_share_event'] > thresholds['top3_share_event']:
        flag = {
            'flag_type': 'COUNTERPARTY_CONCENTRATION',
            'description': f"Concentrated activity: top 3 counterparties = {shifts['top3_share_event']:.0%} of volume "
                          f"(vs {shifts['top3_share_baseline']:.0%} baseline)",
            'severity': 'HIGH' if shifts['top3_share_event'] > 0.85 else 'MEDIUM',
            'supporting_txns': drivers.get('top_counterparty_transactions', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    # Entropy decrease (less diverse transaction types)
    if shifts['entropy_shift'] < thresholds['entropy_shift']:
        flag = {
            'flag_type': 'REDUCED_DIVERSITY',
            'description': f"Less varied transaction types (entropy: {shifts['type_entropy_event']:.2f} vs "
                          f"{shifts['type_entropy_baseline']:.2f} baseline)",
            'severity': 'MEDIUM',
            'supporting_txns': drivers.get('largest_transactions', pd.DataFrame())['txn_id'].tolist()[:5]
        }
        flags.append(flag)
    
    return flags


def format_l2_report(window: EventWindow, shifts: Dict, flags: List[Dict], drivers: Dict) -> str:
    """Format a human-readable report for L2 reviewers"""
    
    lines = [
        "=" * 60,
        f"AML EVENT CHARACTERIZATION REPORT",
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
    
    # Add transaction detail tables
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
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


def characterize_event(
    txns: pd.DataFrame, 
    user_id: str, 
    event_date: str, 
    lookback_days: int = 30, 
    baseline_days: int = 90,
    thresholds: Optional[Dict] = None
) -> Dict:
    """
    Main entry point: characterize an event for a user.
    
    Args:
        txns: Transaction DataFrame
        user_id: User to analyze
        event_date: Date of the detected event/spike
        lookback_days: Days before event_date to consider as event window
        baseline_days: Days before event window to use as baseline
        thresholds: Optional custom thresholds for flag generation
    
    Returns:
        Dict with window, shifts, flags, drivers, and formatted report
    """
    
    window = EventWindow.from_dates(user_id, event_date, lookback_days, baseline_days)
    baseline, event = split_windows(txns, window)
    shifts = compute_behavior_shifts(baseline, event, window)
    drivers = get_driving_transactions(event, shifts)
    flags = generate_flags(shifts, drivers, thresholds)
    report = format_l2_report(window, shifts, flags, drivers)
    
    return {
        'window': window,
        'shifts': shifts,
        'flags': flags,
        'drivers': drivers,
        'report': report,
        'baseline_txns': baseline,
        'event_txns': event,
    }


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def run_batch_characterization(
    txns: pd.DataFrame,
    events: pd.DataFrame,
    lookback_days: int = 30,
    baseline_days: int = 90,
    thresholds: Optional[Dict] = None,
    verbose: bool = True
) -> Dict:
    """
    Run characterization for multiple events.
    
    Args:
        txns: Transaction DataFrame
        events: DataFrame with columns ['user_id', 'event_date'] 
                Optional columns: ['lookback_days', 'baseline_days', 'risk_tier']
        lookback_days: Default lookback if not in events df
        baseline_days: Default baseline if not in events df
        thresholds: Flag thresholds
        verbose: Print progress
    
    Returns:
        Dict with results, summary_df, flags_df, and failed events
    """
    
    results = []
    all_flags = []
    all_drivers = []
    failed = []
    
    total = len(events)
    
    for idx, row in events.iterrows():
        user_id = row['user_id']
        event_date = row['event_date']
        
        # Allow per-event overrides
        lb = row.get('lookback_days', lookback_days)
        bl = row.get('baseline_days', baseline_days)
        risk_tier = row.get('risk_tier', None)
        
        if verbose and (idx + 1) % 10 == 0:
            print(f"Processing {idx + 1}/{total}...")
        
        try:
            result = characterize_event(
                txns=txns,
                user_id=user_id,
                event_date=event_date,
                lookback_days=lb,
                baseline_days=bl,
                thresholds=thresholds
            )
            
            # Build summary row
            summary_row = {
                'user_id': user_id,
                'event_date': event_date,
                'risk_tier': risk_tier,
                'event_start': result['window'].event_start,
                'baseline_start': result['window'].baseline_start,
                'txn_count_event': result['shifts']['txn_count_event'],
                'txn_count_baseline': result['shifts']['txn_count_baseline'],
                'volume_event': result['shifts']['total_volume_event'],
                'volume_baseline': result['shifts']['total_volume_baseline'],
                'txn_size_ratio': result['shifts']['txn_size_ratio'],
                'velocity_ratio': result['shifts']['velocity_ratio'],
                'credit_shift': result['shifts']['credit_shift'],
                'new_cp_count': result['shifts']['new_counterparty_count'],
                'new_cp_volume_share': result['shifts']['new_counterparty_volume_share'],
                'top3_concentration': result['shifts']['top3_share_event'],
                'flags_count': len(result['flags']),
                'flag_types': ', '.join([f['flag_type'] for f in result['flags']]),
                'high_severity_count': sum(1 for f in result['flags'] if f['severity'] == 'HIGH'),
            }
            results.append(summary_row)
            
            # Flatten flags with event context
            for flag in result['flags']:
                flag_row = {
                    'user_id': user_id,
                    'event_date': event_date,
                    'risk_tier': risk_tier,
                    'flag_type': flag['flag_type'],
                    'severity': flag['severity'],
                    'description': flag['description'],
                    'supporting_txn_ids': ', '.join(map(str, flag['supporting_txns'][:10])),
                }
                all_flags.append(flag_row)
            
            # Flatten top drivers
            for driver_type, driver_df in result['drivers'].items():
                if len(driver_df) > 0:
                    for _, txn_row in driver_df.head(5).iterrows():
                        driver_row = {
                            'user_id': user_id,
                            'event_date': event_date,
                            'driver_type': driver_type,
                            'txn_id': txn_row.get('txn_id'),
                            'tran_date': txn_row.get('tran_date'),
                            'amount': txn_row.get('amount'),
                            'tran_type': txn_row.get('tran_type'),
                            'counterparty_id': txn_row.get('counterparty_id'),
                            'is_credit': txn_row.get('is_credit'),
                        }
                        all_drivers.append(driver_row)
                        
        except Exception as e:
            failed.append({
                'user_id': user_id,
                'event_date': event_date,
                'error': str(e)
            })
            if verbose:
                print(f"  Failed: {user_id} @ {event_date}: {e}")
    
    if verbose:
        print(f"\nCompleted: {len(results)}/{total} events")
        if failed:
            print(f"Failed: {len(failed)} events")
    
    summary_df = pd.DataFrame(results)
    flags_df = pd.DataFrame(all_flags)
    drivers_df = pd.DataFrame(all_drivers)
    
    return {
        'summary_df': summary_df,
        'flags_df': flags_df,
        'drivers_df': drivers_df,
        'failed': failed,
    }


def export_to_excel(
    batch_results: Dict,
    output_path: str,
    include_stats: bool = True
) -> str:
    """
    Export batch results to Excel workbook with multiple sheets.
    
    Sheets:
        - Summary: One row per event with all metrics
        - Flags: All flags with supporting txn IDs
        - Drivers: Key transactions per event
        - Stats: Aggregate statistics (optional)
        - Failed: Events that failed processing
    """
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        
        # Summary sheet
        summary_df = batch_results['summary_df']
        if len(summary_df) > 0:
            # Sort by high severity count, then flags count
            summary_df = summary_df.sort_values(
                ['high_severity_count', 'flags_count'], 
                ascending=[False, False]
            )
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Flags sheet
        flags_df = batch_results['flags_df']
        if len(flags_df) > 0:
            flags_df.to_excel(writer, sheet_name='Flags', index=False)
        
        # Drivers sheet
        drivers_df = batch_results['drivers_df']
        if len(drivers_df) > 0:
            drivers_df.to_excel(writer, sheet_name='Key_Transactions', index=False)
        
        # Stats sheet
        if include_stats and len(summary_df) > 0:
            stats = compute_batch_stats(batch_results)
            stats_df = pd.DataFrame([stats]).T
            stats_df.columns = ['Value']
            stats_df.to_excel(writer, sheet_name='Stats')
        
        # Failed sheet
        if batch_results['failed']:
            failed_df = pd.DataFrame(batch_results['failed'])
            failed_df.to_excel(writer, sheet_name='Failed', index=False)
    
    return output_path


def compute_batch_stats(batch_results: Dict) -> Dict:
    """Compute aggregate statistics across all events"""
    
    summary_df = batch_results['summary_df']
    flags_df = batch_results['flags_df']
    
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
    if len(flags_df) > 0:
        flag_counts = flags_df['flag_type'].value_counts().to_dict()
        for flag_type, count in flag_counts.items():
            stats[f'flag_{flag_type}'] = count
    
    return stats


def prioritize_events(
    batch_results: Dict,
    weights: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Score and prioritize events for L2 review.
    
    Returns summary_df with added 'priority_score' column, sorted by priority.
    """
    
    if weights is None:
        weights = {
            'high_severity_count': 30,
            'flags_count': 10,
            'txn_size_ratio': 5,
            'velocity_ratio': 5,
            'new_cp_volume_share': 20,
            'top3_concentration': 10,
            'credit_shift_abs': 15,
            'volume_event': 0.00001,  # Small weight for volume
        }
    
    df = batch_results['summary_df'].copy()
    
    if len(df) == 0:
        return df
    
    # Normalize metrics to 0-1 range
    def safe_normalize(series):
        series = series.replace([np.inf, -np.inf], np.nan)
        min_val = series.min()
        max_val = series.max()
        if max_val == min_val:
            return pd.Series(0.5, index=series.index)
        return (series - min_val) / (max_val - min_val)
    
    df['credit_shift_abs'] = df['credit_shift'].abs()
    
    # Calculate priority score
    df['priority_score'] = 0
    
    for metric, weight in weights.items():
        if metric in df.columns:
            normalized = safe_normalize(df[metric].fillna(0))
            df['priority_score'] += normalized * weight
    
    # Sort by priority
    df = df.sort_values('priority_score', ascending=False)
    
    # Add rank
    df['priority_rank'] = range(1, len(df) + 1)
    
    return df


def generate_l2_queue(
    batch_results: Dict,
    output_path: str,
    top_n: Optional[int] = None,
    weights: Optional[Dict] = None
) -> str:
    """
    Generate prioritized L2 review queue as Excel file.
    
    Args:
        batch_results: Output from run_batch_characterization
        output_path: Where to save Excel file
        top_n: Limit to top N priority events (None = all)
        weights: Priority scoring weights
    
    Returns:
        Path to output file
    """
    
    prioritized = prioritize_events(batch_results, weights)
    
    if top_n:
        prioritized = prioritized.head(top_n)
    
    # Filter flags and drivers to only prioritized events
    priority_events = set(zip(prioritized['user_id'], prioritized['event_date'].astype(str)))
    
    flags_df = batch_results['flags_df'].copy()
    if len(flags_df) > 0:
        flags_df['event_key'] = list(zip(flags_df['user_id'], flags_df['event_date'].astype(str)))
        flags_df = flags_df[flags_df['event_key'].isin(priority_events)]
        flags_df = flags_df.drop(columns=['event_key'])
    
    drivers_df = batch_results['drivers_df'].copy()
    if len(drivers_df) > 0:
        drivers_df['event_key'] = list(zip(drivers_df['user_id'], drivers_df['event_date'].astype(str)))
        drivers_df = drivers_df[drivers_df['event_key'].isin(priority_events)]
        drivers_df = drivers_df.drop(columns=['event_key'])
    
    # Repackage for export
    prioritized_results = {
        'summary_df': prioritized,
        'flags_df': flags_df,
        'drivers_df': drivers_df,
        'failed': batch_results['failed'],
    }
    
    return export_to_excel(prioritized_results, output_path)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    
    # Example: Load your transactions
    # txns = load_transactions('path/to/your/transactions.csv')
    
    # Example: Create sample data for testing
    np.random.seed(42)
    
    # Generate transactions for multiple users
    users = ['USER_001', 'USER_002', 'USER_003', 'USER_004', 'USER_005']
    all_txns = []
    
    for user in users:
        n_txns = np.random.randint(150, 250)
        user_txns = pd.DataFrame({
            'txn_id': [f'{user}_TXN_{i:04d}' for i in range(n_txns)],
            'user_id': [user] * n_txns,
            'tran_date': pd.date_range('2024-11-01', periods=n_txns, freq='D'),
            'tran_type': np.random.choice(['WIRE', 'ACH', 'CHECK', 'INTERNAL'], n_txns),
            'amount': np.concatenate([
                np.random.uniform(100, 5000, n_txns - 50),
                np.random.uniform(5000, 50000, 50)
            ]),
            'counterparty_id': np.concatenate([
                np.random.choice([f'{user}_CP_00{i}' for i in range(1, 6)], n_txns - 50),
                np.random.choice([f'{user}_CP_NEW_{i}' for i in range(1, 4)], 50)
            ]),
            'is_credit': np.concatenate([
                np.random.choice([True, False], n_txns - 50, p=[0.5, 0.5]),
                np.random.choice([True, False], 50, p=[0.8, 0.2])
            ])
        })
        all_txns.append(user_txns)
    
    sample_txns = pd.concat(all_txns, ignore_index=True)
    
    # Define events to analyze (from your spike detection)
    events = pd.DataFrame({
        'user_id': users,
        'event_date': ['2025-05-15', '2025-05-10', '2025-05-20', '2025-05-12', '2025-05-18'],
        'risk_tier': ['HIGH', 'MEDIUM', 'HIGH', 'MEDIUM', 'HIGH']
    })
    
    print("=" * 60)
    print("RUNNING BATCH CHARACTERIZATION")
    print("=" * 60)
    
    # Run batch
    batch_results = run_batch_characterization(
        txns=sample_txns,
        events=events,
        lookback_days=30,
        baseline_days=90,
        verbose=True
    )
    
    # Show summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)
    print(f"\nEvents processed: {len(batch_results['summary_df'])}")
    print(f"Total flags raised: {len(batch_results['flags_df'])}")
    
    # Prioritize
    prioritized = prioritize_events(batch_results)
    print("\n" + "-" * 60)
    print("PRIORITIZED QUEUE (Top 5)")
    print("-" * 60)
    print(prioritized[['user_id', 'event_date', 'priority_score', 'priority_rank', 
                       'flags_count', 'high_severity_count']].head().to_string(index=False))
    
    # Export to Excel
    output_path = 'l2_review_queue.xlsx'
    generate_l2_queue(batch_results, output_path)
    print(f"\nExported L2 queue to: {output_path}")
    
    # Show stats
    print("\n" + "-" * 60)
    print("AGGREGATE STATS")
    print("-" * 60)
    stats = compute_batch_stats(batch_results)
    for key, val in stats.items():
        if isinstance(val, float):
            print(f"  {key}: {val:.2f}")
        else:
            print(f"  {key}: {val}")