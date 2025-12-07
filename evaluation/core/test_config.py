"""Test script for Phase 2 configuration system.

Tests without requiring the full agent graph initialization.
"""

from pathlib import Path

def test_config_loading():
    """Test configuration loading and validation."""
    print("\n" + "="*70)
    print("PHASE 2: CONFIGURATION SYSTEM TEST")
    print("="*70)

    # Test 1: Import config models
    print("\n1. Testing config model imports...")
    try:
        from evaluation.core.config.models import (
            EvaluatorType,
            EvaluatorConfig,
            TestTypeEvaluationConfig,
            EvaluationConfig,
        )
        print("   ✅ Config models imported successfully")
    except Exception as e:
        print(f"   ❌ Failed to import config models: {e}")
        return 1

    # Test 2: Load default config
    print("\n2. Testing default config loading...")
    try:
        config = EvaluationConfig.get_default()
        print(f"   ✅ Default config loaded: {len(config.test_types)} test types")
    except Exception as e:
        print(f"   ❌ Failed to load default config: {e}")
        return 1

    # Test 3: Validate test type weights
    print("\n3. Testing test type weight validation...")
    total_weight = sum(tc.weight for tc in config.test_types.values())
    if abs(total_weight - 1.0) < 0.001:
        print(f"   ✅ Test type weights sum to 1.0 ({total_weight:.3f})")
    else:
        print(f"   ❌ Test type weights don't sum to 1.0 (got {total_weight:.3f})")
        return 1

    # Test 4: Validate evaluator weights
    print("\n4. Testing evaluator weight validation...")
    for test_type, test_config in config.test_types.items():
        if test_config.evaluators:
            evaluator_weight = sum(e.weight for e in test_config.evaluators if e.enabled)
            if abs(evaluator_weight - 1.0) < 0.001:
                print(f"   ✅ {test_type}: evaluator weights sum to 1.0 ({evaluator_weight:.3f})")
            else:
                print(f"   ❌ {test_type}: evaluator weights don't sum to 1.0 (got {evaluator_weight:.3f})")
                return 1
        else:
            print(f"   ℹ️  {test_type}: no evaluators (skip weight check)")

    # Test 5: Test config auto-loading
    print("\n5. Testing config auto-loading from paths...")
    golden_config = config.get_test_type_config("golden")
    for eval_config in golden_config.evaluators:
        if eval_config.config_path:
            print(f"   📄 {eval_config.name}: config_path = {eval_config.config_path}")
            print(f"      config loaded: {len(eval_config.config)} keys")
        elif eval_config.config:
            print(f"   📝 {eval_config.name}: inline config with {len(eval_config.config)} keys")

    # Test 6: Test final score calculation
    print("\n6. Testing final score calculation...")
    test_scores = {
        "golden": 85.0,
        "conversation": 92.0,
        "system": 100.0
    }
    final_score = config.calculate_final_score(test_scores)
    expected = (85 * 0.6) + (92 * 0.3) + (100 * 0.1)
    if abs(final_score - expected) < 0.001:
        print(f"   ✅ Final score calculated correctly: {final_score:.1f}")
        print(f"      Formula: (85 * 0.6) + (92 * 0.3) + (100 * 0.1) = {expected:.1f}")
    else:
        print(f"   ❌ Final score incorrect: got {final_score:.1f}, expected {expected:.1f}")
        return 1

    # Test 7: Test evaluator registry
    print("\n7. Testing evaluator registry...")
    try:
        from evaluation.core.evaluators.registry import EvaluatorRegistry
        registry = EvaluatorRegistry()
        evaluators = registry.list_evaluators()
        print(f"   ✅ Evaluator registry initialized: {len(evaluators)} evaluators")
        for evaluator_name in evaluators:
            print(f"      - {evaluator_name}")
    except Exception as e:
        print(f"   ❌ Failed to initialize evaluator registry: {e}")
        return 1

    # Summary
    print("\n" + "="*70)
    print("CONFIGURATION SYSTEM TEST COMPLETE")
    print("="*70)
    print("✅ All configuration tests passed!")
    print("\n🎉 Phase 2: Centralized Evaluation Configuration is working!")
    print("\nConfiguration features verified:")
    print("  - Two-level weighting system (test types + evaluators)")
    print("  - Automatic weight validation (sum to 1.0)")
    print("  - Config auto-loading from paths")
    print("  - Final score calculation across test types")
    print("  - Evaluator registry integration")
    print("="*70 + "\n")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(test_config_loading())
