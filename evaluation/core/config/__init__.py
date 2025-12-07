"""Configuration models and loaders for evaluation framework.

Provides centralized YAML-based configuration with:
- Two-level weighting system (test types + evaluators)
- Automatic validation (weights sum to 1.0)
- Type-safe enums (prevents typos)
- Auto-loading from paths or inline config
"""

from evaluation.core.config.models import (
    EvaluatorType,
    EvaluatorConfig,
    TestTypeEvaluationConfig,
    EvaluationConfig,
)
from evaluation.core.config.loader import (
    load_evaluation_config,
    get_default_config,
    load_evaluator_config,
)

__all__ = [
    "EvaluatorType",
    "EvaluatorConfig",
    "TestTypeEvaluationConfig",
    "EvaluationConfig",
    "load_evaluation_config",
    "get_default_config",
    "load_evaluator_config",
]
