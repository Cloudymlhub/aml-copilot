"""Completeness evaluator for agent outputs.

Evaluates whether the agent covered all key facts and provided
complete, actionable recommendations.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class KeyFactsCoverage:
    """Coverage score for key facts."""
    coverage_rate: float  # Facts covered / Facts expected
    facts_covered: List[str]  # Facts found in output
    facts_missing: List[str]  # Facts not mentioned
    coverage_percentage: float  # coverage_rate as percentage


@dataclass
class RecommendationScore:
    """Score for recommendation quality."""
    actionability: float  # How actionable are recommendations (0-1)
    coverage: float  # Coverage of expected recommendations (0-1)
    recommendations_provided: List[str]  # Recommendations in output
    recommendations_missing: List[str]  # Expected recommendations not provided
    is_actionable: bool  # Are recommendations specific and actionable?


class CompletenessEvaluator:
    """Evaluate completeness of agent outputs.

    Checks:
    - Key facts coverage
    - Recommendation completeness
    - Attribution chain explanation
    - Investigation steps provided
    """

    def evaluate_key_facts_coverage(
        self,
        agent_output: Dict[str, Any],
        expected_facts: List[str]
    ) -> KeyFactsCoverage:
        """Evaluate whether agent covered all key facts.

        Args:
            agent_output: Agent's complete output
            expected_facts: List of key facts that should be mentioned

        Returns:
            KeyFactsCoverage with coverage rate and details
        """
        if not expected_facts:
            # No expected facts to check
            return KeyFactsCoverage(
                coverage_rate=1.0,
                facts_covered=[],
                facts_missing=[],
                coverage_percentage=100.0
            )

        # Extract text from agent output
        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}".lower()

        # Check each expected fact
        facts_covered = []
        facts_missing = []

        for fact in expected_facts:
            # Normalize fact for search (handle different formats)
            fact_normalized = fact.lower().strip()

            # Check if fact appears in output
            # Use flexible matching (substring search)
            if fact_normalized in combined_text:
                facts_covered.append(fact)
            else:
                # Try more flexible matching (e.g., "$10,000" matches "10000" or "10K")
                fact_words = fact_normalized.split()
                # If at least half the words from the fact appear, consider it covered
                words_found = sum(1 for word in fact_words if word in combined_text)
                if len(fact_words) > 0 and words_found / len(fact_words) >= 0.5:
                    facts_covered.append(fact)
                else:
                    facts_missing.append(fact)

        coverage_rate = len(facts_covered) / len(expected_facts)
        coverage_percentage = coverage_rate * 100

        return KeyFactsCoverage(
            coverage_rate=coverage_rate,
            facts_covered=facts_covered,
            facts_missing=facts_missing,
            coverage_percentage=coverage_percentage
        )

    def evaluate_recommendations(
        self,
        agent_output: Dict[str, Any],
        expected_recommendations: List[str]
    ) -> RecommendationScore:
        """Evaluate recommendation completeness and actionability.

        Args:
            agent_output: Agent's complete output
            expected_recommendations: Expected recommendation themes

        Returns:
            RecommendationScore
        """
        compliance_analysis = agent_output.get("compliance_analysis", {})
        agent_recommendations = compliance_analysis.get("recommendations", []) if compliance_analysis else []

        if not agent_recommendations:
            # No recommendations provided
            return RecommendationScore(
                actionability=0.0,
                coverage=0.0,
                recommendations_provided=[],
                recommendations_missing=expected_recommendations,
                is_actionable=False
            )

        # Check coverage of expected recommendations
        recommendations_provided = []
        recommendations_missing = []

        for expected_rec in expected_recommendations:
            # Check if this recommendation theme is covered
            expected_normalized = expected_rec.lower()

            # Search in agent's recommendations
            found = any(
                expected_normalized in agent_rec.lower()
                for agent_rec in agent_recommendations
            )

            if found:
                recommendations_provided.append(expected_rec)
            else:
                recommendations_missing.append(expected_rec)

        coverage = (
            len(recommendations_provided) / len(expected_recommendations)
            if expected_recommendations
            else 1.0
        )

        # Evaluate actionability (are recommendations specific?)
        # Actionable recommendations typically:
        # - Are specific (mention what to do)
        # - Provide concrete steps
        # - Avoid vague language

        actionable_count = 0
        for rec in agent_recommendations:
            rec_lower = rec.lower()

            # Check for actionable indicators
            has_action_verb = any(verb in rec_lower for verb in [
                "verify", "review", "check", "investigate", "interview",
                "request", "obtain", "analyze", "compare", "document"
            ])

            has_specificity = any(indicator in rec_lower for indicator in [
                "customer", "transaction", "business", "account",
                "location", "documentation", "records"
            ])

            is_not_vague = not any(vague in rec_lower for vague in [
                "consider", "might want to", "could be", "perhaps"
            ])

            if has_action_verb and has_specificity and is_not_vague:
                actionable_count += 1

        actionability = actionable_count / len(agent_recommendations)
        is_actionable = actionability >= 0.6  # At least 60% actionable

        return RecommendationScore(
            actionability=actionability,
            coverage=coverage,
            recommendations_provided=recommendations_provided,
            recommendations_missing=recommendations_missing,
            is_actionable=is_actionable
        )

    def evaluate_attribution_chain(
        self,
        agent_output: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Evaluate whether agent explained the attribution chain.

        Attribution chain: Typology → Red Flags → Features

        Args:
            agent_output: Agent's complete output

        Returns:
            Tuple of (has_attribution_chain, explanation)
        """
        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}".lower()

        # Check for attribution chain indicators
        has_typology_mention = any(word in combined_text for word in [
            "typology", "pattern", "structuring", "layering"
        ])

        has_red_flag_mention = any(word in combined_text for word in [
            "red flag", "indicator", "suspicious", "unusual"
        ])

        has_feature_mention = any(word in combined_text for word in [
            "transaction", "amount", "frequency", "threshold", "feature"
        ])

        has_explanation_words = any(word in combined_text for word in [
            "because", "indicates", "suggests", "shows", "demonstrates",
            "based on", "due to", "as evidenced by"
        ])

        # Attribution chain is present if all elements are mentioned with explanation
        has_attribution = (
            has_typology_mention and
            has_red_flag_mention and
            has_feature_mention and
            has_explanation_words
        )

        if has_attribution:
            explanation = "Agent provided complete attribution chain linking typology → red flags → features"
        else:
            missing = []
            if not has_typology_mention:
                missing.append("typology identification")
            if not has_red_flag_mention:
                missing.append("red flag explanation")
            if not has_feature_mention:
                missing.append("feature analysis")
            if not has_explanation_words:
                missing.append("causal explanation")

            explanation = f"Attribution chain incomplete. Missing: {', '.join(missing)}"

        return has_attribution, explanation

    def evaluate(
        self,
        agent_output: Dict[str, Any],
        expected_facts: List[str],
        expected_recommendations: List[str],
        require_attribution_chain: bool = False
    ) -> Dict[str, Any]:
        """Complete completeness evaluation.

        Args:
            agent_output: Agent's complete output
            expected_facts: Expected key facts
            expected_recommendations: Expected recommendation themes
            require_attribution_chain: Whether to require attribution chain explanation

        Returns:
            Dictionary with completeness scores
        """
        # Evaluate each dimension
        facts_coverage = self.evaluate_key_facts_coverage(
            agent_output, expected_facts
        )

        recommendations_score = self.evaluate_recommendations(
            agent_output, expected_recommendations
        )

        has_attribution, attribution_explanation = self.evaluate_attribution_chain(
            agent_output
        )

        # Calculate overall completeness score
        # Weighted average: facts (50%), recommendations (40%), attribution (10%)
        overall_completeness = (
            facts_coverage.coverage_rate * 0.5 +
            (recommendations_score.coverage * 0.7 + recommendations_score.actionability * 0.3) * 0.4 +
            (1.0 if has_attribution else 0.0) * 0.1
        )

        return {
            "completeness_score": overall_completeness,
            "key_facts": {
                "coverage_rate": facts_coverage.coverage_rate,
                "coverage_percentage": facts_coverage.coverage_percentage,
                "covered": facts_coverage.facts_covered,
                "missing": facts_coverage.facts_missing
            },
            "recommendations": {
                "actionability": recommendations_score.actionability,
                "coverage": recommendations_score.coverage,
                "is_actionable": recommendations_score.is_actionable,
                "provided": recommendations_score.recommendations_provided,
                "missing": recommendations_score.recommendations_missing
            },
            "attribution_chain": {
                "present": has_attribution,
                "explanation": attribution_explanation
            }
        }
