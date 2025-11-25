Run a human-review evaluation test where an expert (you) evaluates agent outputs against test cases.

## Purpose

Simulate the human expert review process for agent quality assurance. Present agent outputs in a structured format for expert scoring and feedback collection.

## Process

1. **Select Test Cases**: Choose 3-5 test cases (random or specific)
2. **Run Agent**: Execute agent workflow for each case
3. **Present for Review**: Show output in review format
4. **Collect Scores**: Ask expert to score on multiple dimensions
5. **Gather Feedback**: Collect qualitative feedback
6. **Generate Report**: Summarize expert review results

## Review Format

For each test case, present:

```markdown
# Test Case: STRUCT_001 - Classic Structuring Pattern

## Context
- **Customer**: C000123 (Small business owner)
- **Alert**: ALT_2024_001
- **ML Assessment**: Structuring (85% likelihood)
- **Key Data**: 6 transactions averaging $9,850, total $59,100

## Agent Output

[Full agent response here - formatted for readability]

---

## Expert Review Form

### Scoring (0-10 scale)

**Technical Accuracy**: How correct is the AML analysis?
Score: ___/10
Comments: ___

**Practical Usefulness**: Would this help an analyst investigate?
Score: ___/10
Comments: ___

**Regulatory Compliance**: Proper citations, thresholds, guidance?
Score: ___/10
Comments: ___

**Overall Quality**: Would you trust this output?
Score: ___/10
Comments: ___

### Qualitative Feedback

**Strengths** (What did the agent do well?):
- ___
- ___

**Improvements** (What could be better?):
- ___
- ___

**Concerns** (Any red flags or issues?):
- ___

**Approved for Production**: [ ] Yes  [ ] No  [ ] With Changes

---

## Ground Truth Comparison

**Expected Typologies**: structuring
**Agent Identified**: ___

**Expected Red Flags**: transactions_below_threshold
**Agent Identified**: ___

**Expected Risk**: HIGH
**Agent Assessed**: ___

**Key Facts Coverage**: ___/7 (___%)
- [ ] "6 transactions"
- [ ] "$9,850 average"
- [ ] "$10,000 threshold"
- [ ] "$59,100 total"
- [ ] "31 USC 5324"
- [ ] "31 CFR 1020.320"
- [ ] "$5,000 SAR threshold"

**Hallucinations Detected**: [ ] None  [ ] See below
Details: ___
```

## Usage Examples

**Run random sample review**:
```
/human-review-test
```
This will select 3-5 random test cases from golden dataset.

**Review specific category**:
```
/human-review-test category=structuring
```
Reviews structuring cases only.

**Review specific test case**:
```
/human-review-test test_id=STRUCT_001
```
Reviews one specific case.

**Quick review (1 case)**:
```
/human-review-test quick
```
Reviews just 1 case for rapid feedback.

## Output

After completing reviews, generate:

```markdown
# Human Review Test Report
Date: 2024-01-15
Reviewer: [Expert Name]
Cases Reviewed: 3

## Summary Scores

| Dimension | Avg Score | Range |
|-----------|-----------|-------|
| Technical Accuracy | 8.7/10 | 8-9 |
| Practical Usefulness | 8.3/10 | 7-9 |
| Regulatory Compliance | 9.0/10 | 9-9 |
| Overall Quality | 8.7/10 | 8-9 |

## Approval Status
- Approved: 2/3 (67%)
- Approved with Changes: 1/3 (33%)
- Not Approved: 0/3 (0%)

## Key Findings

### Strengths
- Accurate typology identification across all cases
- Proper regulatory citations
- Clear, actionable recommendations

### Common Issues
- Could provide more specific transaction dates
- Sometimes misses secondary typologies

### Action Items
1. Update prompt to request specific dates when available
2. Add test case for detecting secondary typologies
3. Review borderline case handling

## Individual Case Results

### STRUCT_001 - APPROVED
Scores: Tech 9/10, Practical 8/10, Regulatory 9/10, Overall 9/10
Strengths: Excellent pattern recognition, clear explanations
Improvements: Could mention timing patterns

### STRUCT_002 - APPROVED WITH CHANGES
Scores: Tech 8/10, Practical 9/10, Regulatory 9/10, Overall 8/10
Strengths: Identified smurfing pattern well
Improvements: Should emphasize coordination aspect more

### STRUCT_003 - APPROVED
Scores: Tech 9/10, Practical 8/10, Regulatory 9/10, Overall 9/10
Strengths: Good handling of ambiguous case
Improvements: None major

## Recommendations

1. **Golden Dataset Updates**:
   - Add test case for timing pattern analysis
   - Include secondary typology detection case

2. **Prompt Improvements**:
   - Request specific dates when data available
   - Emphasize coordination in smurfing cases

3. **Next Review**:
   - Focus on layering cases
   - Test edge case handling
```

## Integration with Golden Dataset

Expert feedback updates the golden dataset:
- Scores below 7/10 → Investigate agent behavior
- Common issues → Update prompts or test cases
- New insights → Enhance expected outputs
- Patterns discovered → Add new test cases

## Frequency Recommendations

- **Weekly**: Quick review (1-2 cases) during active development
- **Before Release**: Comprehensive review (10+ cases)
- **Monthly**: Rotating category focus
- **After Prompt Changes**: Targeted review of affected cases

## Expert Review Guidelines

**As the reviewer, evaluate:**

1. **Correctness**: Is the AML analysis accurate?
2. **Completeness**: Does it miss important details?
3. **Actionability**: Can an analyst actually use this?
4. **Compliance**: Does it follow regulations?
5. **Trust**: Would you rely on this output?

**Be objective but constructive:**
- Point out both strengths and weaknesses
- Provide specific examples
- Suggest concrete improvements
- Consider real-world analyst needs

## Notes

- This is a manual process - requires human time and expertise
- Collect feedback systematically to improve system
- Use results to validate automated metrics
- Expert reviews are the gold standard for quality
