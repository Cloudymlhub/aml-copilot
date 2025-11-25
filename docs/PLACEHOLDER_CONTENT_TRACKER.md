# Placeholder Content Tracker

This document tracks ALL placeholder content in the AML Copilot codebase that needs expert review, validation, or replacement before production deployment.

## Scope

This tracker covers:
1. **Mock Data**: Test fixtures, synthetic data, placeholder API responses
2. **Domain Knowledge**: Red flags, typologies, regulatory references (need expert review)
3. **Placeholder Logic**: Temporary implementations, simplified algorithms
4. **Configuration**: Default values that need production tuning

## Purpose

During development, we use placeholder content to:
- Enable rapid development without full infrastructure
- Test agent workflows with controlled scenarios
- Provide starting points for domain expert review and validation
- Demonstrate system capabilities with realistic examples

**CRITICAL**: All HIGH priority placeholders MUST be reviewed/replaced before production deployment.

## Priority Levels

- **HIGH**: Critical for production - security risk or compliance requirement
- **MEDIUM**: Important for full functionality - should be addressed before launch
- **LOW**: Nice to have - can be addressed post-launch if needed

---

## Placeholder Content Inventory

### 1. ML Model Outputs (HIGH Priority - Mock Data)

**Location**: Multiple files
- `tests/fixtures/ml_model_fixtures.py` - All ML scenarios
- `db/services/data_service.py:364-423` - `get_ml_model_output()` method
- `tools/ml_output_tools.py:1-148` - All ML output tools

**What's Mocked**:
- Daily risk score trends
- Feature values (transaction patterns, volumes)
- Red flag confidence scores
- Typology likelihood assessments
- Attribution chains (Typology → Red Flags → Features)

**Replacement Strategy**:
```python
# Current (MOCK):
from tests.fixtures import get_ml_scenario
ml_output = get_ml_scenario("structuring")

# Production:
from ml_service import MLModelClient
ml_client = MLModelClient(api_url=settings.ml_service_url)
ml_output = ml_client.get_risk_assessment(cif_no)
```

**Production Requirements**:
- ML model service API integration
- Feature store connection
- Real-time or near-real-time model predictions
- Model versioning and A/B testing support
- Fallback handling for service unavailability

---

### 2. AML Domain Knowledge (HIGH Priority - Needs Expert Review)

**Type**: Placeholder domain knowledge requiring validation

**Location**:
- `agents/prompts/components/red_flag_catalog.py:16-232` - Red flag definitions
- `agents/prompts/components/typology_library.py:16-275` - Typology descriptions
- `agents/prompts/components/regulatory_references.py:13-227` - Regulatory thresholds

**What's Placeholder**:
- Red flag catalog (based on common AML patterns, needs institution-specific review)
- Typology library (based on FATF guidance, needs validation)
- Regulatory references (based on current BSA/AML regulations, needs legal verification)

**Why This Matters**:
These are NOT mock data - they're real AML concepts. However, they are PLACEHOLDERS because:
- Need expert review to ensure accuracy and completeness
- Need customization for institution's specific risk profile
- Need legal validation of regulatory citations
- Need alignment with institution's policies and procedures

**Validation Requirements**:
- **REQUIRED**: AML compliance expert review
- **REQUIRED**: Legal/regulatory team approval
- **REQUIRED**: Cross-reference with current FinCEN guidance
- **REQUIRED**: Verify all regulatory citations (CFR sections, thresholds)

**Status**: Marked as `PLACEHOLDER` with comment: "Needs AML domain expert review"

**Review Strategy**:
1. Schedule review with AML compliance team
2. Validate all regulatory references against current law
3. Update typology library with institution-specific patterns
4. Add custom red flags for institution's risk profile
5. Implement version control for prompt components
6. Create audit trail for domain knowledge updates

---

### 3. Customer Data Generation (MEDIUM Priority)

**Location**: `data/mock_data.py:1-500+` (entire file)

**What's Mocked**:
- Customer profiles (names, DOB, countries, KYC status)
- Transaction histories with engineered patterns
- Alert generation based on scenarios
- Risk scoring logic

**Purpose**: Database seeding for development/testing

**Replacement Strategy**:
- Keep for development/staging environments
- Use anonymized production data for testing (with proper PII handling)
- Implement data masking for non-production environments

---

### 4. Database Connection (MEDIUM Priority)

**Location**: Various repository and service files

**What's Mocked**: Currently using real PostgreSQL, but mock connection logic may exist

**Status**: Database is real, but uses mock/seed data

**Production Requirements**:
- Production database credentials (via secrets manager)
- Connection pooling configuration
- Read replica setup for analytics
- Backup and disaster recovery
- Data retention policies

---

### 5. Redis Cache (LOW Priority)

**Location**:
- `db/services/cache_service.py`
- Dependency injection in services

**Current State**: Real Redis connection, but may have mock fallback

**Production Requirements**:
- Production Redis cluster
- Proper cache invalidation strategies
- TTL tuning based on data freshness requirements
- Monitoring and alerting

---

## Code Markers

All placeholder content is marked with one of these patterns:

### MOCK_DATA Marker
Use for synthetic/fake data that will be replaced:
```python
# MOCK_DATA: Brief description - Priority: HIGH/MEDIUM/LOW
```

Examples:
```python
# MOCK_DATA: ML model outputs from fixtures - Priority: HIGH
# MOCK_DATA: Synthetic customer data for testing - Priority: MEDIUM
# MOCK_DATA: Feature importance calculation - Priority: HIGH
```

### PLACEHOLDER Marker
Use for real content that needs expert review/validation:
```python
# PLACEHOLDER: Brief description - Needs [expert type] review - Priority: HIGH/MEDIUM/LOW
```

Examples:
```python
# PLACEHOLDER: Red flag definitions - Needs AML expert review - Priority: HIGH
# PLACEHOLDER: Regulatory thresholds - Needs legal verification - Priority: HIGH
# PLACEHOLDER: Typology library - Needs compliance validation - Priority: HIGH
```

### When to Use Which Marker

**MOCK_DATA**: Content that is fake/synthetic and will be completely replaced
- Test fixtures
- Synthetic database records
- Placeholder API responses
- Generated sample data

**PLACEHOLDER**: Content that is real but needs validation/customization
- Domain knowledge (red flags, typologies)
- Regulatory references
- Business rules
- Threshold configurations

---

## Search Commands

Find all placeholder content:
```bash
# Find all markers (both types)
grep -rE "(MOCK_DATA|PLACEHOLDER)" --include="*.py" .

# Find all MOCK_DATA markers
grep -r "MOCK_DATA" --include="*.py" .

# Find all PLACEHOLDER markers
grep -r "PLACEHOLDER" --include="*.py" .

# Find high priority items (any type)
grep -rE "(MOCK_DATA|PLACEHOLDER).*HIGH" --include="*.py" .

# Find items needing expert review
grep -r "Needs.*review" --include="*.py" .
```

Or use the slash command (once implemented):
```
/check-placeholders [priority]
```

---

## Pre-Production Checklist

Before deploying to production, verify:

### Critical (Must Complete)

- [ ] All HIGH priority mock data identified
- [ ] ML model service integration complete and tested
- [ ] AML domain knowledge reviewed by compliance experts
- [ ] Regulatory references validated by legal team
- [ ] All `MOCK_DATA: HIGH` comments resolved
- [ ] Production database configured
- [ ] Security review completed

### Important (Should Complete)

- [ ] All MEDIUM priority mock data addressed
- [ ] Feature store integration tested
- [ ] Monitoring and alerting configured
- [ ] Fallback handling for service failures tested
- [ ] Performance testing with production data volumes

### Nice to Have (Can Defer)

- [ ] LOW priority mock data replaced
- [ ] Enhanced logging implemented
- [ ] A/B testing framework setup

---

## Mock Data Replacement Process

### Step 1: Identify Mock Data

Use grep or the check-mocks command to find all instances

### Step 2: Assess Priority

Determine if HIGH, MEDIUM, or LOW based on:
- Security implications
- Compliance requirements
- Functional impact
- User experience

### Step 3: Design Production Implementation

- Define API contracts
- Identify dependencies
- Plan error handling
- Design fallback strategies

### Step 4: Implement and Test

- Write production code
- Add comprehensive tests
- Performance test with realistic volumes
- Security review

### Step 5: Deploy and Monitor

- Gradual rollout (canary deployment)
- Monitor error rates and performance
- Have rollback plan ready
- Document changes

### Step 6: Remove Mock Code

- Delete mock implementations
- Remove MOCK_DATA markers
- Update documentation
- Archive fixtures for testing

---

## Domain Expert Review Requirements

### AML Compliance Review

**Required for**:
- Red flag catalog
- Typology library
- SAR narrative templates
- Disposition criteria

**Reviewers**: AML Compliance Officer, BSA Officer

**Review Checklist**:
- [ ] Red flags match institution's risk assessment
- [ ] Typologies cover relevant threat scenarios
- [ ] Investigation steps are practical and complete
- [ ] Terminology is consistent with industry standards

### Legal/Regulatory Review

**Required for**:
- All regulatory references
- Threshold amounts
- Filing deadlines
- Regulatory citations

**Reviewers**: General Counsel, Compliance Legal Team

**Review Checklist**:
- [ ] All CFR citations are current and accurate
- [ ] Dollar thresholds are correct
- [ ] Deadlines match current regulations
- [ ] Penalties and consequences are accurate

### IT Security Review

**Required for**:
- ML model integration
- Data access patterns
- API authentication
- PII handling

**Reviewers**: CISO, Security Architecture Team

**Review Checklist**:
- [ ] No credentials in code
- [ ] Proper authentication/authorization
- [ ] Data encryption in transit and at rest
- [ ] Audit logging implemented

---

## Monitoring Mock Data in Production

**Never allow mock data in production!**

Implement these safeguards:

### 1. Environment Checks

```python
if settings.environment == "production":
    if "MOCK_FIXTURE" in data_source:
        raise RuntimeError("Mock data detected in production!")
```

### 2. Logging

All mock data access should log warnings:
```python
logger.warning(
    "Using mock data: %s (environment: %s)",
    mock_type,
    settings.environment
)
```

### 3. Metrics

Track mock data usage:
- Count of mock data accesses
- Alert if mock data accessed in production
- Dashboard showing mock data usage by environment

### 4. CI/CD Checks

```bash
# Pre-deployment check
if [ "$ENVIRONMENT" == "production" ]; then
    echo "Checking for mock data markers..."
    if grep -r "MOCK_DATA.*HIGH" --include="*.py" .; then
        echo "ERROR: High-priority mock data found!"
        exit 1
    fi
fi
```

---

## Contact

For questions about mock data replacement:
- **ML Integration**: ML Engineering Team
- **AML Domain Knowledge**: AML Compliance Officer
- **Regulatory Content**: Legal/Compliance Team
- **Technical Implementation**: Engineering Lead

---

## Version History

- **2024-01**: Initial mock data inventory created
- **2024-01**: Added ML model output fixtures
- **2024-01**: Added modular prompt components with domain knowledge

---

## Related Documentation

- [Architecture Overview](./ARCHITECTURE.md)
- [Agent Configuration](./AGENT_ARCHITECTURE_REVISED.md)
- [Compliance Expert Prompt Design](../agents/prompts/components/README.md)
- [Testing Strategy](./TESTING_STRATEGY.md)
