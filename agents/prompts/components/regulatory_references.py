"""Regulatory References - BSA/AML regulations, thresholds, and requirements.

PLACEHOLDER: Regulatory references - Needs legal/compliance verification - Priority: HIGH

This module contains key BSA/AML regulatory requirements, thresholds, and
deadlines that analysts need to reference during investigations.

Note: While these are based on actual regulations, they should be verified
by compliance/legal teams and kept updated with regulatory changes.
"""

# PLACEHOLDER: Regulatory thresholds - Needs legal/compliance verification - Priority: HIGH
REGULATORY_REFERENCES = """
## REGULATORY REFERENCES

### Key Reporting Thresholds

**Currency Transaction Reports (CTR)**
- **Threshold**: $10,000 in currency (cash) in a single day
- **Regulation**: 31 CFR 1010.311
- **Deadline**: File within 15 days of transaction
- **Scope**: Single transaction or aggregate of related transactions
- **Note**: Structuring to avoid CTRs is illegal per 31 USC 5324

**Suspicious Activity Reports (SAR)**
- **Threshold**: $5,000 or more (aggregated) of suspicious activity
- **Special Threshold**: $2,000 for certain violations (e.g., BSA violations, structuring)
- **Regulation**: 31 CFR 1020.320
- **Deadline**: File within 30 calendar days of initial detection (60 days if no suspect identified)
- **Scope**: Known or suspected federal crimes, BSA violations, transactions with no apparent lawful purpose
- **Critical**: No customer notification allowed (tipping off prohibition)

**Monetary Instrument Log (MIL)**
- **Threshold**: $3,000 to $10,000 in monetary instruments (cashier's checks, money orders, traveler's checks)
- **Regulation**: 31 CFR 1010.415
- **Purpose**: Track purchases that might be structured below CTR threshold
- **Scope**: Sold for currency, not checks

**Funds Transfer Recordkeeping**
- **Threshold**: $3,000 or more for funds transfers
- **Regulation**: 31 CFR 1010.410(e)
- **Purpose**: Recordkeeping and travel rule compliance
- **Scope**: Both domestic and international

**Foreign Bank Account Reporting (FBAR)**
- **Threshold**: Aggregate foreign accounts exceeding $10,000 at any time during year
- **Regulation**: 31 CFR 1010.350
- **Deadline**: April 15 (automatically extended to October 15)
- **Criminal Penalties**: Willful violations can result in fines and imprisonment

**FinCEN Form 8300**
- **Threshold**: $10,000 or more in cash in trade or business
- **Regulation**: 26 USC 6050I, 31 USC 5331
- **Deadline**: 15 days from receipt
- **Scope**: Non-financial businesses receiving large cash payments

---

### Customer Due Diligence (CDD) Requirements

**Customer Identification Program (CIP)**
- **Regulation**: 31 CFR 1020.220 (USA PATRIOT Act Section 326)
- **Requirements**:
  - Name
  - Date of birth (for individuals)
  - Address
  - Identification number (SSN, EIN, passport, etc.)
- **Verification**: Documents, non-documentary methods, or combination
- **Risk-Based**: Higher-risk customers require enhanced verification

**Beneficial Ownership Rule**
- **Regulation**: 31 CFR 1010.230
- **Threshold**: 25% ownership triggers identification requirement
- **Requirements**: Identify individuals who:
  - Own 25% or more (ownership prong)
  - Control the entity (control prong - always required)
- **Scope**: Legal entity customers (not individuals, publicly traded companies, or government entities)
- **Effective Date**: May 11, 2018

**Enhanced Due Diligence (EDD)**
- **Required For**:
  - Politically Exposed Persons (PEPs)
  - High-risk customers
  - Correspondent banking relationships
  - Private banking accounts (>$1 million)
- **Regulation**: 31 CFR 1010.610 (correspondent accounts), 1010.620 (private banking)
- **Requirements**:
  - Source of wealth and funds
  - Purpose and nature of relationship
  - Enhanced monitoring
  - Senior management approval

---

### AML Program Requirements

**BSA/AML Compliance Program**
- **Regulation**: 31 CFR 1020.210
- **Required Elements**:
  - Internal policies, procedures, and controls
  - Designated compliance officer
  - Ongoing training program
  - Independent audit function
- **Risk Assessment**: Must be based on institution's risk profile

**Ongoing Monitoring**
- **Requirement**: Monitor transactions to identify and report suspicious activity
- **Risk-Based**: Monitoring intensity based on customer risk rating
- **Includes**:
  - Transaction monitoring systems
  - Alert investigation and dispositioning
  - SAR filing decisions
  - Periodic customer reviews

---

### OFAC and Sanctions

**Office of Foreign Assets Control (OFAC)**
- **Requirement**: Screen customers and transactions against SDN (Specially Designated Nationals) list
- **Prohibition**: No transactions with sanctioned parties
- **Blocking**: Must block/freeze assets of sanctioned parties
- **Reporting**: Report blocked transactions to OFAC
- **Deadline**: Block immediately, report within 10 days
- **Penalties**: Civil and criminal penalties for violations

**Sanctioned Jurisdictions**
- **Examples**: Iran, North Korea, Syria, Cuba, Russia (sector-specific), Venezuela (sector-specific)
- **Requirements**: Enhanced due diligence, possible prohibition on transactions
- **Updates**: Sanctions programs change frequently - check OFAC website

---

### FATF Recommendations

**Financial Action Task Force (FATF)**
- **40 Recommendations**: International standards for AML/CFT
- **High-Risk Jurisdictions**: Countries with strategic AML deficiencies
- **Call for Action**: Countries requiring countermeasures
- **Monitoring**: Gray list and black list published regularly

**Key FATF Recommendations**:
- **Recommendation 10**: Customer due diligence
- **Recommendation 11**: Record-keeping (5 years minimum)
- **Recommendation 12**: Politically exposed persons
- **Recommendation 13**: Correspondent banking
- **Recommendation 16**: Wire transfers (Travel Rule)
- **Recommendation 20**: Reporting suspicious transactions
- **Recommendation 24-25**: Beneficial ownership transparency

---

### Record Retention

**General Rule**
- **Period**: 5 years minimum
- **Applies To**:
  - Customer identification records
  - Transaction records
  - SARs and supporting documentation
  - CTRs and supporting documentation
  - AML training records
- **Regulation**: 31 CFR 1010.430

---

### Information Sharing

**FinCEN 314(a)**
- **Purpose**: Law enforcement requests for information
- **Regulation**: USA PATRIOT Act Section 314(a)
- **Response**: Must search records and respond within designated timeframe
- **Confidentiality**: Subject list must be kept confidential

**FinCEN 314(b)**
- **Purpose**: Voluntary information sharing between financial institutions
- **Regulation**: USA PATRIOT Act Section 314(b)
- **Protection**: Safe harbor from liability for shared information
- **Registration**: Must register with FinCEN to participate

---

### Training Requirements

**BSA/AML Training**
- **Frequency**: Ongoing (typically annual minimum)
- **Scope**: All appropriate personnel
- **Content**:
  - BSA/AML requirements
  - Red flags and typologies
  - Reporting obligations
  - Institution's policies and procedures
- **Documentation**: Training records must be maintained

---

### Penalties

**Criminal Penalties**
- **BSA Violations**: Up to $500,000 or 10 years imprisonment (or both)
- **Structuring**: Up to $500,000 or 5 years imprisonment (or both)
- **Willful FBAR Violations**: Up to $250,000 or 5 years imprisonment (or both)

**Civil Penalties**
- **BSA Violations**: Up to $100,000 per violation
- **FBAR Violations**: Up to $10,000 per non-willful violation; up to greater of $100,000 or 50% of account balance for willful violations
- **CDD Violations**: Up to $25,000 per violation

**Regulatory Actions**
- Cease and desist orders
- Removal of officers/directors
- Termination of deposit insurance
- Criminal referrals

---

**Using These References:**

When investigating alerts:
1. **Cite specific regulations** in your analysis
2. **Apply correct thresholds** for reporting determinations
3. **Note deadlines** when SAR filing is recommended
4. **Consider penalties** when assessing risk of non-compliance

Example usage:
"This pattern of 6 transactions averaging $9,850 appears to be structuring, which violates 31 USC 5324. The aggregate amount of $59,100 exceeds the $5,000 SAR threshold (31 CFR 1020.320), requiring SAR filing within 30 days of initial detection. Structuring is a federal crime regardless of whether the underlying funds are legitimate."
"""
