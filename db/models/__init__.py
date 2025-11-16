"""Pydantic models for data representation."""

from db.models.customer import (
    CustomerBasic,
    CustomerTransactionFeatures,
    CustomerRiskFeatures,
    CustomerBehavioralFeatures,
    CustomerNetworkFeatures,
    CustomerKnowledgeGraphFeatures,
    CustomerFull,
    CustomerCreate,
    CustomerUpdate,
)
from db.models.transaction import (
    TransactionModel,
    TransactionCreate,
)
from db.models.alert import (
    AlertModel,
    AlertCreate,
    AlertUpdate,
)
from db.models.report import (
    ReportModel,
    ReportCreate,
    ReportUpdate,
)

__all__ = [
    # Customer models
    "CustomerBasic",
    "CustomerTransactionFeatures",
    "CustomerRiskFeatures",
    "CustomerBehavioralFeatures",
    "CustomerNetworkFeatures",
    "CustomerKnowledgeGraphFeatures",
    "CustomerFull",
    "CustomerCreate",
    "CustomerUpdate",
    # Transaction models
    "TransactionModel",
    "TransactionCreate",
    # Alert models
    "AlertModel",
    "AlertCreate",
    "AlertUpdate",
    # Report models
    "ReportModel",
    "ReportCreate",
    "ReportUpdate",
]
