"""
Behavioral shift calculations: baseline vs event metrics
"""

import pandas as pd
import numpy as np
from scipy.stats import entropy
from typing import Dict

from .core import EventWindow


def _top_n_share(df: pd.DataFrame, n: int = 3) -> float:
    """Calculate share of volume from top N counterparties"""
    if len(df) == 0 or df['amount'].sum() == 0:
        return 0.0
    
    top_volume = df.groupby('counterparty_id')['amount'].sum().nlargest(n).sum()
    return top_volume / df['amount'].sum()


def _type_entropy(df: pd.DataFrame) -> float:
    """Calculate entropy of transaction type distribution"""
    if len(df) == 0:
        return 0.0
    
    type_counts = df['tran_type'].value_counts(normalize=True)
    return entropy(type_counts)


def _get_new_counterparties(baseline: pd.DataFrame, event: pd.DataFrame) -> set:
    """Identify counterparties in event window not seen in baseline"""
    baseline_cps = set(baseline['counterparty_id'].unique())
    event_cps = set(event['counterparty_id'].unique())
    return event_cps - baseline_cps


def compute_shifts(baseline: pd.DataFrame, event: pd.DataFrame, window: EventWindow) -> Dict:
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
        baseline_top3_share = _top_n_share(baseline, 3)
        baseline_entropy = _type_entropy(baseline)
    
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
        event_top3_share = _top_n_share(event, 3)
        event_entropy = _type_entropy(event)
    
    # New counterparty analysis
    new_cps = _get_new_counterparties(baseline, event)
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