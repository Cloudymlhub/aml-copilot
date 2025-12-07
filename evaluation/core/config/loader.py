"""Configuration loaders for evaluation framework.

Loads YAML configuration files and validates them using Pydantic models.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import ValidationError


def load_evaluation_config(yaml_path: Path):
    """Load evaluation config from YAML file.

    Loads and validates the main evaluation configuration file which defines:
    - Test types with weights (must sum to 1.0)
    - Evaluators for each test type with weights (must sum to 1.0)
    - Thresholds and configurations

    Args:
        yaml_path: Path to YAML configuration file

    Returns:
        Validated EvaluationConfig instance

    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If config structure is invalid or weights don't sum to 1.0
        yaml.YAMLError: If YAML syntax is invalid

    Example:
        >>> from pathlib import Path
        >>> config = load_evaluation_config(Path("evaluation_config.yaml"))
        >>> print(config.test_types["golden"].weight)
        0.6
    """
    # Import here to avoid circular dependency
    from evaluation.core.config.models import EvaluationConfig

    if not yaml_path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    try:
        with open(yaml_path) as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML syntax in {yaml_path}: {e}")

    if not raw_config:
        raise ValueError(f"Empty config file: {yaml_path}")

    # Pydantic validates:
    # - Structure (required fields, types)
    # - Enums (evaluator names must be valid)
    # - Weights sum to 1.0 (both levels)
    # - Config auto-loading from paths
    try:
        return EvaluationConfig(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Invalid config in {yaml_path}: {e}")


def get_default_config():
    """Get default evaluation configuration.

    Loads the default configuration from evaluation/config/default_evaluation_config.yaml.

    Returns:
        Default EvaluationConfig with standard weights

    Raises:
        FileNotFoundError: If default config file not found
        ValidationError: If default config is invalid

    Example:
        >>> config = get_default_config()
        >>> config.get_test_type_config("golden").weight
        0.6
    """
    # evaluation/core/config/loader.py → evaluation/config/default_evaluation_config.yaml
    default_yaml = Path(__file__).parent.parent.parent / "config" / "default_evaluation_config.yaml"

    if not default_yaml.exists():
        raise FileNotFoundError(
            f"Default evaluation config not found at {default_yaml}. "
            "Please create it or specify a custom config path."
        )

    return load_evaluation_config(default_yaml)


def load_evaluator_config(config_path: Path) -> Dict[str, Any]:
    """Load evaluator-specific configuration from YAML file.

    These are separate YAML files referenced by the main evaluation config.
    They contain evaluator-specific settings like feature weights, thresholds, etc.

    Args:
        config_path: Path to evaluator config YAML

    Returns:
        Dictionary with evaluator-specific settings (empty dict if file doesn't exist)

    Raises:
        yaml.YAMLError: If YAML syntax is invalid

    Example:
        >>> from pathlib import Path
        >>> config = load_evaluator_config(
        ...     Path("evaluation/config/evaluators/correctness_config.yaml")
        ... )
        >>> config["typologies"]["weight_in_correctness"]
        0.4
    """
    if not config_path.exists():
        # Return empty dict if no config - evaluator will use defaults
        return {}

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config if config is not None else {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML syntax in {config_path}: {e}")
