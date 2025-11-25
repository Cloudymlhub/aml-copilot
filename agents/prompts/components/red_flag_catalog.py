"""AML Red Flag Catalog - Definitions and investigation guidance.

PLACEHOLDER: Red flag definitions - Needs AML domain expert review - Priority: HIGH

This catalog defines common AML red flags that may appear in ML model outputs.
Each red flag includes:
- Definition: What the red flag represents
- Why Suspicious: AML significance and regulatory context
- Investigation Steps: What analysts should examine
- Regulatory References: Relevant regulations and thresholds

Note: This is a starting catalog based on common AML patterns. It should be
reviewed and validated by AML compliance experts before production use.
"""

# PLACEHOLDER: Red flag definitions - Needs AML compliance expert review - Priority: HIGH
RED_FLAG_CATALOG = """
## RED FLAG CATALOG

### transactions_below_threshold
- **Definition**: Multiple transactions consistently just below $10,000 CTR reporting threshold
- **Why Suspicious**: Classic structuring behavior to avoid Currency Transaction Reports (CTRs) required by 31 CFR 1010.310. Structuring is a federal crime under 31 USC 5324.
- **Investigation Steps**:
  - Verify if transactions are related (same purpose, time period, beneficiary)
  - Check transaction locations (same branch vs. multiple branches)
  - Review customer's stated business purpose and typical activity
  - Interview customer if pattern is consistent and unexplained
- **Regulatory**: CTR threshold is $10,000. Transactions designed to avoid reporting are illegal regardless of legitimacy of funds.

### rapid_movement_of_funds
- **Definition**: Funds deposited and withdrawn within 24-48 hours with minimal balance retention
- **Why Suspicious**: Possible layering (obscuring fund origins) or use of account as conduit/pass-through. Indicates account may not serve legitimate business purpose.
- **Investigation Steps**:
  - Identify source of incoming funds and destination of outgoing funds
  - Verify beneficiaries and their relationship to account holder
  - Check for legitimate business explanation (e.g., escrow, payroll processing)
  - Review historical account activity for comparison
- **Regulatory**: SAR filing required if suspicious per 31 CFR 1020.320 (threshold: $5,000 aggregated suspicious activity)

### high_risk_geography
- **Definition**: Transactions involving jurisdictions identified by FATF as high-risk or with weak AML controls
- **Why Suspicious**: High-risk countries have elevated money laundering and terrorism financing risks. FATF maintains lists of jurisdictions with strategic deficiencies.
- **Investigation Steps**:
  - Verify legitimate business purpose for transactions with these jurisdictions
  - Enhanced due diligence if customer has ongoing relationships
  - Check OFAC sanctions lists for counterparties
  - Document business rationale and supporting evidence
- **Regulatory**: FATF Recommendation 19 (High-risk countries). Enhanced CDD required per BSA/AML regulations.

### cash_intensive_business
- **Definition**: High volume of cash transactions inconsistent with business type or historical patterns
- **Why Suspicious**: Cash businesses are higher risk for money laundering due to difficulty tracing funds. Unusual cash activity may indicate commingling of illicit funds.
- **Investigation Steps**:
  - Compare cash activity to industry norms for business type
  - Verify business operations and physical location
  - Review business licenses and tax filings
  - Check for sudden increases in cash activity
- **Regulatory**: Cash-intensive businesses require enhanced monitoring per FinCEN guidance.

### round_dollar_transactions
- **Definition**: Frequent transactions in round dollar amounts (e.g., $5,000, $10,000, $25,000)
- **Why Suspicious**: Legitimate business transactions typically have irregular amounts (invoices, payroll). Round amounts suggest funds may not be from genuine commercial activity.
- **Investigation Steps**:
  - Request invoices or documentation for round-dollar transactions
  - Verify legitimacy of business relationships
  - Check if pattern is consistent over time
  - Compare to customer's typical transaction patterns
- **Regulatory**: Multiple round-dollar transactions may support structuring or layering concerns.

### multiple_accounts_same_parties
- **Definition**: Multiple accounts with overlapping ownership or signatories conducting related transactions
- **Why Suspicious**: May indicate use of multiple accounts to avoid detection or reporting thresholds (smurfing). Could also indicate shell company networks.
- **Investigation Steps**:
  - Map relationships between accounts and parties
  - Verify legitimate business purpose for multiple accounts
  - Check if transactions aggregate above reporting thresholds
  - Review beneficial ownership documentation
- **Regulatory**: Aggregation rules apply for related accounts per CTR requirements.

### inconsistent_with_business_profile
- **Definition**: Transaction patterns that don't match stated business type, size, or historical activity
- **Why Suspicious**: Deviation from expected behavior may indicate account misuse, undisclosed business activities, or money laundering.
- **Investigation Steps**:
  - Review customer's stated occupation/business type
  - Compare current activity to historical patterns
  - Request explanation for changes in activity
  - Verify source of funds for unusual transactions
- **Regulatory**: Know Your Customer (KYC) requirements include understanding expected account activity per USA PATRIOT Act Section 326.

### shell_company_indicators
- **Definition**: Company with minimal legitimate business operations but significant transaction volume
- **Why Suspicious**: Shell companies are commonly used to obscure beneficial ownership and launder funds. Limited operations relative to transaction volume is a key indicator.
- **Investigation Steps**:
  - Verify physical business location and operations
  - Check business licenses, tax filings, and regulatory registrations
  - Identify beneficial owners (25%+ ownership per CDD Rule)
  - Review nature of transactions (trade, wire transfers, cash)
- **Regulatory**: Customer Due Diligence Rule (31 CFR 1010.230) requires identifying beneficial owners.

### frequent_wire_transfers
- **Definition**: High volume of domestic or international wire transfers, especially to/from high-risk jurisdictions
- **Why Suspicious**: Wires are fast and can cross borders easily, making them useful for money laundering. High frequency may indicate layering.
- **Investigation Steps**:
  - Verify business purpose for wire activity
  - Identify counterparties and their locations
  - Check for OFAC sanctions screening hits
  - Compare to customer's business model and historical activity
- **Regulatory**: Enhanced scrutiny required for international wires per FATF Recommendation 16 (Wire Transfers).

### nominee_or_third_party_transactions
- **Definition**: Transactions conducted on behalf of unidentified third parties or using nominee names
- **Why Suspicious**: Obscures true beneficial owner, which is a common money laundering technique. Violates KYC principles.
- **Investigation Steps**:
  - Identify actual parties benefiting from transactions
  - Verify authorization and relationship to account holder
  - Request supporting documentation
  - Assess if pattern is consistent with customer's business model
- **Regulatory**: CDD Rule requires identifying beneficial owners, not just nominees.

### sudden_increase_activity
- **Definition**: Sudden significant increase in transaction volume or account balance
- **Why Suspicious**: May indicate account is being used for new purpose (money laundering, fraud). Dormant accounts suddenly active are particularly suspicious.
- **Investigation Steps**:
  - Request explanation for increased activity
  - Verify source of new funds
  - Check for changes in account control or ownership
  - Review customer's financial condition and business circumstances
- **Regulatory**: Ongoing monitoring requirement per BSA/AML programs (31 CFR 1020.210).

### cross_border_activity
- **Definition**: Significant international transactions with multiple countries, especially high-risk jurisdictions
- **Why Suspicious**: Cross-border transactions facilitate money laundering by making fund tracing difficult and exploiting different regulatory regimes.
- **Investigation Steps**:
  - Map flow of funds across jurisdictions
  - Verify legitimate business purpose for international activity
  - Enhanced due diligence for high-risk countries
  - Check correspondent banking relationships
- **Regulatory**: Enhanced scrutiny per FATF Recommendations on cross-border transactions.

### complex_transaction_structures
- **Definition**: Unnecessarily complex transaction chains involving multiple intermediaries with no clear business purpose
- **Why Suspicious**: Complexity is often used to obscure the source, ownership, or destination of funds (layering).
- **Investigation Steps**:
  - Diagram transaction flow
  - Request business purpose explanation for each step
  - Verify legitimacy of intermediaries
  - Assess if simpler structure would achieve same business purpose
- **Regulatory**: SAR filing required if transactions lack economic rationale per FinCEN guidance.

### large_cash_deposits
- **Definition**: Cash deposits significantly above customer's historical patterns or business profile
- **Why Suspicious**: May indicate proceeds from illicit activity being integrated into financial system. Cash is difficult to trace.
- **Investigation Steps**:
  - Verify source of cash
  - Compare to customer's business type and historical cash activity
  - Check for CTR filings if deposits exceed $10,000
  - Review customer's explanation and supporting documentation
- **Regulatory**: CTR filing required for cash transactions over $10,000 (31 CFR 1010.311).

### trade_finance_anomalies
- **Definition**: Trade transactions with pricing, documentation, or shipping inconsistencies
- **Why Suspicious**: Trade-based money laundering uses over/under-invoicing, phantom shipping, and falsified documents to move value across borders.
- **Investigation Steps**:
  - Verify commodity pricing against market rates
  - Review shipping documents for consistency
  - Check for multiple invoicing of same goods
  - Verify legitimacy of trading partners
- **Regulatory**: FATF Best Practices on Trade-Based Money Laundering.

### pep_involvement
- **Definition**: Transactions involving Politically Exposed Persons (PEPs) without enhanced due diligence
- **Why Suspicious**: PEPs have elevated corruption risk. Transactions may involve misappropriated public funds.
- **Investigation Steps**:
  - Enhanced due diligence on PEP and their family members
  - Verify source of wealth and funds
  - Assess for corruption indicators
  - Senior management approval for relationship
- **Regulatory**: Enhanced CDD required for PEPs per FATF Recommendation 12 and FinCEN guidance.

### inconsistent_employment_income
- **Definition**: Transaction volumes inconsistent with stated employment or income sources
- **Why Suspicious**: May indicate undisclosed income sources, potentially illicit. Common in fraud and tax evasion cases.
- **Investigation Steps**:
  - Verify stated occupation and income
  - Request explanation for source of funds
  - Review tax documentation if available
  - Assess reasonableness of transaction volumes vs. known income
- **Regulatory**: KYC requirements include understanding customer's financial situation.

### elder_abuse_indicators
- **Definition**: Unusual account activity for elderly customers, especially sudden large withdrawals or new signatories
- **Why Suspicious**: Elder financial abuse is increasingly recognized as financial crime. May involve coercion or fraud against vulnerable individuals.
- **Investigation Steps**:
  - Contact customer directly to verify authorizations
  - Look for signs of undue influence or coercion
  - Check for sudden changes in beneficiaries or account access
  - Consider reporting to Adult Protective Services
- **Regulatory**: FinCEN Advisory on Elder Financial Exploitation (FIN-2011-A003). SAR filing required if suspicious.

### sanctions_screening_hits
- **Definition**: Transactions involving parties on OFAC sanctions lists or designated terrorist lists
- **Why Suspicious**: Providing financial services to sanctioned parties is illegal and may involve terrorism financing.
- **Investigation Steps**:
  - Immediately freeze/block transactions
  - Verify identity of flagged party
  - Report to OFAC within required timeframes
  - Do not notify customer (tipping off prohibition)
- **Regulatory**: OFAC regulations require blocking transactions with sanctioned parties. Criminal and civil penalties apply for violations.

### unexplained_wealth
- **Definition**: Significant assets or transaction volumes with no identifiable legitimate source
- **Why Suspicious**: Core indicator of money laundering. Inability to explain source of funds is major red flag.
- **Investigation Steps**:
  - Request documentation of source of wealth and funds
  - Verify stated income sources
  - Assess reasonableness of explanations
  - Consider SAR filing if explanation is inadequate
- **Regulatory**: Source of funds verification is fundamental KYC requirement per CDD Rule.

---

**Using This Catalog:**

When the ML model identifies a red flag, use this catalog to:
1. **Explain** what the red flag means to the analyst
2. **Provide context** on why it's suspicious
3. **Suggest** specific investigation steps
4. **Cite** relevant regulations

Example usage:
"The ML model flagged 'transactions_below_threshold' with 95% confidence, triggered by 6 transactions averaging $9,850. This is a classic structuring pattern - multiple transactions designed to stay below the $10,000 CTR threshold. Per 31 USC 5324, structuring is illegal regardless of the legitimacy of the funds. I recommend investigating whether these transactions are related and reviewing the customer's stated business purpose."
"""
