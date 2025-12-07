"""Smoke test for unified evaluation framework.

Run this to verify all core components can be imported and initialized.
"""

from evaluation.core.models import (
    TestRegistry,
    GoldenTestCase,
    ConversationTestCase,
    SystemTestCase,
    UnifiedEvaluationReport,
)
from evaluation.core.evaluators.registry import EvaluatorRegistry
from evaluation.core.runner import UnifiedTestRunner

def main():
    print("\n" + "="*70)
    print("UNIFIED EVALUATION FRAMEWORK - SMOKE TEST")
    print("="*70)

    # Test imports
    print("\n1. Testing imports...")
    print("   ✅ All core modules imported successfully")

    # Test registry initialization
    print("\n2. Testing Test Registry...")
    registry = TestRegistry.get_default_registry()
    print(f"   ✅ Test Registry initialized: {len(registry.test_types)} test types")
    for test_type, config in registry.test_types.items():
        print(f"      - {test_type}: {config.description}")
        print(f"        Executor: {config.executor_class}")
        print(f"        Requires Evaluators: {config.requires_evaluators}")

    # Test evaluator registry
    print("\n3. Testing Evaluator Registry...")
    eval_registry = EvaluatorRegistry()
    print(f"   ✅ Evaluator Registry initialized: {len(eval_registry.list_evaluators())} evaluators")
    for evaluator in eval_registry.list_evaluators():
        print(f"      - {evaluator}")

    # Test evaluator assignment
    print("\n4. Testing Evaluator Assignment...")
    for test_type in eval_registry.list_test_types():
        evaluators = eval_registry.get_evaluators_for_test_type(test_type)
        print(f"   {test_type}: {len(evaluators)} evaluators")

    # Test UnifiedTestRunner initialization
    print("\n5. Testing UnifiedTestRunner...")
    try:
        runner = UnifiedTestRunner()
        print(f"   ✅ UnifiedTestRunner initialized")
        print(f"      Executors loaded: {list(runner.executors.keys())}")
        print(f"      Graph created: {runner.graph is not None}")
    except Exception as e:
        print(f"   ❌ Failed to initialize UnifiedTestRunner: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Summary
    print("\n" + "="*70)
    print("SMOKE TEST COMPLETE")
    print("="*70)
    print("✅ All core components initialized successfully!")
    print("\n🎉 Unified Evaluation Framework is ready!")
    print("\nNext steps:")
    print("  - Run conversation tests: poetry run python evaluation/core/test_example.py")
    print("  - Create test fixtures with test_type field")
    print("  - Use UnifiedTestRunner for all test types")
    print("="*70 + "\n")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
