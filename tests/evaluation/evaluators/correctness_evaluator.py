"""Correctness evaluator for agent outputs.

Evaluates whether the agent correctly identified typologies, red flags,
risk levels, and regulatory citations.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class TypologyScore:
    """Score for typology identification."""
    precision: float  # TP / (TP + FP)
    recall: float  # TP / (TP + FN)
    f1_score: float  # Harmonic mean of precision and recall
    true_positives: List[str]  # Correctly identified typologies
    false_positives: List[str]  # Incorrectly identified typologies
    false_negatives: List[str]  # Missed typologies


@dataclass
class RedFlagScore:
    """Score for red flag detection."""
    detection_rate: float  # Detected / Expected
    detected_flags: List[str]  # Red flags detected
    missed_flags: List[str]  # Red flags missed


@dataclass
class RiskAssessmentScore:
    """Score for risk assessment accuracy."""
    correct: bool  # Did agent assess correct risk level?
    expected: str  # Expected risk level
    actual: str  # Agent's risk level
    severity_diff: int  # How many levels off (0=correct, 1=off by one, etc.)


class CorrectnessEvaluator:
    """Evaluate correctness of agent outputs.

    Checks:
    - Typology identification (precision, recall, F1)
    - Red flag detection
    - Risk assessment accuracy
    - Regulatory citation accuracy
    """

    def evaluate_typology_identification(
        self,
        predicted: List[str],
        expected: List[str],
        allow_additional: bool = False
    ) -> TypologyScore:
        """Evaluate typology identification accuracy.

        Args:
            predicted: Typologies identified by agent
            expected: Expected typologies from ground truth
            allow_additional: Whether to allow agent to identify additional typologies

        Returns:
            TypologyScore with precision, recall, F1
        """
        # Normalize to lowercase for comparison
        predicted_set = {t.lower().strip() for t in predicted}
        expected_set = {t.lower().strip() for t in expected}

        # Calculate true positives, false positives, false negatives
        true_positives = list(predicted_set & expected_set)
        false_positives = list(predicted_set - expected_set)
        false_negatives = list(expected_set - predicted_set)

        # If we don't allow additional typologies, false positives are errors
        if not allow_additional and false_positives:
            # Penalize for identifying typologies that shouldn't be there
            pass
        elif allow_additional:
            # Don't penalize false positives if additional typologies are allowed
            false_positives = []

        # Calculate metrics
        tp_count = len(true_positives)
        fp_count = len(false_positives)
        fn_count = len(false_negatives)

        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return TypologyScore(
            precision=precision,
            recall=recall,
            f1_score=f1,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives
        )

    def evaluate_red_flag_detection(
        self,
        agent_output: Dict[str, Any],
        expected_flags: List[str]
    ) -> RedFlagScore:
        """Evaluate red flag detection.

        Checks if the agent's output mentions the expected red flags.

        Args:
            agent_output: Agent's complete output
            expected_flags: Expected red flags from ground truth

        Returns:
            RedFlagScore with detection rate and details
        """
        # Extract text from agent output for searching
        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}".lower()

        # Check which expected red flags were detected
        detected = []
        missed = []

        for flag in expected_flags:
            # Normalize flag name for search
            # e.g., "transactions_below_threshold" → "transactions below threshold"
            flag_normalized = flag.replace("_", " ").lower()

            if flag_normalized in combined_text:
                detected.append(flag)
            else:
                missed.append(flag)

        detection_rate = len(detected) / len(expected_flags) if expected_flags else 0.0

        return RedFlagScore(
            detection_rate=detection_rate,
            detected_flags=detected,
            missed_flags=missed
        )

    def evaluate_risk_assessment(
        self,
        agent_output: Dict[str, Any],
        expected_risk: str
    ) -> RiskAssessmentScore:
        """Evaluate risk assessment accuracy.

        Args:
            agent_output: Agent's complete output
            expected_risk: Expected risk level (LOW, MEDIUM, HIGH, CRITICAL)

        Returns:
            RiskAssessmentScore
        """
        compliance_analysis = agent_output.get("compliance_analysis", {})
        actual_risk = compliance_analysis.get("risk_assessment", "") if compliance_analysis else ""

        # Normalize
        expected_normalized = expected_risk.upper().strip()
        actual_normalized = actual_risk.upper().strip()

        correct = (expected_normalized == actual_normalized)

        # Calculate severity difference
        risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        try:
            expected_idx = risk_levels.index(expected_normalized)
            actual_idx = risk_levels.index(actual_normalized) if actual_normalized in risk_levels else -1

            if actual_idx >= 0:
                severity_diff = abs(expected_idx - actual_idx)
            else:
                severity_diff = len(risk_levels)  # Max difference if not found
        except ValueError:
            severity_diff = len(risk_levels)

        return RiskAssessmentScore(
            correct=correct,
            expected=expected_normalized,
            actual=actual_normalized,
            severity_diff=severity_diff
        )

    def evaluate_regulatory_citations(
        self,
        agent_output: Dict[str, Any],
        expected_citations: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """Evaluate regulatory citation accuracy.

        Args:
            agent_output: Agent's complete output
            expected_citations: Expected regulatory citations

        Returns:
            Tuple of (accuracy_score, citations_found, citations_missing)
        """
        compliance_analysis = agent_output.get("compliance_analysis", {})

        # Extract citations from structured field
        agent_citations = compliance_analysis.get("regulatory_references", []) if compliance_analysis else []

        # Also search in text
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}"

        citations_found = []
        citations_missing = []

        for citation in expected_citations:
            # Check if citation appears in agent's structured citations or text
            found = (
                citation in agent_citations or
                citation.lower() in combined_text.lower()
            )

            if found:
                citations_found.append(citation)
            else:
                citations_missing.append(citation)

        accuracy = len(citations_found) / len(expected_citations) if expected_citations else 0.0

        return accuracy, citations_found, citations_missing

    def evaluate(
        self,
        agent_output: Dict[str, Any],
        expected_typologies: List[str],
        expected_red_flags: List[str],
        expected_risk: str,
        expected_citations: List[str],
        allow_additional_typologies: bool = False
    ) -> Dict[str, Any]:
        """Complete correctness evaluation.

        Args:
            agent_output: Agent's complete output
            expected_typologies: Expected typologies
            expected_red_flags: Expected red flags
            expected_risk: Expected risk level
            expected_citations: Expected regulatory citations
            allow_additional_typologies: Allow agent to identify additional typologies

        Returns:
            Dictionary with all correctness scores
        """
        # Extract agent's typologies
        compliance_analysis = agent_output.get("compliance_analysis", {})
        agent_typologies = compliance_analysis.get("typologies", []) if compliance_analysis else []

        # Evaluate each dimension
        typology_score = self.evaluate_typology_identification(
            agent_typologies, expected_typologies, allow_additional_typologies
        )

        red_flag_score = self.evaluate_red_flag_detection(
            agent_output, expected_red_flags
        )

        risk_score = self.evaluate_risk_assessment(
            agent_output, expected_risk
        )

        citation_accuracy, citations_found, citations_missing = self.evaluate_regulatory_citations(
            agent_output, expected_citations
        )

        # Calculate overall correctness score
        # Weighted average: typology (40%), red flags (30%), risk (20%), citations (10%)
        overall_correctness = (
            typology_score.f1_score * 0.4 +
            red_flag_score.detection_rate * 0.3 +
            (1.0 if risk_score.correct else 0.0) * 0.2 +
            citation_accuracy * 0.1
        )

        return {
            "correctness_score": overall_correctness,
            "typology_score": {
                "precision": typology_score.precision,
                "recall": typology_score.recall,
                "f1": typology_score.f1_score,
                "true_positives": typology_score.true_positives,
                "false_positives": typology_score.false_positives,
                "false_negatives": typology_score.false_negatives
            },
            "red_flag_score": {
                "detection_rate": red_flag_score.detection_rate,
                "detected": red_flag_score.detected_flags,
                "missed": red_flag_score.missed_flags
            },
            "risk_assessment": {
                "correct": risk_score.correct,
                "expected": risk_score.expected,
                "actual": risk_score.actual,
                "severity_diff": risk_score.severity_diff
            },
            "regulatory_citations": {
                "accuracy": citation_accuracy,
                "found": citations_found,
                "missing": citations_missing
            }
        }
