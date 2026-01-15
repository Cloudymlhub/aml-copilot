"""
Drivers: Extract evidence that explains behavioral shifts.

Each driver is a function with signature:
    def driver_name(event, baseline, shifts, **params) -> pd.DataFrame

DRIVERS dict maps names to functions for easy lookup/iteration.
"""

import pandas as pd
from typing import Dict, List, Optional


# =============================================================================
# TRANSACTION DRIVERS
# =============================================================================

def largest_transactions(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    top_n: int = 5
) -> pd.DataFrame:
    """Top N transactions by amount in event window"""
    
    if len(event) == 0:
        return pd.DataFrame()
    
    cols = ['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id', 'is_credit']
    cols = [c for c in cols if c in event.columns]
    
    return event.nlargest(top_n, 'amount')[cols].copy()


def top_credits(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    top_n: int = 5
) -> pd.DataFrame:
    """Top N credit transactions by amount"""
    
    if len(event) == 0:
        return pd.DataFrame()
    
    credits = event[event['is_credit'] == True]
    
    if len(credits) == 0:
        return pd.DataFrame()
    
    cols = ['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id']
    cols = [c for c in cols if c in credits.columns]
    
    return credits.nlargest(top_n, 'amount')[cols].copy()


def top_debits(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    top_n: int = 5
) -> pd.DataFrame:
    """Top N debit transactions by amount"""
    
    if len(event) == 0:
        return pd.DataFrame()
    
    debits = event[event['is_credit'] == False]
    
    if len(debits) == 0:
        return pd.DataFrame()
    
    cols = ['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id']
    cols = [c for c in cols if c in debits.columns]
    
    return debits.nlargest(top_n, 'amount')[cols].copy()


def new_counterparty_transactions(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    top_n: int = 5
) -> pd.DataFrame:
    """Top transactions with counterparties not seen in baseline"""
    
    new_cps = shifts.get('new_counterparty_ids', set())
    
    if len(event) == 0 or not new_cps:
        return pd.DataFrame()
    
    new_cp_txns = event[event['counterparty_id'].isin(new_cps)]
    
    if len(new_cp_txns) == 0:
        return pd.DataFrame()
    
    cols = ['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id', 'is_credit']
    cols = [c for c in cols if c in new_cp_txns.columns]
    
    return new_cp_txns.nlargest(top_n, 'amount')[cols].copy()


# =============================================================================
# COUNTERPARTY DRIVERS
# =============================================================================

def counterparty_breakdown(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    id_col: str = 'counterparty_id',
    account_col: str = 'counterparty_account',
) -> pd.DataFrame:
    """
    Volume breakdown per counterparty: credits, debits, net flow.
    
    Handles both:
    - Internal transactions: uses counterparty_id
    - External transactions: uses counterparty_account
    """
    
    if len(event) == 0:
        return pd.DataFrame()
    
    event = event.copy()
    
    # Create unified counterparty identifier
    # Use account if available, otherwise use id (internal)
    if account_col in event.columns:
        event['_cp_key'] = event[account_col].fillna('')
        has_id = id_col in event.columns
        if has_id:
            # Where account is empty, use id
            mask = event['_cp_key'] == ''
            event.loc[mask, '_cp_key'] = event.loc[mask, id_col].fillna('UNKNOWN')
            # Flag internal transactions
            event['is_internal'] = event[account_col].isna() | (event[account_col] == '')
        else:
            event['is_internal'] = False
    elif id_col in event.columns:
        event['_cp_key'] = event[id_col].fillna('UNKNOWN')
        event['is_internal'] = True
    else:
        return pd.DataFrame()
    
    # Get baseline counterparties for is_new flag
    baseline_cps = set()
    if len(baseline) > 0:
        baseline = baseline.copy()
        if account_col in baseline.columns:
            baseline['_cp_key'] = baseline[account_col].fillna('')
            if id_col in baseline.columns:
                mask = baseline['_cp_key'] == ''
                baseline.loc[mask, '_cp_key'] = baseline.loc[mask, id_col].fillna('UNKNOWN')
        elif id_col in baseline.columns:
            baseline['_cp_key'] = baseline[id_col].fillna('UNKNOWN')
        baseline_cps = set(baseline['_cp_key'].unique())
    
    # Aggregate by unified key and direction
    cp_summary = event.groupby(['_cp_key', 'is_credit']).agg(
        total_amount=('amount', 'sum'),
        txn_count=('txn_id', 'count'),
    ).reset_index()
    
    # Pivot credits/debits
    cp_credits = cp_summary[cp_summary['is_credit'] == True].copy()
    cp_credits = cp_credits.rename(columns={
        'total_amount': 'credit_amount',
        'txn_count': 'credit_count'
    })[['_cp_key', 'credit_amount', 'credit_count']]
    
    cp_debits = cp_summary[cp_summary['is_credit'] == False].copy()
    cp_debits = cp_debits.rename(columns={
        'total_amount': 'debit_amount',
        'txn_count': 'debit_count'
    })[['_cp_key', 'debit_amount', 'debit_count']]
    
    # Merge
    cp_breakdown = pd.merge(cp_credits, cp_debits, on='_cp_key', how='outer').fillna(0)
    
    # Calculate derived metrics
    cp_breakdown['net_flow'] = cp_breakdown['credit_amount'] - cp_breakdown['debit_amount']
    cp_breakdown['total_volume'] = cp_breakdown['credit_amount'] + cp_breakdown['debit_amount']
    cp_breakdown['total_txns'] = (cp_breakdown['credit_count'] + cp_breakdown['debit_count']).astype(int)
    
    # Flag new counterparties
    cp_breakdown['is_new'] = ~cp_breakdown['_cp_key'].isin(baseline_cps)
    
    # Flag internal (get from first occurrence in event)
    internal_map = event.groupby('_cp_key')['is_internal'].first()
    cp_breakdown['is_internal'] = cp_breakdown['_cp_key'].map(internal_map)
    
    # Create display column
    cp_breakdown['display_id'] = cp_breakdown.apply(
        lambda r: f"[INTERNAL] {r['_cp_key']}" if r['is_internal'] else r['_cp_key'],
        axis=1
    )
    
    # Sort by total volume
    cp_breakdown = cp_breakdown.sort_values('total_volume', ascending=False)
    
    # Rename and reorder columns
    cp_breakdown = cp_breakdown.rename(columns={'_cp_key': 'counterparty'})
    
    cols = [
        'display_id', 'counterparty', 'is_new', 'is_internal',
        'credit_amount', 'credit_count',
        'debit_amount', 'debit_count',
        'net_flow', 'total_volume', 'total_txns'
    ]
    cols = [c for c in cols if c in cp_breakdown.columns]
    
    return cp_breakdown[cols]


def top_counterparty_transactions(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    top_n_cp: int = 3,
    top_n_txns: int = 5
) -> pd.DataFrame:
    """Transactions with the top N counterparties by volume"""
    
    if len(event) == 0:
        return pd.DataFrame()
    
    top_cps = event.groupby('counterparty_id')['amount'].sum().nlargest(top_n_cp).index.tolist()
    
    subset = event[event['counterparty_id'].isin(top_cps)]
    
    if len(subset) == 0:
        return pd.DataFrame()
    
    cols = ['txn_id', 'tran_date', 'amount', 'tran_type', 'counterparty_id', 'is_credit']
    cols = [c for c in cols if c in subset.columns]
    
    return subset.nlargest(top_n_txns, 'amount')[cols].copy()


# =============================================================================
# DRIVER REGISTRY
# =============================================================================

DRIVERS = {
    'largest_transactions': largest_transactions,
    'top_credits': top_credits,
    'top_debits': top_debits,
    'new_counterparty_transactions': new_counterparty_transactions,
    'counterparty_breakdown': counterparty_breakdown,
    'top_counterparty_transactions': top_counterparty_transactions,
}


def run_drivers(
    event: pd.DataFrame,
    baseline: pd.DataFrame,
    shifts: Dict,
    drivers: Optional[List[str]] = None,
    params: Optional[Dict[str, Dict]] = None
) -> Dict[str, pd.DataFrame]:
    """
    Run multiple drivers and collect results.
    
    Args:
        event: Event window transactions
        baseline: Baseline window transactions
        shifts: Pre-computed shift metrics
        drivers: List of driver names to run (None = all)
        params: Per-driver parameters, e.g. {'largest_transactions': {'top_n': 10}}
    
    Returns:
        Dict mapping driver name to result DataFrame
    """
    
    if drivers is None:
        drivers = list(DRIVERS.keys())
    
    if params is None:
        params = {}
    
    results = {}
    
    for name in drivers:
        if name not in DRIVERS:
            print(f"Warning: Unknown driver '{name}', skipping")
            continue
        
        driver_fn = DRIVERS[name]
        driver_params = params.get(name, {})
        
        try:
            results[name] = driver_fn(event, baseline, shifts, **driver_params)
        except Exception as e:
            print(f"Warning: Driver '{name}' failed: {e}")
            results[name] = pd.DataFrame()
    
    return results