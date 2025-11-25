"""AML Typology Library - Major money laundering patterns and methods.

PLACEHOLDER: Typology definitions - Needs AML compliance expert review - Priority: HIGH

This library describes common AML typologies (money laundering patterns) that
may appear in ML model outputs. Each typology includes:
- Pattern: How the typology typically manifests
- Common Methods: Specific techniques used
- Indicators: Red flags and features that suggest this typology
- FATF References: Relevant international standards

Note: This is a starting library based on FATF guidance and common patterns.
It should be reviewed and validated by AML compliance experts before production use.
"""

# PLACEHOLDER: Typology definitions - Needs AML compliance expert review - Priority: HIGH
TYPOLOGY_LIBRARY = """
## AML TYPOLOGY LIBRARY

### Structuring / Smurfing
- **Pattern**: Breaking large amounts into smaller transactions to avoid reporting thresholds
- **Common Methods**:
  - Multiple deposits just below $10,000 CTR threshold
  - Using multiple individuals to conduct transactions (smurfing)
  - Spreading transactions across multiple branches or days
  - Sequential transactions at different institutions
- **Key Indicators**:
  - Consistent amounts just under reporting limits
  - High frequency of near-threshold transactions
  - Use of multiple accounts or individuals
  - Transactions at multiple locations
- **FATF Reference**: Recommendation 10 (Record-keeping), 20 (Reporting of suspicious transactions)
- **Regulatory Context**: Structuring is a federal crime under 31 USC 5324, regardless of whether underlying funds are legitimate

### Layering
- **Pattern**: Complex series of transactions to obscure the origin of funds
- **Common Methods**:
  - Rapid movement of funds through multiple accounts
  - International wire transfers through multiple jurisdictions
  - Use of shell companies and nominees
  - Purchase and sale of high-value assets
  - Loans backed by illicit funds
- **Key Indicators**:
  - Unnecessary transaction complexity
  - No clear business purpose
  - Rapid in-and-out movement
  - Multiple jurisdictions involved
  - Use of intermediaries with no apparent role
- **FATF Reference**: Recommendation 11 (Unusual transactions), 16 (Wire transfers)
- **Regulatory Context**: Layering separates proceeds from their criminal source, making detection difficult

### Trade-Based Money Laundering (TBML)
- **Pattern**: Using legitimate trade transactions to disguise movement of illicit funds
- **Common Methods**:
  - Over-invoicing of goods (moving value out)
  - Under-invoicing of goods (moving value in)
  - Multiple invoicing of same shipment
  - Phantom shipping (goods never delivered)
  - Falsified quality/quantity descriptions
  - Misrepresentation of commodity type
- **Key Indicators**:
  - Prices significantly different from market rates
  - Commodities inconsistent with business type
  - High-risk jurisdictions involved
  - Documentation inconsistencies
  - Complex intermediary chains
  - Circular trading patterns
- **FATF Reference**: Best Practices on Trade-Based Money Laundering (2020)
- **Regulatory Context**: TBML is particularly difficult to detect due to legitimate trade volume

### Integration
- **Pattern**: Reintroducing laundered funds into the legitimate economy
- **Common Methods**:
  - Investment in legitimate businesses
  - Real estate purchases
  - High-value asset purchases (art, jewelry, vehicles)
  - Commingling with legitimate business revenue
  - Loans or investments appearing legitimate
- **Key Indicators**:
  - Large cash deposits in business accounts
  - Purchases inconsistent with known income
  - Sudden business expansion without clear funding source
  - Investment in cash-intensive businesses
- **FATF Reference**: Recommendation 1 (Risk assessment)
- **Regulatory Context**: Integration is the final stage where laundered funds become difficult to distinguish from legitimate wealth

### Shell Company / Front Company
- **Pattern**: Using companies with no legitimate business operations to move illicit funds
- **Common Methods**:
  - Minimal or no business operations
  - Round-dollar wire transfers with vague descriptions
  - Opaque ownership structures
  - Use of nominee directors/officers
  - Quick incorporation and dissolution
  - Multiple companies with overlapping principals
- **Key Indicators**:
  - High transaction volume vs. minimal operations
  - No employees or physical location
  - Round-dollar transactions
  - Inconsistent with stated business purpose
  - Bearer shares or complex ownership
- **FATF Reference**: Recommendation 24 (Transparency of legal persons), 25 (Beneficial ownership)
- **Regulatory Context**: CDD Rule (31 CFR 1010.230) requires identifying beneficial owners (25%+ ownership)

### Cuckoo Smurfing
- **Pattern**: Using innocent third-party accounts to move illicit funds across borders
- **Common Methods**:
  - Identifying legitimate wire transfer expectations
  - Depositing illicit cash into third party's account
  - Arranging corresponding wire transfer abroad
  - Third party unaware their account was used
- **Key Indicators**:
  - Unexpected cash deposits in accounts
  - Deposits that match expected wire amounts
  - International nexus with high-risk jurisdictions
  - Customer unaware of source of funds
- **FATF Reference**: Recommendation 16 (Wire transfers)
- **Regulatory Context**: Exploits legitimate trade and migration patterns

### Black Market Peso Exchange (BMPE)
- **Pattern**: Converting drug proceeds without formal banking system, common in Latin American drug trade
- **Common Methods**:
  - Peso brokers purchase US dollars from drug traffickers at discount
  - Dollars deposited in US accounts controlled by broker
  - Colombian importers buy dollars from broker to pay for goods
  - US exporters receive payment from broker's US accounts
- **Key Indicators**:
  - Third-party payments for goods shipped to South America
  - Payments from unrelated parties
  - High-volume trade with Colombia, Mexico, other high-risk areas
  - Round-dollar payments for specific goods
- **FATF Reference**: FATF Typologies on BMPE
- **Regulatory Context**: Major method for laundering drug proceeds from US

### Real Estate Money Laundering
- **Pattern**: Using real estate transactions to launder illicit funds
- **Common Methods**:
  - All-cash purchases by shell companies
  - Purchases through series of intermediaries
  - Rapid buy-sell cycles
  - Renovation with illicit funds
  - Rental income mixing legitimate and illicit cash
- **Key Indicators**:
  - All-cash purchases above typical thresholds
  - Purchases by shell companies or foreign entities
  - Prices significantly above/below market value
  - Frequent property flipping
  - Beneficial owners unclear
- **FATF Reference**: Recommendation 22 (DNFBPs - real estate agents)
- **Regulatory Context**: FinCEN Geographic Targeting Orders (GTOs) require reporting of high-value cash real estate purchases

### Casino / Gambling
- **Pattern**: Using casinos to obscure source of funds
- **Common Methods**:
  - Buying chips with cash, minimal gambling, cashing out
  - Structured chip purchases below reporting thresholds
  - Using gambling winnings as source of funds explanation
  - Loan-sharking through casinos
- **Key Indicators**:
  - Large cash chip purchases with minimal play
  - Structured transactions at casinos
  - "Winnings" without corresponding gambling activity
  - Multiple trips to casino with large cash
- **FATF Reference**: Recommendation 28 (Casinos)
- **Regulatory Context**: Casinos are subject to BSA/AML requirements

### Cryptocurrency / Virtual Assets
- **Pattern**: Using cryptocurrencies and virtual assets to move value while obscuring sources
- **Common Methods**:
  - Converting cash to crypto to hide source
  - Layering through multiple wallets/exchanges
  - Privacy coins (Monero, Zcash) for anonymity
  - Crypto ATMs for cash conversion
  - DeFi platforms to avoid KYC
- **Key Indicators**:
  - Large fiat-to-crypto conversions
  - Use of mixers/tumblers
  - Privacy-enhanced cryptocurrencies
  - Offshore or unregulated exchanges
  - Rapid conversion between assets
- **FATF Reference**: Recommendation 15 (New technologies), Updated Guidance on Virtual Assets (2021)
- **Regulatory Context**: FinCEN applies BSA to virtual currency exchangers and administrators

### Professional Money Laundering Networks
- **Pattern**: Third-party money laundering services provided to multiple criminal organizations
- **Common Methods**:
  - Operating network of money brokers
  - Using corrupt professionals (lawyers, accountants)
  - Trade-based laundering infrastructure
  - Network of shell companies and bank accounts
  - Bulk cash smuggling operations
- **Key Indicators**:
  - Multiple unrelated clients with similar transaction patterns
  - Professional facilitators (gatekeepers) involved
  - Sophisticated methods suggesting expertise
  - Scale of operations suggests organized network
- **FATF Reference**: FATF Report on Professional Money Laundering (2018)
- **Regulatory Context**: Increasingly recognized as major ML threat

### Cash Smuggling / Bulk Cash
- **Pattern**: Physical transport of currency across borders to avoid detection
- **Common Methods**:
  - Concealment in luggage, vehicles, containers
  - Use of couriers and mules
  - Structured cash movements below reporting thresholds
  - Trade goods with hidden cash compartments
- **Key Indicators**:
  - Large cash deposits with no clear source
  - Multiple currency declarations just below thresholds
  - Travel to/from high-risk jurisdictions
  - Frequent cash courier activity
- **FATF Reference**: Recommendation 32 (Cash couriers)
- **Regulatory Context**: FBAR reporting required for cross-border cash movements over $10,000

### Human Trafficking / Modern Slavery
- **Pattern**: Financial patterns associated with human trafficking operations
- **Common Methods**:
  - Multiple low-value transfers to victims
  - Victims' accounts controlled by traffickers
  - Cash-intensive businesses as fronts
  - Rapid movement of funds
  - Exploitation of vulnerable individuals
- **Key Indicators**:
  - Account activity inconsistent with victim's profile
  - Multiple victims linked to same controller
  - Large cash deposits by low-income individuals
  - Evidence of coercion or control
  - Inconsistent explanations for account activity
- **FATF Reference**: FATF Report on Human Trafficking (2018)
- **Regulatory Context**: FinCEN guidance on human trafficking financial indicators

### Terrorism Financing
- **Pattern**: Funding terrorist organizations or activities
- **Common Methods**:
  - Small-value transfers to high-risk regions
  - Charitable organizations as fronts
  - Cash couriers and hawala
  - Trade-based value transfer
  - Self-funding by radicalized individuals
- **Key Indicators**:
  - Transfers to countries with terrorist activity
  - Links to designated terrorist organizations
  - Fundraising inconsistent with stated charitable purpose
  - Small transactions to multiple high-risk destinations
- **FATF Reference**: Recommendations on Terrorism Financing
- **Regulatory Context**: USA PATRIOT Act Section 314(a) information sharing; Heightened scrutiny required

### Hawala / Alternative Remittance
- **Pattern**: Using informal value transfer systems to move funds outside banking system
- **Common Methods**:
  - Offsetting debts between hawala operators
  - Minimal formal records
  - Trust-based systems within communities
  - Often legitimate but can facilitate ML
- **Key Indicators**:
  - Payments to/from money services businesses
  - Remittances inconsistent with known relationships
  - High-volume activity through MSBs
  - Destinations in countries with large diaspora populations
- **FATF Reference**: Recommendation 14 (Money value transfer services)
- **Regulatory Context**: Unlicensed MSBs are illegal; Licensed MSBs must have AML programs

---

**Using This Library:**

When the ML model identifies a typology, use this library to:
1. **Explain** the pattern to the analyst
2. **Connect** red flags and features to the typology
3. **Provide context** on how this typology works
4. **Cite** relevant FATF standards

Example usage:
"The ML model indicates an 85% likelihood of structuring, supported by the 'transactions_below_threshold' red flag (95%). Structuring involves breaking large amounts into smaller transactions to avoid the $10,000 CTR reporting threshold - exactly what we see here with 6 transactions averaging $9,850. This is a common pattern where individuals attempt to avoid regulatory reporting while conducting high-volume cash activity."
"""
