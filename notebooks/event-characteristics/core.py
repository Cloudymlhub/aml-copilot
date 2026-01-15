"""
Core utilities: EventWindow, data loading, window splitting
"""

import pandas as pd
from dataclasses import dataclass
from typing import Tuple, Dict, Optional


# =============================================================================
# COLUMN SCHEMA
# =============================================================================

# Required columns - these must be present (or mapped)
REQUIRED_COLUMNS = [
    'txn_id',           # Transaction identifier
    'user_id',          # Account/customer identifier
    'tran_date',        # Transaction date
    'amount',           # Transaction amount
    'counterparty_id',  # Counterparty identifier (internal ID or external)
    'is_credit',        # Boolean: True = credit (inflow), False = debit (outflow)
]

# Optional columns - used if present
OPTIONAL_COLUMNS = [
    'tran_type',            # Transaction type (WIRE, ACH, CHECK, INTERNAL, etc.)
    'counterparty_account', # External bank account (when not internal)
]

# Example mapping from your source columns to standard names
EXAMPLE_COLUMN_MAPPING = {
    # 'YOUR_COLUMN_NAME': 'standard_name'
    # 'TRANSACTION_ID': 'txn_id',
    # 'CUSTOMER_ID': 'user_id',
    # 'TXN_DATE': 'tran_date',
    # 'TXN_TYPE': 'tran_type',
    # 'TXN_AMOUNT': 'amount',
    # 'CPTY_ID': 'counterparty_id',
    # 'CPTY_ACCOUNT': 'counterparty_account',
    # 'CREDIT_DEBIT_FLAG': 'is_credit',  # Will be converted to boolean
}


# =============================================================================
# EVENT WINDOW
# =============================================================================

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


# =============================================================================
# DATA LOADING
# =============================================================================

def apply_column_mapping(df: pd.DataFrame, column_mapping: Dict[str, str]) -> pd.DataFrame:
    """
    Apply column mapping and validate required columns exist.
    
    Args:
        df: Source DataFrame
        column_mapping: Dict mapping source columns to standard names
    
    Returns:
        DataFrame with standardized column names
    """
    df = df.copy()
    
    # Apply mapping
    if column_mapping:
        df = df.rename(columns=column_mapping)
    
    # Check required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after mapping: {missing}")
    
    return df


def standardize_types(df: pd.DataFrame, credit_values: Optional[list] = None) -> pd.DataFrame:
    """
    Standardize column types.
    
    Args:
        df: DataFrame with standard column names
        credit_values: Values in is_credit column that indicate credit (default: common patterns)
    
    Returns:
        DataFrame with standardized types
    """
    df = df.copy()
    
    # Date parsing
    df['tran_date'] = pd.to_datetime(df['tran_date'])
    
    # is_credit to boolean
    if df['is_credit'].dtype == 'object' or df['is_credit'].dtype.name == 'category':
        if credit_values is None:
            credit_values = ['CREDIT', 'C', 'CR', 'TRUE', '1', 'Y', 'YES']
        df['is_credit'] = df['is_credit'].astype(str).str.upper().isin(credit_values)
    elif df['is_credit'].dtype in ['int64', 'float64']:
        df['is_credit'] = df['is_credit'].astype(bool)
    
    # Amount to float
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').abs()
    
    return df


def load_transactions(
    filepath: str,
    column_mapping: Optional[Dict[str, str]] = None,
    credit_values: Optional[list] = None
) -> pd.DataFrame:
    """
    Load transaction CSV, apply mapping, and standardize types.
    
    Args:
        filepath: Path to CSV file
        column_mapping: Dict mapping your columns to standard names
        credit_values: Values that indicate credit transactions
    
    Returns:
        Standardized DataFrame ready for analysis
    
    Example:
        txns = load_transactions(
            'transactions.csv',
            column_mapping={
                'TRANSACTION_ID': 'txn_id',
                'CUSTOMER_ID': 'user_id',
                'TXN_DATE': 'tran_date',
                'TXN_TYPE': 'tran_type',
                'TXN_AMOUNT': 'amount',
                'CPTY_ID': 'counterparty_id',
                'CPTY_ACCOUNT': 'counterparty_account',
                'DR_CR_FLAG': 'is_credit',
            },
            credit_values=['CR', 'CREDIT']
        )
    """
    df = pd.read_csv(filepath)
    df = apply_column_mapping(df, column_mapping)
    df = standardize_types(df, credit_values)
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