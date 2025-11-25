"""Example script demonstrating the AML Copilot evaluation framework.

This script shows how to:
1. Load golden test cases
2. Run evaluations
3. Use specialized evaluators
4. Generate reports
"""

import sys
from pathlib import Path
from tests.config import GOLDEN_DATASETS_DIR, EVALUATION_REPORTS_DIR
from tests.evaluation.test_runner import AgentEvaluationRunner
from tests.evaluation.evaluators import (
    CorrectnessEvaluator,
    CompletenessEvaluator,
    HallucinationDetector
)


def example_1_quick_evaluation():
    """Example 1: Quick evaluation of all test cases."""
    print("=" * 70)
    print("EXAMPLE 1: Quick Evaluation")
    print("=" * 70)

    runner = AgentEvaluationRunner()

    # Run evaluation on structuring cases
    dataset_path = GOLDEN_DATASETS_DIR / "structuring_cases.json"

    report = runner.run_evaluation_suite(dataset_path)

    print(f"\n✅ Evaluation complete!")
    print(f"   Pass Rate: {report.pass_rate:.1%}")
    print(f"   Average Overall Score: {report.avg_overall_score:.1f}/100")

    return report


def example_2_single_test_detailed():
    """Example 2: Run single test with detailed output."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Single Test Case (Detailed)")
    print("=" * 70)

    runner = AgentEvaluationRunner()

    # Load test cases
    dataset_path = GOLDEN_DATASETS_DIR / "structuring_cases.json"
    test_cases = runner.load_golden_test_cases(dataset_path)

    # Run first test case
    test_case = test_cases[0]
    print(f"\nRunning: {test_case.test_id} - {test_case.description}")

    result = runner.execute_test_case(test_case)

    # Print detailed results
    print(f"\n📊 Test Result Details:")
    print(f"   Status: {result.status}")
    print(f"   Overall Score: {result.overall_score:.1f}/100")
    print(f"   - Correctness: {result.correctness_score:.2f}")
    print(f"   - Completeness: {result.completeness_score:.2f}")
    print(f"   - Hallucination: {result.hallucination_score:.2f}")
    print(f"   Execution Time: {result.execution_time_seconds:.2f}s")

    if result.key_facts_covered:
        print(f"\n✓ Key Facts Covered ({len(result.key_facts_covered)}):")
        for fact in result.key_facts_covered:
            print(f"   • {fact}")

    if result.key_facts_missing:
        print(f"\n✗ Key Facts Missing ({len(result.key_facts_missing)}):")
        for fact in result.key_facts_missing:
            print(f"   • {fact}")

    return result


def example_3_using_evaluators():
    """Example 3: Using individual evaluators."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Using Individual Evaluators")
    print("=" * 70)

    # Create sample agent output (mock for demonstration)
    agent_output = {
        "compliance_analysis": {
            "typologies": ["structuring"],
            "risk_assessment": "HIGH",
            "analysis": "The customer conducted 6 transactions averaging $9,850, which is just below the $10,000 CTR threshold. This pattern is consistent with structuring behavior as defined in 31 USC 5324.",
            "recommendations": [
                "Verify if transactions are related",
                "Review transaction locations",
                "Interview customer about business purpose"
            ],
            "regulatory_references": ["31 USC 5324", "31 CFR 1020.320"]
        },
        "final_response": "Analysis complete. Customer C000123 shows indicators of structuring.",
        "ml_model_output": {
            "feature_values": {
                "txn_count_near_threshold": 6,
                "avg_txn_amount": 9850.50,
                "total_amount_30d": 59100.00
            }
        }
    }

    # Example 3A: Correctness Evaluator
    print("\n--- Correctness Evaluator ---")
    correctness_eval = CorrectnessEvaluator()

    correctness_result = correctness_eval.evaluate(
        agent_output=agent_output,
        expected_typologies=["structuring"],
        expected_red_flags=["transactions_below_threshold"],
        expected_risk="HIGH",
        expected_citations=["31 USC 5324"],
        allow_additional_typologies=False
    )

    print(f"Correctness Score: {correctness_result['correctness_score']:.2f}")
    print(f"Typology F1: {correctness_result['typology_score']['f1']:.2f}")
    print(f"Red Flag Detection: {correctness_result['red_flag_score']['detection_rate']:.1%}")
    print(f"Risk Assessment: {correctness_result['risk_assessment']['correct']}")

    # Example 3B: Completeness Evaluator
    print("\n--- Completeness Evaluator ---")
    completeness_eval = CompletenessEvaluator()

    completeness_result = completeness_eval.evaluate(
        agent_output=agent_output,
        expected_facts=[
            "6 transactions",
            "$9,850",
            "$10,000 threshold",
            "$59,100",
            "31 USC 5324"
        ],
        expected_recommendations=[
            "verify transactions",
            "review locations",
            "interview customer"
        ],
        require_attribution_chain=True
    )

    print(f"Completeness Score: {completeness_result['completeness_score']:.2f}")
    print(f"Key Facts Coverage: {completeness_result['key_facts']['coverage_percentage']:.1f}%")
    print(f"Recommendation Actionability: {completeness_result['recommendations']['actionability']:.1%}")
    print(f"Attribution Chain Present: {completeness_result['attribution_chain']['present']}")

    # Example 3C: Hallucination Detector
    print("\n--- Hallucination Detector ---")
    hallucination_detector = HallucinationDetector()

    source_data = {
        "ml_output": agent_output["ml_model_output"],
        "customer_data": {
            "cif_no": "C000123",
            "name": "John Doe",
            "occupation": "Small business owner"
        }
    }

    hallucination_result = hallucination_detector.evaluate(
        agent_output=agent_output,
        source_data=source_data,
        should_not_include=["FILE_SAR", "CLOSE", "January 15"]
    )

    print(f"Hallucination Score: {hallucination_result['hallucination_score']:.2f}")
    print(f"Is Trustworthy: {hallucination_result['is_trustworthy']}")
    print(f"Hallucinations Found: {hallucination_result['hallucination_count']}")

    if hallucination_result['hallucinations_detected']:
        print("\n⚠️ Hallucinations Detected:")
        for h in hallucination_result['hallucinations_detected']:
            print(f"   [{h['severity']}] {h['type']}: {h['description']}")


def example_4_filter_and_run():
    """Example 4: Filter test cases and run specific ones."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Filtering Test Cases")
    print("=" * 70)

    runner = AgentEvaluationRunner()

    dataset_path = GOLDEN_DATASETS_DIR / "structuring_cases.json"

    # Load only HIGH priority cases
    high_priority_cases = runner.load_golden_test_cases(
        dataset_path,
        priority="HIGH"
    )

    print(f"\nFound {len(high_priority_cases)} HIGH priority test cases:")
    for tc in high_priority_cases:
        print(f"   • {tc.test_id}: {tc.description}")

    # Run evaluation on filtered cases
    print(f"\nRunning evaluation on HIGH priority cases...")
    report = runner.run_evaluation_suite(
        dataset_path,
        priority="HIGH"
    )

    print(f"\n✅ HIGH Priority Cases:")
    print(f"   Pass Rate: {report.pass_rate:.1%}")
    print(f"   Average Score: {report.avg_overall_score:.1f}/100")


def example_5_save_report():
    """Example 5: Save evaluation report for baseline comparison."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Saving Evaluation Report")
    print("=" * 70)

    runner = AgentEvaluationRunner()

    dataset_path = GOLDEN_DATASETS_DIR / "structuring_cases.json"

    # Run evaluation
    report = runner.run_evaluation_suite(dataset_path)

    # Save report
    output_path = EVALUATION_REPORTS_DIR / f"{report.report_id}.json"
    runner.save_report(report, output_path)

    print(f"\n✅ Report saved to: {output_path}")
    print(f"\nThis report can be used as a baseline for regression testing:")
    print(f"   $ python run_evaluation.py --baseline {output_path}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("AML COPILOT EVALUATION FRAMEWORK - EXAMPLES")
    print("=" * 70)

    try:
        # Run examples
        example_1_quick_evaluation()
        example_2_single_test_detailed()
        example_3_using_evaluators()
        example_4_filter_and_run()
        example_5_save_report()

        print("\n" + "=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
