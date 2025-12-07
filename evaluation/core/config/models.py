"""Pydantic models for evaluation configuration.

Implements two-level weighting system:
1. Test Type Weights: How much each test type contributes to final score
2. Evaluator Weights: How much each evaluator contributes within its test type

Both levels must sum to 1.0 (validated by Pydantic).
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from pathlib import Path


class EvaluatorType(str, Enum):
    """Enum of available evaluators (prevents typos in YAML).

    Adding new evaluators:
    1. Add enum value here
    2. Register evaluator instance in EvaluatorRegistry
    3. Optionally create evaluator-specific config YAML
    """
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    HALLUCINATION = "hallucination"
    # Future evaluators can be added here


class EvaluatorConfig(BaseModel):
    """Configuration for a single evaluator within a test type.

    Users can provide EITHER:
    - config_path: Reference to external YAML file
    - config: Inline configuration dict

    The Pydantic validator automatically loads config_path into config field,
    so downstream code only needs to check eval_config.config.

    Example YAML (path reference):
        - name: correctness
          weight: 0.40
          threshold: 0.70
          config_path: evaluation/config/evaluators/correctness_config.yaml

    Example YAML (inline):
        - name: completeness
          weight: 0.40
          threshold: 0.75
          config:
            key_facts_weight: 0.50
            recommendations_weight: 0.30
    """
    name: EvaluatorType  # Enum validation prevents typos
    weight: float = Field(..., ge=0, le=1, description="Weight in test type score (0-1)")
    threshold: float = Field(..., ge=0, le=1, description="Minimum passing score (0-1)")

    # User provides EITHER config_path OR config (mutually exclusive)
    config_path: Optional[Path] = Field(None, description="Path to evaluator-specific config YAML")
    config: Optional[Dict[str, Any]] = Field(None, description="Evaluator config (auto-loaded from path)")
    enabled: bool = Field(True, description="Whether evaluator is enabled")

    @validator("config", always=True)
    def load_config_from_path(cls, v, values):
        """Auto-load config from path if config is None.

        This validator enables three patterns:
        1. User specifies config_path in YAML → auto-loads into config field
        2. User specifies inline config in YAML → uses directly
        3. Neither specified → returns empty dict

        Downstream code always accesses eval_config.config (never config_path).

        Raises:
            ValueError: If both config and config_path are specified
        """
        # Check mutual exclusivity
        if v is not None and values.get("config_path") is not None:
            raise ValueError("Cannot specify both 'config' and 'config_path'")

        # Auto-load from path if config is None
        if v is None and values.get("config_path"):
            # Import here to avoid circular dependency
            from evaluation.core.config.loader import load_evaluator_config
            config_path = values["config_path"]
            return load_evaluator_config(config_path)

        return v or {}  # Default to empty dict

    class Config:
        use_enum_values = True  # Serialize enum as string


class TestTypeEvaluationConfig(BaseModel):
    """Evaluation configuration for a specific test type.

    Defines:
    - Test metadata (name, description)
    - Weight in final scorecard (all test type weights must sum to 1.0)
    - List of evaluators with their weights (must sum to 1.0)

    Example:
        golden:
          name: "AML Business Knowledge Tests"
          description: "Single-turn domain expertise tests"
          weight: 0.60  # 60% of final score
          evaluators:
            - name: correctness
              weight: 0.40  # 40% of golden test score
              threshold: 0.70
    """
    test_type: str  # "golden", "conversation", "system"
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Description of this test type")
    weight: float = Field(..., ge=0, le=1, description="Weight in final scorecard (0-1)")
    evaluators: List[EvaluatorConfig]

    @validator("evaluators")
    def evaluator_weights_must_sum_to_one(cls, evaluators):
        """Validate that evaluator weights within this test type sum to 1.0.

        Only checks enabled evaluators. Test types with no evaluators skip validation.

        Raises:
            ValueError: If weights don't sum to 1.0 (±0.001 tolerance)
        """
        if not evaluators:
            return evaluators  # No evaluators = no weight requirement

        enabled_evaluators = [e for e in evaluators if e.enabled]
        if not enabled_evaluators:
            return evaluators  # All disabled = no weight requirement

        total_weight = sum(e.weight for e in enabled_evaluators)
        if abs(total_weight - 1.0) > 0.001:  # Allow small floating point error
            weights_detail = [(e.name, e.weight) for e in enabled_evaluators]
            raise ValueError(
                f"Evaluator weights must sum to 1.0, got {total_weight}. "
                f"Weights: {weights_detail}"
            )
        return evaluators

    class Config:
        use_enum_values = True


class EvaluationConfig(BaseModel):
    """Master evaluation configuration for the entire framework.

    This is the root config loaded from YAML. It defines:
    - All test types with their weights
    - Evaluators for each test type
    - Two-level validation (test type weights + evaluator weights)

    Usage:
        >>> config = EvaluationConfig.from_yaml(Path("evaluation_config.yaml"))
        >>> golden_config = config.get_test_type_config("golden")
        >>> final_score = config.calculate_final_score({
        ...     "golden": 85.0,
        ...     "conversation": 92.0,
        ...     "system": 100.0
        ... })
        >>> print(final_score)
        89.1  # (0.6 * 85) + (0.3 * 92) + (0.1 * 100)
    """
    version: str = Field("1.0", description="Config version for future migration")
    test_types: Dict[str, TestTypeEvaluationConfig]

    @validator("test_types")
    def test_type_weights_must_sum_to_one(cls, test_types):
        """Validate that test type weights sum to 1.0 for final scorecard aggregation.

        This ensures the final score calculation is meaningful:
        final_score = sum(test_type_score * test_type_weight for each test type)

        Raises:
            ValueError: If test type weights don't sum to 1.0 (±0.001 tolerance)
        """
        total_weight = sum(config.weight for config in test_types.values())
        if abs(total_weight - 1.0) > 0.001:  # Allow small floating point error
            weights_detail = [(name, config.weight) for name, config in test_types.items()]
            raise ValueError(
                f"Test type weights must sum to 1.0, got {total_weight}. "
                f"Weights: {weights_detail}"
            )
        return test_types

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "EvaluationConfig":
        """Load configuration from YAML file.

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            Validated EvaluationConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If config structure is invalid or weights don't sum to 1.0
        """
        from evaluation.core.config.loader import load_evaluation_config
        return load_evaluation_config(yaml_path)

    @classmethod
    def get_default(cls) -> "EvaluationConfig":
        """Get default evaluation configuration.

        Returns:
            Default EvaluationConfig with standard weights
        """
        from evaluation.core.config.loader import get_default_config
        return get_default_config()

    def get_test_type_config(self, test_type: str) -> TestTypeEvaluationConfig:
        """Get configuration for specific test type.

        Args:
            test_type: Type of test ("golden", "conversation", "system")

        Returns:
            TestTypeEvaluationConfig for the test type

        Raises:
            ValueError: If test type is not found
        """
        if test_type not in self.test_types:
            available = list(self.test_types.keys())
            raise ValueError(
                f"Unknown test type: {test_type}. Available: {available}"
            )
        return self.test_types[test_type]

    def calculate_final_score(self, test_type_scores: Dict[str, float]) -> float:
        """Calculate final aggregated score across all test types.

        Uses two-level weighting:
        1. Each test type has evaluator weights (sum to 1.0)
        2. Each test type has a weight in final score (sum to 1.0)

        Args:
            test_type_scores: Dict mapping test type → score (0-100)
                             Missing test types default to 0.0

        Returns:
            Weighted final score (0-100)

        Example:
            >>> config = EvaluationConfig.get_default()
            >>> scores = {
            ...     "golden": 85.0,      # 85% on golden tests
            ...     "conversation": 92.0, # 92% on conversation tests
            ...     "system": 100.0       # 100% on system tests
            ... }
            >>> config.calculate_final_score(scores)
            89.1  # (85 * 0.60) + (92 * 0.30) + (100 * 0.10)
        """
        weighted_sum = 0.0
        for test_type, config in self.test_types.items():
            score = test_type_scores.get(test_type, 0.0)
            weighted_sum += score * config.weight

        return weighted_sum

    class Config:
        use_enum_values = True
