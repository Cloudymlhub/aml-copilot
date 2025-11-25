"""Centralized evaluation configuration and constants.

This module provides shared configuration for all evaluation modules,
including paths, directories, and common settings.
"""

from pathlib import Path
from typing import Optional

# Project structure
EVALUATION_ROOT = Path(__file__).parent
PROJECT_ROOT = EVALUATION_ROOT.parent

# Results directories
RESULTS_DIR = EVALUATION_ROOT / "results"
GOLDEN_DATASETS_DIR = EVALUATION_ROOT / "golden_datasets"

# Ensure directories exist
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# Latest result file paths (for non-categorized results)
CONVERSATION_TESTS_LATEST_FILE = RESULTS_DIR / "conversation_tests_latest.json"
EVALUATION_TESTS_LATEST_FILE = RESULTS_DIR / "evaluation_tests_latest.json"
SYSTEM_TESTS_LATEST_FILE = RESULTS_DIR / "system_tests_latest.json"
SCORECARD_LATEST_FILE = RESULTS_DIR / "test_scorecard_latest.json"


def get_timestamped_filename(base_name: str, category: Optional[str] = None) -> str:
    """Generate timestamped filename for test results.

    Args:
        base_name: Base name for the file (e.g., 'conversation_tests')
        category: Optional category suffix

    Returns:
        Formatted filename with timestamp
    """
    from datetime import datetime
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    category_suffix = f"_{category}" if category else ""
    return f"{base_name}_{timestamp_str}{category_suffix}.json"


def get_latest_filename(base_name: str, category: Optional[str] = None) -> str:
    """Generate 'latest' filename for test results with optional category.

    Use this when you need a categorized result file (e.g., 'conversation_tests_latest_data_synthesis.json').
    For non-categorized files, use the predefined constants instead (e.g., CONVERSATION_TESTS_LATEST_FILE).

    Args:
        base_name: Base name for the file (e.g., 'conversation_tests')
        category: Optional category suffix

    Returns:
        Formatted 'latest' filename
    """
    category_suffix = f"_{category}" if category else ""
    return f"{base_name}_latest{category_suffix}.json"


def get_result_file_path(base_name: str, category: Optional[str] = None, timestamped: bool = True) -> Path:
    """Get full path to a result file.

    Convenience function that combines directory + filename generation.

    Args:
        base_name: Base name for the file (e.g., 'conversation_tests')
        category: Optional category suffix
        timestamped: If True, generates timestamped filename; if False, generates 'latest' filename

    Returns:
        Full Path to the result file
    """
    if timestamped:
        filename = get_timestamped_filename(base_name, category)
    else:
        filename = get_latest_filename(base_name, category)
    return RESULTS_DIR / filename
