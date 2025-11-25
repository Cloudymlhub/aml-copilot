"""Modular prompt components for AML Copilot agents.

This module contains reusable prompt building blocks that can be:
- Maintained independently
- Shared across multiple agents
- Updated without breaking main prompts
- Reviewed by domain experts separately

Components:
- red_flag_catalog: Definitions of 20-30 common AML red flags
- typology_library: Descriptions of major AML typologies
- regulatory_references: BSA/AML regulations and thresholds
"""

from .red_flag_catalog import RED_FLAG_CATALOG
from .typology_library import TYPOLOGY_LIBRARY
from .regulatory_references import REGULATORY_REFERENCES

__all__ = [
    "RED_FLAG_CATALOG",
    "TYPOLOGY_LIBRARY",
    "REGULATORY_REFERENCES",
]
