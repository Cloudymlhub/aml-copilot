"""Generate unified scorecard aggregating all test types.

This script reads results from conversation, evaluation, and system tests
and creates a unified scorecard showing overall quality metrics.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from evaluation.config import (
    RESULTS_DIR,
    CONVERSATION_TESTS_LATEST_FILE,
    EVALUATION_TESTS_LATEST_FILE,
    SYSTEM_TESTS_LATEST_FILE,
    SCORECARD_LATEST_FILE
)


def load_test_results() -> Dict[str, Optional[Dict[str, Any]]]:
    """Load latest results from all test types.

    Returns:
        Dictionary with results from each test type
    """
    results = {
        "conversation": None,
        "evaluation": None,
        "system": None
    }

    # Load conversation tests
    if CONVERSATION_TESTS_LATEST_FILE.exists():
        with open(CONVERSATION_TESTS_LATEST_FILE, 'r') as f:
            results["conversation"] = json.load(f)

    # Load evaluation tests
    if EVALUATION_TESTS_LATEST_FILE.exists():
        with open(EVALUATION_TESTS_LATEST_FILE, 'r') as f:
            results["evaluation"] = json.load(f)

    # Load system tests
    if SYSTEM_TESTS_LATEST_FILE.exists():
        with open(SYSTEM_TESTS_LATEST_FILE, 'r') as f:
            results["system"] = json.load(f)

    return results


def generate_scorecard(results: Dict[str, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Generate unified scorecard from test results.

    Args:
        results: Dictionary of test results by type

    Returns:
        Unified scorecard with aggregate metrics
    """
    # Extract metrics from each test type
    conv_data = results.get("conversation") or {}
    eval_data = results.get("evaluation") or {}
    sys_data = results.get("system") or {}

    # Conversation test metrics
    conv_metrics = {
        "total": conv_data.get("total", 0),
        "passed": conv_data.get("passed", 0),
        "failed": conv_data.get("failed", 0),
        "pass_rate": conv_data.get("pass_rate", 0.0),
        "category_stats": conv_data.get("category_stats", {}),
        "status": "✅" if conv_data.get("pass_rate", 0) >= 0.8 else "⚠️" if conv_data.get("pass_rate", 0) >= 0.5 else "❌",
        "available": bool(conv_data)
    }

    # Evaluation test metrics
    eval_metrics = {
        "total": eval_data.get("total_cases", 0),
        "passed": eval_data.get("passed", 0),
        "failed": eval_data.get("failed", 0),
        "pass_rate": eval_data.get("pass_rate", 0.0),
        "avg_score": eval_data.get("avg_overall_score", 0.0),
        "status": "✅" if eval_data.get("pass_rate", 0) >= 0.9 else "⚠️" if eval_data.get("pass_rate", 0) >= 0.7 else "❌",
        "available": bool(eval_data)
    }

    # System test metrics
    sys_metrics = {
        "total": sys_data.get("total", 0),
        "passed": sys_data.get("passed", 0),
        "failed": sys_data.get("failed", 0),
        "pass_rate": sys_data.get("pass_rate", 0.0),
        "category_stats": sys_data.get("category_stats", {}),
        "status": "✅" if sys_data.get("pass_rate", 0) >= 0.9 else "⚠️" if sys_data.get("pass_rate", 0) >= 0.7 else "❌",
        "available": bool(sys_data)
    }

    # Calculate overall metrics
    total_tests = conv_metrics["total"] + eval_metrics["total"] + sys_metrics["total"]
    total_passed = conv_metrics["passed"] + eval_metrics["passed"] + sys_metrics["passed"]
    overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0.0

    # Determine overall status
    if overall_pass_rate >= 0.85:
        overall_status = "✅ EXCELLENT"
    elif overall_pass_rate >= 0.70:
        overall_status = "⚠️ GOOD"
    elif overall_pass_rate >= 0.50:
        overall_status = "⚠️ NEEDS IMPROVEMENT"
    else:
        overall_status = "❌ CRITICAL"

    # Build scorecard
    scorecard = {
        "generated_at": datetime.now().isoformat(),
        "overall": {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "overall_pass_rate": overall_pass_rate,
            "status": overall_status
        },
        "by_test_type": {
            "conversation_tests": conv_metrics,
            "evaluation_tests": eval_metrics,
            "system_tests": sys_metrics
        },
        "quality_gates": {
            "production_ready": overall_pass_rate >= 0.90,
            "conversation_ready": conv_metrics["pass_rate"] >= 0.80,
            "evaluation_ready": eval_metrics["pass_rate"] >= 0.95,
            "system_ready": sys_metrics["pass_rate"] >= 0.90
        },
        "recommendations": []
    }

    # Add recommendations
    if conv_metrics["pass_rate"] < 0.80:
        scorecard["recommendations"].append(
            f"Conversation tests: {conv_metrics['pass_rate']:.1%} pass rate. Target: 80%. "
            f"Focus on: {', '.join(k for k, v in conv_metrics.get('category_stats', {}).items() if v.get('passed', 0) / v.get('total', 1) < 0.8)}"
        )

    if eval_metrics["pass_rate"] < 0.95:
        scorecard["recommendations"].append(
            f"Evaluation tests: {eval_metrics['pass_rate']:.1%} pass rate. Target: 95%. "
            f"Review failed cases and improve domain knowledge."
        )

    if sys_metrics["pass_rate"] < 0.90:
        scorecard["recommendations"].append(
            f"System tests: {sys_metrics['pass_rate']:.1%} pass rate. Target: 90%. "
            f"Fix error handling and boundary cases."
        )

    if not scorecard["recommendations"]:
        scorecard["recommendations"].append("All quality gates met! ✅")

    return scorecard


def print_scorecard(scorecard: Dict[str, Any]):
    """Print scorecard to console in a readable format.

    Args:
        scorecard: Scorecard dictionary
    """
    print("\n" + "="*70)
    print("AML COPILOT - UNIFIED TEST SCORECARD")
    print("="*70)
    print(f"Generated: {scorecard['generated_at']}")
    print("="*70)

    # Overall summary
    overall = scorecard["overall"]
    print(f"\n{overall['status']}")
    print(f"Overall Pass Rate: {overall['overall_pass_rate']:.1%} ({overall['total_passed']}/{overall['total_tests']} tests)")

    # By test type
    print(f"\n{'Test Type':<25} {'Total':<8} {'Passed':<8} {'Pass Rate':<12} {'Status'}")
    print("-" * 70)

    by_type = scorecard["by_test_type"]

    for test_type, metrics in by_type.items():
        if not metrics["available"]:
            print(f"{test_type.replace('_', ' ').title():<25} {'N/A':<8} {'N/A':<8} {'N/A':<12} ⚠️ Not Run")
        else:
            print(
                f"{test_type.replace('_', ' ').title():<25} "
                f"{metrics['total']:<8} "
                f"{metrics['passed']:<8} "
                f"{metrics['pass_rate']:.1%}{'':<8} "
                f"{metrics['status']}"
            )

    # Quality gates
    print(f"\n{'='*70}")
    print("QUALITY GATES")
    print("="*70)

    gates = scorecard["quality_gates"]
    print(f"Production Ready:    {'✅ YES' if gates['production_ready'] else '❌ NO'}")
    print(f"Conversation Ready:  {'✅ YES' if gates['conversation_ready'] else '❌ NO'}")
    print(f"Evaluation Ready:    {'✅ YES' if gates['evaluation_ready'] else '❌ NO'}")
    print(f"System Ready:        {'✅ YES' if gates['system_ready'] else '❌ NO'}")

    # Recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print("="*70)
    for i, rec in enumerate(scorecard["recommendations"], 1):
        print(f"{i}. {rec}")

    print(f"\n{'='*70}\n")


def main():
    """Generate and display unified scorecard."""
    # Get results directory
    if not RESULTS_DIR.exists():
        print(f"❌ Results directory not found: {RESULTS_DIR}")
        print("   Run tests first: make test")
        return 1

    # Load test results
    print("Loading test results...")
    results = load_test_results()

    # Check if any results available
    if not any(results.values()):
        print("❌ No test results found!")
        print("   Run tests first:")
        print("     make test-conversations")
        print("     make test-evaluation")
        print("     make test-unit")
        return 1

    # Generate scorecard
    scorecard = generate_scorecard(results)

    # Print to console
    print_scorecard(scorecard)

    # Save scorecard
    with open(SCORECARD_LATEST_FILE, 'w') as f:
        json.dump(scorecard, f, indent=2)

    print(f"📊 Scorecard saved to: {SCORECARD_LATEST_FILE}")

    # Exit code based on overall status
    if scorecard["quality_gates"]["production_ready"]:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
