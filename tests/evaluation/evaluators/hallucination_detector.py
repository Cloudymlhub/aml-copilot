"""Hallucination detector for agent outputs.

Detects when the agent invents information not present in source data,
including fabricated facts, incorrect citations, and made-up details.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import re


@dataclass
class HallucinationReport:
    """Report of hallucinations detected."""
    hallucination_score: float  # 1.0 = no hallucinations, 0.0 = severe hallucinations
    hallucinations_found: List[Dict[str, str]]  # List of hallucinations with details
    verification_score: float  # % of facts that could be verified
    is_trustworthy: bool  # Overall trustworthiness (no critical hallucinations)


class HallucinationDetector:
    """Detect hallucinations in agent outputs.

    Checks for:
    - Invented transaction amounts
    - Fabricated dates
    - Non-existent regulations
    - Made-up customer details
    - Incorrect data references
    """

    # Known regulations for verification
    KNOWN_REGULATIONS = [
        "31 USC 5324",  # Structuring statute
        "31 CFR 1020.320",  # CTR requirements
        "31 CFR 1020.320",  # SAR requirements
        "Bank Secrecy Act",
        "BSA",
        "FinCEN",
        "31 USC 5318(g)",  # AML program requirements
        "31 CFR 1010.311",  # CTR filing
        "31 CFR 1020.220",  # Customer identification
    ]

    def detect_invented_amounts(
        self,
        agent_output: Dict[str, Any],
        source_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Detect if agent invented transaction amounts.

        Args:
            agent_output: Agent's output
            source_data: Original source data (ML output, customer data, etc.)

        Returns:
            List of invented amounts with context
        """
        hallucinations = []

        # Extract text from agent output
        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}"

        # Extract amounts from agent output (e.g., $10,000 or 10000.00)
        amount_pattern = r'\$?[\d,]+\.?\d*'
        agent_amounts = re.findall(amount_pattern, combined_text)

        # Normalize amounts (remove $ and commas)
        agent_amounts_normalized = [
            float(amt.replace('$', '').replace(',', ''))
            for amt in agent_amounts
            if amt.replace('$', '').replace(',', '').replace('.', '').isdigit()
        ]

        # Extract amounts from source data
        source_amounts = []

        # Check ML output feature values
        ml_output = source_data.get("ml_output") or agent_output.get("ml_model_output")
        if ml_output:
            feature_values = ml_output.get("feature_values", {})
            for key, value in feature_values.items():
                if isinstance(value, (int, float)):
                    source_amounts.append(float(value))

        # Check customer data
        customer_data = source_data.get("customer_data")
        if customer_data:
            # Extract numeric values from customer data
            for key, value in customer_data.items():
                if isinstance(value, (int, float)):
                    source_amounts.append(float(value))

        # Check if agent amounts are in source (with tolerance for rounding)
        for agent_amt in agent_amounts_normalized:
            # Check if this amount exists in source data (within 1% tolerance)
            found_in_source = any(
                abs(agent_amt - source_amt) / max(source_amt, 1) < 0.01
                for source_amt in source_amounts
            )

            # Also allow standard regulatory thresholds
            is_regulatory_threshold = agent_amt in [
                5000, 10000, 15000, 25000, 50000, 100000  # Common thresholds
            ]

            if not found_in_source and not is_regulatory_threshold and agent_amt > 100:
                hallucinations.append({
                    "type": "invented_amount",
                    "value": f"${agent_amt:,.2f}",
                    "severity": "HIGH",
                    "description": f"Agent mentioned amount ${agent_amt:,.2f} not found in source data"
                })

        return hallucinations

    def detect_fabricated_dates(
        self,
        agent_output: Dict[str, Any],
        source_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Detect if agent invented specific dates.

        Args:
            agent_output: Agent's output
            source_data: Original source data

        Returns:
            List of fabricated dates with context
        """
        hallucinations = []

        # Extract text from agent output
        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}"

        # Look for specific date mentions (e.g., "January 15", "2024-01-15", "Jan 15")
        # Pattern for dates like "January 15" or "Jan 15, 2024"
        date_pattern = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:,\s*\d{4})?'

        agent_dates = re.findall(date_pattern, combined_text, re.IGNORECASE)

        if agent_dates:
            # Extract dates from source data
            source_dates = []

            ml_output = source_data.get("ml_output") or agent_output.get("ml_model_output")
            if ml_output:
                daily_scores = ml_output.get("daily_risk_scores", [])
                for score in daily_scores:
                    if "date" in score:
                        source_dates.append(score["date"])

            # Check if agent mentioned specific dates not in source
            for date in agent_dates:
                # This is a hallucination - agent shouldn't mention specific dates
                # unless they were in the source data
                hallucinations.append({
                    "type": "fabricated_date",
                    "value": date,
                    "severity": "MEDIUM",
                    "description": f"Agent mentioned specific date '{date}' which may not be in source data"
                })

        return hallucinations

    def verify_regulatory_citations(
        self,
        agent_output: Dict[str, Any]
    ) -> Tuple[List[Dict[str, str]], float]:
        """Verify that regulatory citations are valid.

        Args:
            agent_output: Agent's output

        Returns:
            Tuple of (hallucinations, accuracy_score)
        """
        hallucinations = []

        compliance_analysis = agent_output.get("compliance_analysis", {})
        agent_citations = compliance_analysis.get("regulatory_references", []) if compliance_analysis else []

        if not agent_citations:
            return hallucinations, 1.0  # No citations, no errors

        # Also extract citations from text
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}"

        # Pattern for USC citations (e.g., "31 USC 5324")
        usc_pattern = r'\d+\s+USC\s+\d+'
        cfr_pattern = r'\d+\s+CFR\s+[\d.]+'

        all_citations = set(agent_citations)
        all_citations.update(re.findall(usc_pattern, combined_text, re.IGNORECASE))
        all_citations.update(re.findall(cfr_pattern, combined_text, re.IGNORECASE))

        verified = 0
        total = len(all_citations)

        for citation in all_citations:
            citation_normalized = citation.upper().strip()

            # Check if citation is in known regulations
            is_known = any(
                known.upper() in citation_normalized or citation_normalized in known.upper()
                for known in self.KNOWN_REGULATIONS
            )

            if is_known:
                verified += 1
            else:
                # Unknown citation - might be hallucination
                hallucinations.append({
                    "type": "unverified_citation",
                    "value": citation,
                    "severity": "MEDIUM",
                    "description": f"Citation '{citation}' not in known regulatory references"
                })

        accuracy = verified / total if total > 0 else 1.0

        return hallucinations, accuracy

    def detect_prohibited_content(
        self,
        agent_output: Dict[str, Any],
        should_not_include: List[str]
    ) -> List[Dict[str, str]]:
        """Detect if agent output contains prohibited content.

        Args:
            agent_output: Agent's output
            should_not_include: List of things that should NOT be in output

        Returns:
            List of prohibited content found
        """
        hallucinations = []

        if not should_not_include:
            return hallucinations

        # Extract text
        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}".lower()

        for prohibited in should_not_include:
            if prohibited.lower() in combined_text:
                hallucinations.append({
                    "type": "prohibited_content",
                    "value": prohibited,
                    "severity": "HIGH",
                    "description": f"Output contains prohibited content: '{prohibited}'"
                })

        return hallucinations

    def detect_customer_detail_hallucinations(
        self,
        agent_output: Dict[str, Any],
        source_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Detect if agent invented customer details.

        Args:
            agent_output: Agent's output
            source_data: Original source data

        Returns:
            List of invented customer details
        """
        hallucinations = []

        # Get customer data from source
        customer_data = source_data.get("customer_data", {})

        if not customer_data:
            # No customer data to verify against
            return hallucinations

        compliance_analysis = agent_output.get("compliance_analysis", {})
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        final_response = agent_output.get("final_response", "")
        combined_text = f"{analysis_text} {final_response}".lower()

        # Check if agent mentioned details not in customer data
        # Look for occupation, business type, etc.
        if customer_data.get("occupation"):
            occupation = customer_data["occupation"].lower()
            # Agent should not mention different occupations
            # (This is a simplified check - more sophisticated NLP would be better)

        # For now, we'll rely on the should_not_include list and amount/date checks
        # More sophisticated customer detail verification would require NLP/entity extraction

        return hallucinations

    def detect_hallucinations(
        self,
        agent_output: Dict[str, Any],
        source_data: Dict[str, Any],
        should_not_include: List[str]
    ) -> HallucinationReport:
        """Complete hallucination detection.

        Args:
            agent_output: Agent's output
            source_data: Original source data
            should_not_include: Content that should not be in output

        Returns:
            HallucinationReport with score and details
        """
        all_hallucinations = []

        # Run all detection methods
        all_hallucinations.extend(
            self.detect_invented_amounts(agent_output, source_data)
        )

        all_hallucinations.extend(
            self.detect_fabricated_dates(agent_output, source_data)
        )

        citation_hallucinations, citation_accuracy = self.verify_regulatory_citations(
            agent_output
        )
        all_hallucinations.extend(citation_hallucinations)

        all_hallucinations.extend(
            self.detect_prohibited_content(agent_output, should_not_include)
        )

        all_hallucinations.extend(
            self.detect_customer_detail_hallucinations(agent_output, source_data)
        )

        # Calculate hallucination score
        # Penalize based on severity
        penalty = 0.0
        for h in all_hallucinations:
            if h["severity"] == "HIGH":
                penalty += 0.3
            elif h["severity"] == "MEDIUM":
                penalty += 0.15
            else:  # LOW
                penalty += 0.05

        hallucination_score = max(0.0, 1.0 - penalty)

        # Determine trustworthiness (no HIGH severity hallucinations)
        has_high_severity = any(h["severity"] == "HIGH" for h in all_hallucinations)
        is_trustworthy = not has_high_severity

        # Verification score (how many facts could be verified)
        # This is based on citation accuracy and absence of invented data
        verification_score = citation_accuracy * (1.0 if not all_hallucinations else 0.7)

        return HallucinationReport(
            hallucination_score=hallucination_score,
            hallucinations_found=all_hallucinations,
            verification_score=verification_score,
            is_trustworthy=is_trustworthy
        )

    def evaluate(
        self,
        agent_output: Dict[str, Any],
        source_data: Dict[str, Any],
        should_not_include: List[str]
    ) -> Dict[str, Any]:
        """Complete hallucination evaluation.

        Args:
            agent_output: Agent's complete output
            source_data: Original source data
            should_not_include: Content that should not appear

        Returns:
            Dictionary with hallucination scores and details
        """
        report = self.detect_hallucinations(agent_output, source_data, should_not_include)

        return {
            "hallucination_score": report.hallucination_score,
            "verification_score": report.verification_score,
            "is_trustworthy": report.is_trustworthy,
            "hallucinations_detected": [
                {
                    "type": h["type"],
                    "value": h["value"],
                    "severity": h["severity"],
                    "description": h["description"]
                }
                for h in report.hallucinations_found
            ],
            "hallucination_count": len(report.hallucinations_found),
            "high_severity_count": sum(1 for h in report.hallucinations_found if h["severity"] == "HIGH")
        }
