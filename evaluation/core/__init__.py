"""Core evaluation framework for AML Copilot.

This module provides a unified, modular framework for testing the AML Copilot
multi-agent system across different test types (Golden/Business, Conversation, System).
"""

from evaluation.core.models import (
    # Test Registry
    TestTypeConfig,
    TestRegistry,
    # Base Models
    BaseTestCase,
    BaseTestResult,
    # Golden Test Models
    GoldenTestCase,
    GoldenTestResult,
    # Conversation Test Models
    ConversationTestCase,
    ConversationTestResult,
    ConversationTurn,
    TurnResult,
    # System Test Models
    SystemTestCase,
    SystemTestResult,
    # Reports
    UnifiedEvaluationReport,
)

__all__ = [
    # Test Registry
    "TestTypeConfig",
    "TestRegistry",
    # Base Models
    "BaseTestCase",
    "BaseTestResult",
    # Golden Test Models
    "GoldenTestCase",
    "GoldenTestResult",
    # Conversation Test Models
    "ConversationTestCase",
    "ConversationTestResult",
    "ConversationTurn",
    "TurnResult",
    # System Test Models
    "SystemTestCase",
    "SystemTestResult",
    # Reports
    "UnifiedEvaluationReport",
]
