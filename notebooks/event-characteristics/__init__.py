"""
AML Event Characterization Package

Main entry points:
- characterize_event(): Analyze a single event
- run_batch(): Analyze multiple events
- generate_l2_queue(): Create prioritized Excel output
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from .core import (
    EventWindow, 
    load_transactions, 
    split_windows,
    apply_column_mapping,
    standardize_types,
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    EXAMPLE_COLUMN_MAPPING,
)
from .shifts import compute_shifts
from .drivers import DRIVERS, run_drivers
from .flags import generate_flags, DEFAULT_THRESHOLDS
from .reports import format_text_report, format_hover_text, export_to_excel


# =============================================================================
# SINGLE EVENT
# =============================================================================

def characterize_event(
    txns: pd.DataFrame,
    user_id: str,
    event_date: str,
    lookback_days: int = 30,
    baseline_days: int = 90,
    drivers: Optional[List[str]] = None,
    driver_params: Optional[Dict] = None,
    thresholds: Optional[Dict] = None,
    column_mapping: Optional[Dict[str, str]] = None,
    credit_values: Optional[List[str]] = None,
) -> Dict:
    """
    Characterize a single event for a user.
    
    Args:
        txns: Transaction DataFrame
        user_id: User to analyze
        event_date: Date of detected event/spike
        lookback_days: Days before event_date for event window
        baseline_days: Days before event window for baseline
        drivers: List of driver names to run (None = all)
        driver_params: Per-driver parameters
        thresholds: Flag thresholds
        column_mapping: Dict mapping your columns to standard names
        credit_values: Values in is_credit column that indicate credit
    
    Returns:
        Dict with: window, shifts, drivers, flags, report, baseline_txns, event_txns
    """
    
    # Apply column mapping if provided
    if column_mapping:
        txns = apply_column_mapping(txns, column_mapping)
        txns = standardize_types(txns, credit_values)
    
    window = EventWindow.from_dates(user_id, event_date, lookback_days, baseline_days)
    baseline, event = split_windows(txns, window)
    
    shifts = compute_shifts(baseline, event, window)
    driver_results = run_drivers(event, baseline, shifts, drivers, driver_params)
    flags = generate_flags(shifts, driver_results, thresholds)
    report = format_text_report(window, shifts, flags, driver_results)
    
    return {
        'window': window,
        'shifts': shifts,
        'drivers': driver_results,
        'flags': flags,
        'report': report,
        'baseline_txns': baseline,
        'event_txns': event,
    }


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def run_batch(
    txns: pd.DataFrame,
    events: pd.DataFrame,
    lookback_days: int = 30,
    baseline_days: int = 90,
    drivers: Optional[List[str]] = None,
    driver_params: Optional[Dict] = None,
    thresholds: Optional[Dict] = None,
    column_mapping: Optional[Dict[str, str]] = None,
    credit_values: Optional[List[str]] = None,
    verbose: bool = True
) -> Dict:
    """
    Run characterization for multiple events.
    
    Args:
        txns: Transaction DataFrame
        events: DataFrame with ['user_id', 'event_date'], optional ['risk_tier']
        lookback_days: Default lookback
        baseline_days: Default baseline
        drivers: Drivers to run
        driver_params: Per-driver params
        thresholds: Flag thresholds
        column_mapping: Dict mapping your columns to standard names
        credit_values: Values in is_credit column that indicate credit
        verbose: Print progress
    
    Returns:
        Dict with: summary_df, flags_df, drivers_df, counterparty_df, failed
    """
    
    # Apply column mapping once upfront
    if column_mapping:
        txns = apply_column_mapping(txns, column_mapping)
        txns = standardize_types(txns, credit_values)
    
    results = []
    all_flags = []
    all_drivers = []
    all_counterparties = []
    failed = []
    
    total = len(events)
    
    for idx, row in events.iterrows():
        user_id = row['user_id']
        event_date = row['event_date']
        risk_tier = row.get('risk_tier', None)
        
        if verbose and (idx + 1) % 10 == 0:
            print(f"Processing {idx + 1}/{total}...")
        
        try:
            result = characterize_event(
                txns=txns,
                user_id=user_id,
                event_date=event_date,
                lookback_days=lookback_days,
                baseline_days=baseline_days,
                drivers=drivers,
                driver_params=driver_params,
                thresholds=thresholds
            )
            
            # Summary row
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
            
            # Flatten flags
            for flag in result['flags']:
                all_flags.append({
                    'user_id': user_id,
                    'event_date': event_date,
                    'risk_tier': risk_tier,
                    'flag_type': flag['flag_type'],
                    'severity': flag['severity'],
                    'description': flag['description'],
                    'supporting_txn_ids': ', '.join(map(str, flag['supporting_txns'][:10])),
                })
            
            # Flatten transaction drivers
            for driver_name, driver_df in result['drivers'].items():
                if driver_name == 'counterparty_breakdown':
                    continue
                if len(driver_df) > 0 and 'txn_id' in driver_df.columns:
                    for _, txn_row in driver_df.head(5).iterrows():
                        all_drivers.append({
                            'user_id': user_id,
                            'event_date': event_date,
                            'driver_type': driver_name,
                            'txn_id': txn_row.get('txn_id'),
                            'tran_date': txn_row.get('tran_date'),
                            'amount': txn_row.get('amount'),
                            'tran_type': txn_row.get('tran_type'),
                            'counterparty_id': txn_row.get('counterparty_id'),
                            'is_credit': txn_row.get('is_credit'),
                        })
            
            # Flatten counterparty breakdown
            if 'counterparty_breakdown' in result['drivers']:
                cp_df = result['drivers']['counterparty_breakdown'].copy()
                cp_df['user_id'] = user_id
                cp_df['event_date'] = event_date
                all_counterparties.append(cp_df)
                
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
    
    return {
        'summary_df': pd.DataFrame(results),
        'flags_df': pd.DataFrame(all_flags),
        'drivers_df': pd.DataFrame(all_drivers),
        'counterparty_df': pd.concat(all_counterparties, ignore_index=True) if all_counterparties else pd.DataFrame(),
        'failed': failed,
    }


def prioritize_events(
    batch_results: Dict,
    weights: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Score and prioritize events for L2 review.
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
            'volume_event': 0.00001,
        }
    
    df = batch_results['summary_df'].copy()
    
    if len(df) == 0:
        return df
    
    def safe_normalize(series):
        series = series.replace([np.inf, -np.inf], np.nan)
        min_val, max_val = series.min(), series.max()
        if max_val == min_val:
            return pd.Series(0.5, index=series.index)
        return (series - min_val) / (max_val - min_val)
    
    df['credit_shift_abs'] = df['credit_shift'].abs()
    df['priority_score'] = 0
    
    for metric, weight in weights.items():
        if metric in df.columns:
            df['priority_score'] += safe_normalize(df[metric].fillna(0)) * weight
    
    df = df.sort_values('priority_score', ascending=False)
    df['priority_rank'] = range(1, len(df) + 1)
    
    return df


def generate_l2_queue(
    batch_results: Dict,
    output_path: str,
    top_n: Optional[int] = None,
    weights: Optional[Dict] = None
) -> str:
    """Generate prioritized L2 review queue as Excel file."""
    
    prioritized = prioritize_events(batch_results, weights)
    
    if top_n:
        prioritized = prioritized.head(top_n)
    
    priority_events = set(zip(prioritized['user_id'], prioritized['event_date'].astype(str)))
    
    def filter_df(df):
        if len(df) == 0:
            return df
        df = df.copy()
        df['_key'] = list(zip(df['user_id'], df['event_date'].astype(str)))
        df = df[df['_key'].isin(priority_events)]
        return df.drop(columns=['_key'])
    
    return export_to_excel({
        'summary_df': prioritized,
        'flags_df': filter_df(batch_results['flags_df']),
        'drivers_df': filter_df(batch_results['drivers_df']),
        'counterparty_df': filter_df(batch_results.get('counterparty_df', pd.DataFrame())),
        'failed': batch_results['failed'],
    }, output_path)


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Column schema
    'REQUIRED_COLUMNS',
    'OPTIONAL_COLUMNS',
    'EXAMPLE_COLUMN_MAPPING',
    
    # Core
    'EventWindow',
    'load_transactions',
    'split_windows',
    'apply_column_mapping',
    'standardize_types',
    
    # Analysis
    'compute_shifts',
    'run_drivers',
    'generate_flags',
    'DRIVERS',
    'DEFAULT_THRESHOLDS',
    
    # Main entry points
    'characterize_event',
    'run_batch',
    'prioritize_events',
    'generate_l2_queue',
    
    # Reports
    'format_text_report',
    'format_hover_text',
    'export_to_excel',
]