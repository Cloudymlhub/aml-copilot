"""Transaction data models."""

from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class TransactionModel(BaseModel):
    """Transaction record with counterparty and risk indicators."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    transaction_id: str
    customer_id: int

    # Transaction details
    amount: Decimal
    currency: str
    transaction_date: datetime
    transaction_type: Optional[str]
    channel: Optional[str]

    # Counterparty information
    counterparty_name: Optional[str]
    counterparty_account: Optional[str]
    counterparty_country: Optional[str]
    counterparty_bank: Optional[str]

    # Risk indicators
    is_cash_transaction: bool
    is_round_amount: bool
    is_high_risk_country: bool
    is_structured: bool
    is_international: bool

    # Metadata
    description: Optional[str]
    created_at: Optional[datetime]


class TransactionCreate(BaseModel):
    """Model for creating a new transaction."""

    transaction_id: str
    customer_id: int
    amount: Decimal
    currency: str = "USD"
    transaction_date: datetime
    transaction_type: Optional[str] = None
    channel: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_country: Optional[str] = None
    description: Optional[str] = None
