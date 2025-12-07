"""Evaluator registry for pluggable evaluation.

Provides centralized, stateless management of evaluator instances.
Configuration (weights, thresholds, test type assignments) is handled by EvaluationConfig.
"""

from typing import List, Dict, Any, Optional

# Import existing evaluators
from evaluation.core.evaluators.correctness_evaluator import CorrectnessEvaluator
from evaluation.core.evaluators.completeness_evaluator import CompletenessEvaluator
from evaluation.core.evaluators.hallucination_detector import HallucinationDetector


class EvaluatorRegistry:
    """Central registry for pluggable evaluators (stateless).

    This registry is a simple lookup table for evaluator instances.
    It does NOT manage configuration (weights, thresholds, test type assignments).
    Configuration is managed by EvaluationConfig loaded from YAML.

    Design:
    - Registry: Stateless evaluator instances
    - EvaluationConfig: Weights, thresholds, test type assignments
    - UnifiedTestRunner: Orchestrates strategy pattern (inject evaluator + config)

    Example:
        >>> registry = EvaluatorRegistry()
        >>> evaluator = registry.get_evaluator("correctness")
        >>> config = {...}  # Loaded from YAML
        >>> result = evaluator.evaluate(agent_output, expected_output, config)
    """

    def __init__(self):
        """Initialize registry with default evaluator instances.

        Evaluators are stateless - they receive configuration at evaluation time
        via the strategy pattern, not in __init__.
        """
        self._evaluators: Dict[str, Any] = {
            "correctness": CorrectnessEvaluator(),
            "completeness": CompletenessEvaluator(),
            "hallucination": HallucinationDetector(),
        }

    def get_evaluator(self, name: str) -> Optional[Any]:
        """Get a specific evaluator by name.

        Args:
            name: Name of evaluator

        Returns:
            Evaluator instance or None if not found

        Example:
            >>> registry = EvaluatorRegistry()
            >>> evaluator = registry.get_evaluator("correctness")
            >>> evaluator.evaluate(agent_output, expected, config)
        """
        return self._evaluators.get(name)

    def register(self, name: str, evaluator: Any):
        """Register a custom evaluator.

        Args:
            name: Unique name for the evaluator
            evaluator: Evaluator instance (should be stateless)

        Example:
            >>> from my_evaluators import CustomEvaluator
            >>> registry = EvaluatorRegistry()
            >>> registry.register("custom", CustomEvaluator())
        """
        self._evaluators[name] = evaluator

    def list_evaluators(self) -> List[str]:
        """List all registered evaluator names.

        Returns:
            List of evaluator names

        Example:
            >>> registry = EvaluatorRegistry()
            >>> registry.list_evaluators()
            ['correctness', 'completeness', 'hallucination']
        """
        return list(self._evaluators.keys())
