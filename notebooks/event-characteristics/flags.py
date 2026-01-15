"""
Flag generation: Generate alerts based on shift thresholds.
"""

import pandas as pd
from typing import Dict, List, Optional


DEFAULT_THRESHOLDS = {
    'txn_size_ratio': 1.5,
    'velocity_ratio': 2.0,
    'credit_shift': 0.15,
    'new_cp_volume_share': 0.3,
    'top3_share_event': 0.7,
    'concentration_shift': 0.15,
    'entropy_shift': -0.3,
}


def generate_flags(
    shifts: Dict,
    drivers: Dict[str, pd.DataFrame],
    thresholds: Optional[Dict] = None
) -> List[Dict]:
    """
    Generate human-readable flags with supporting transaction IDs.
    
    Args:
        shifts: Behavioral shift metrics
        drivers: Driver results (for extracting supporting txn IDs)
        thresholds: Custom thresholds (uses DEFAULT_THRESHOLDS if not provided)
    
    Returns:
        List of flag dicts with: flag_type, description, severity, supporting_txns
    """
    
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS.copy()
    
    flags = []
    
    # Helper to get txn IDs from a driver result
    def get_txn_ids(driver_name: str, n: int = 5) -> List[str]:
        df = drivers.get(driver_name, pd.DataFrame())
        if len(df) == 0 or 'txn_id' not in df.columns:
            return []
        return df['txn_id'].head(n).tolist()
    
    # Transaction size increase
    if shifts['txn_size_ratio'] > thresholds['txn_size_ratio']:
        flags.append({
            'flag_type': 'TRANSACTION_SIZE_INCREASE',
            'description': f"Transaction sizes {shifts['txn_size_ratio']:.1f}x baseline average "
                          f"(${shifts['avg_txn_size_event']:,.0f} vs ${shifts['avg_txn_size_baseline']:,.0f})",
            'severity': 'HIGH' if shifts['txn_size_ratio'] > 3 else 'MEDIUM',
            'supporting_txns': get_txn_ids('largest_transactions')
        })
    
    # Velocity increase
    if shifts['velocity_ratio'] > thresholds['velocity_ratio']:
        flags.append({
            'flag_type': 'VELOCITY_INCREASE',
            'description': f"Transaction frequency {shifts['velocity_ratio']:.1f}x baseline "
                          f"({shifts['txns_per_day_event']:.1f}/day vs {shifts['txns_per_day_baseline']:.1f}/day)",
            'severity': 'HIGH' if shifts['velocity_ratio'] > 4 else 'MEDIUM',
            'supporting_txns': get_txn_ids('largest_transactions')
        })
    
    # Credit shift (inflows)
    if shifts['credit_shift'] > thresholds['credit_shift']:
        flags.append({
            'flag_type': 'CREDIT_HEAVY',
            'description': f"Credit-heavy activity: {shifts['credit_ratio_event']:.0%} credits vs "
                          f"{shifts['credit_ratio_baseline']:.0%} baseline (+{shifts['credit_shift']:.0%} shift)",
            'severity': 'HIGH' if shifts['credit_shift'] > 0.3 else 'MEDIUM',
            'supporting_txns': get_txn_ids('top_credits')
        })
    
    # Debit shift (outflows)
    if shifts['credit_shift'] < -thresholds['credit_shift']:
        flags.append({
            'flag_type': 'DEBIT_HEAVY',
            'description': f"Debit-heavy activity: {1-shifts['credit_ratio_event']:.0%} debits vs "
                          f"{1-shifts['credit_ratio_baseline']:.0%} baseline",
            'severity': 'HIGH' if shifts['credit_shift'] < -0.3 else 'MEDIUM',
            'supporting_txns': get_txn_ids('top_debits')
        })
    
    # New counterparties
    if shifts['new_counterparty_volume_share'] > thresholds['new_cp_volume_share']:
        flags.append({
            'flag_type': 'NEW_COUNTERPARTY_VOLUME',
            'description': f"{shifts['new_counterparty_volume_share']:.0%} of volume to "
                          f"{shifts['new_counterparty_count']} NEW counterparties",
            'severity': 'HIGH' if shifts['new_counterparty_volume_share'] > 0.5 else 'MEDIUM',
            'supporting_txns': get_txn_ids('new_counterparty_transactions')
        })
    
    # Concentration
    if shifts['top3_share_event'] > thresholds['top3_share_event']:
        flags.append({
            'flag_type': 'COUNTERPARTY_CONCENTRATION',
            'description': f"Concentrated activity: top 3 counterparties = {shifts['top3_share_event']:.0%} of volume "
                          f"(vs {shifts['top3_share_baseline']:.0%} baseline)",
            'severity': 'HIGH' if shifts['top3_share_event'] > 0.85 else 'MEDIUM',
            'supporting_txns': get_txn_ids('top_counterparty_transactions')
        })
    
    # Entropy decrease (less diverse transaction types)
    if shifts['entropy_shift'] < thresholds['entropy_shift']:
        flags.append({
            'flag_type': 'REDUCED_DIVERSITY',
            'description': f"Less varied transaction types (entropy: {shifts['type_entropy_event']:.2f} vs "
                          f"{shifts['type_entropy_baseline']:.2f} baseline)",
            'severity': 'MEDIUM',
            'supporting_txns': get_txn_ids('largest_transactions')
        })
    
    return flags