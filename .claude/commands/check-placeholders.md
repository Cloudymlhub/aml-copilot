Search the codebase for all placeholder content (MOCK_DATA and PLACEHOLDER markers) and provide a comprehensive inventory.

## Task

1. Run the placeholder check script or search directly
2. Categorize findings by priority (HIGH, MEDIUM, LOW)
3. Categorize by type (MOCK_DATA vs PLACEHOLDER)
4. Provide file locations and descriptions
5. Give actionable next steps

## Search Commands

Use these patterns to find all placeholder content:

```bash
# Find all markers (comprehensive)
grep -rE "(MOCK_DATA|PLACEHOLDER)" --include="*.py" .

# By priority
grep -rE "(MOCK_DATA|PLACEHOLDER).*HIGH" --include="*.py" .
grep -rE "(MOCK_DATA|PLACEHOLDER).*MEDIUM" --include="*.py" .
grep -rE "(MOCK_DATA|PLACEHOLDER).*LOW" --include="*.py" .

# By type
grep -r "MOCK_DATA" --include="*.py" .
grep -r "PLACEHOLDER" --include="*.py" .

# Items needing expert review
grep -r "Needs.*review" --include="*.py" .
```

## Output Format

Present results like this:

```
PLACEHOLDER CONTENT INVENTORY
==============================

HIGH PRIORITY (Critical for Production)
----------------------------------------
1. agents/prompts/components/red_flag_catalog.py
   Red flag definitions - Needs AML compliance expert review

2. agents/prompts/components/typology_library.py
   Typology definitions - Needs AML compliance expert review

3. agents/prompts/components/regulatory_references.py
   Regulatory thresholds - Needs legal/compliance verification

4. tools/ml_output_tools.py
   ML model outputs from fixtures

5. db/services/data_service.py
   ML model output retrieval (uses fixtures)

MEDIUM PRIORITY
---------------
1. data/mock_data.py
   Synthetic customer data for testing

LOW PRIORITY
------------
(None currently)

SUMMARY
-------
Total markers: 19
High: 13 | Medium: 6 | Low: 0

By Type:
- Mock Data (will be replaced): 11
- Placeholders (need expert review): 8

NEXT STEPS
----------
⚠️  13 HIGH priority items require attention before production:

For Mock Data (11 items):
1. Integrate with ML model service
2. Configure production data sources
3. Replace fixture data with real API calls

For Placeholders (8 items):
1. Schedule AML compliance expert review for:
   - Red flag catalog
   - Typology library
2. Schedule legal/regulatory review for:
   - Regulatory references
3. Customize for institution's risk profile

EXPERT REVIEW REQUIREMENTS
---------------------------
- AML Compliance Officer: Review red flags and typologies
- Legal/Regulatory Team: Verify all regulatory citations
- IT Security: Review ML service integration approach

See docs/PLACEHOLDER_CONTENT_TRACKER.md for complete details.
```

## Context

- **MOCK_DATA**: Synthetic/fake data that will be completely replaced
  - Test fixtures
  - Placeholder API responses
  - Generated sample data

- **PLACEHOLDER**: Real content that needs expert review/validation
  - Domain knowledge (red flags, typologies, regulations)
  - Business rules
  - Configuration values

## Priority Definitions

- **HIGH**: Security risk or compliance requirement - must fix before production
- **MEDIUM**: Important for functionality - should address before launch
- **LOW**: Nice to have - can defer post-launch

## Related Documentation

Refer to these for additional context:
- `docs/PLACEHOLDER_CONTENT_TRACKER.md` - Complete placeholder documentation
- `tests/fixtures/ml_model_fixtures.py` - ML model test scenarios
- `agents/prompts/components/` - Domain knowledge components

## Production Readiness Check

If this is a pre-deployment check, also verify:
1. ✓ All HIGH priority items addressed
2. ✓ Domain knowledge reviewed by experts
3. ✓ ML service integration complete
4. ✓ Production database configured
5. ✓ No placeholder content in production code paths
