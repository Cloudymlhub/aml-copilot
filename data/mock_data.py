"""Generate realistic mock AML data with engineered features.

MOCK_DATA: Entire file generates synthetic data for development/testing - Priority: MEDIUM

This module creates realistic but fake customer profiles, transactions, and alerts
for database seeding during development. Should NOT be used in production.

Production Strategy:
- Keep for development/staging environments
- Use anonymized production data for testing (with proper PII handling)
- Implement data masking for non-production environments
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from faker import Faker
import psycopg2
from psycopg2.extras import execute_batch

from config.settings import settings


# Initialize Faker
fake = Faker()

# AML-specific constants
HIGH_RISK_COUNTRIES = ["AFG", "IRN", "PRK", "SYR", "YEM", "MMR", "CUB", "SDN"]
TRANSACTION_TYPES = ["deposit", "withdrawal", "transfer", "wire", "check", "cash"]
CHANNELS = ["online", "atm", "branch", "mobile", "phone"]
ALERT_TYPES = [
    "structuring",
    "smurfing",
    "unusual_activity",
    "high_risk_country",
    "rapid_movement",
    "round_dollar_transactions",
    "velocity_spike",
]
INDUSTRIES = ["technology", "finance", "retail", "healthcare", "manufacturing", "real_estate", "hospitality"]
OCCUPATIONS = ["engineer", "doctor", "lawyer", "accountant", "manager", "consultant", "entrepreneur", "analyst"]


class AMLDataGenerator:
    """Generate realistic AML compliance mock data."""

    def __init__(self, num_customers: int = 100, transactions_per_customer: int = 50):
        """Initialize generator.

        Args:
            num_customers: Number of customers to generate
            transactions_per_customer: Average transactions per customer
        """
        self.num_customers = num_customers
        self.transactions_per_customer = transactions_per_customer
        self.customers: List[Dict[str, Any]] = []
        self.transactions: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []

    def generate_customer(self, customer_id: int, risk_profile: str = "low") -> Dict[str, Any]:
        """Generate a single customer with risk profile.

        Args:
            customer_id: Customer database ID
            risk_profile: 'low', 'medium', 'high', 'critical'
        """
        cif_no = f"C{customer_id:06d}"

        # Adjust country based on risk profile
        if risk_profile == "critical" or (risk_profile == "high" and random.random() > 0.7):
            country = random.choice(HIGH_RISK_COUNTRIES)
        else:
            country = fake.country_code(representation="alpha-3")

        # KYC status
        kyc_statuses = ["verified", "pending", "expired", "rejected"]
        kyc_weights = [0.85, 0.08, 0.05, 0.02] if risk_profile == "low" else [0.60, 0.20, 0.15, 0.05]
        kyc_status = random.choices(kyc_statuses, weights=kyc_weights)[0]

        # Risk score based on profile
        risk_score_ranges = {
            "low": (10, 40),
            "medium": (40, 70),
            "high": (70, 85),
            "critical": (85, 99)
        }
        risk_score = random.uniform(*risk_score_ranges.get(risk_profile, (10, 40)))

        return {
            "cif_no": cif_no,
            "name": fake.name(),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80),
            "country": country,
            "kyc_status": kyc_status,
            "account_opened_date": fake.date_between(start_date="-5y", end_date="today"),
            "occupation": random.choice(OCCUPATIONS),
            "industry": random.choice(INDUSTRIES),
            "risk_score": round(risk_score, 2),
        }

    def generate_transactions(self, customer_id: int, cif_no: str, risk_profile: str) -> List[Dict[str, Any]]:
        """Generate transactions for a customer.

        Args:
            customer_id: Customer database ID
            cif_no: Customer CIF number
            risk_profile: Customer risk profile
        """
        transactions = []

        # Number of transactions varies by risk profile
        if risk_profile == "critical":
            num_txns = random.randint(100, 200)
        elif risk_profile == "high":
            num_txns = random.randint(50, 100)
        else:
            num_txns = random.randint(20, 60)

        now = datetime.now()

        for i in range(num_txns):
            # Generate transaction date (weighted towards recent)
            days_ago = int(random.expovariate(1/60))  # Exponential distribution, avg 60 days
            days_ago = min(days_ago, 180)  # Cap at 180 days
            txn_date = now - timedelta(days=days_ago)

            # Amount varies by risk profile
            if risk_profile in ["high", "critical"] and random.random() > 0.7:
                # High-risk customers have some large transactions
                amount = Decimal(str(round(random.uniform(50000, 500000), 2)))
            else:
                amount = Decimal(str(round(random.uniform(100, 50000), 2)))

            # Round amount flag (structuring indicator)
            is_round_amount = (float(amount) % 1000 == 0) and random.random() > 0.7

            # Transaction type and channel
            txn_type = random.choice(TRANSACTION_TYPES)
            channel = random.choice(CHANNELS)

            # Cash transaction (risk indicator)
            is_cash = (txn_type in ["cash", "deposit", "withdrawal"] and
                      channel in ["atm", "branch"] and random.random() > 0.8)

            # International transaction
            counterparty_country = random.choice(HIGH_RISK_COUNTRIES) if random.random() > 0.9 else fake.country_code()
            is_international = counterparty_country != "USA"
            is_high_risk_country = counterparty_country in HIGH_RISK_COUNTRIES

            # Structuring (multiple similar amounts in short time)
            is_structured = (is_round_amount and float(amount) < 10000 and
                           risk_profile in ["high", "critical"] and random.random() > 0.85)

            transactions.append({
                "transaction_id": f"TXN{customer_id:06d}{i:06d}",
                "customer_id": customer_id,
                "amount": amount,
                "currency": "USD",
                "transaction_date": txn_date,
                "transaction_type": txn_type,
                "channel": channel,
                "counterparty_name": fake.company(),
                "counterparty_account": fake.iban(),
                "counterparty_country": counterparty_country,
                "counterparty_bank": fake.company(),
                "is_cash_transaction": is_cash,
                "is_round_amount": is_round_amount,
                "is_high_risk_country": is_high_risk_country,
                "is_structured": is_structured,
                "is_international": is_international,
                "description": f"{txn_type.title()} transaction",
            })

        return transactions

    def calculate_customer_features(self, customer_id: int, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate engineered features for a customer.

        Args:
            customer_id: Customer database ID
            transactions: List of customer transactions

        Returns:
            Dict of calculated features
        """
        now = datetime.now()
        features = {}

        # Helper to filter transactions by time window
        def filter_by_window(start_days: int, end_days: int) -> List[Dict]:
            start_date = now - timedelta(days=end_days)
            end_date = now - timedelta(days=start_days)
            return [t for t in transactions
                   if start_date <= t["transaction_date"] <= end_date]

        # Calculate features for each time window
        for window_name, start_days, end_days in [
            ("w0_30", 0, 30),
            ("w0_90", 0, 90),
            ("w30_60", 30, 60),
            ("w0_180", 0, 180),
        ]:
            window_txns = filter_by_window(start_days, end_days)

            if window_txns:
                amounts = [float(t["amount"]) for t in window_txns]
                features[f"sum_txn_count_{window_name}"] = len(window_txns)
                features[f"sum_txn_amount_{window_name}"] = Decimal(str(round(sum(amounts), 2)))
                features[f"avg_txn_amount_{window_name}"] = Decimal(str(round(sum(amounts) / len(amounts), 2)))
                features[f"max_txn_amount_{window_name}"] = Decimal(str(round(max(amounts), 2)))

                if window_name == "w0_30":
                    features[f"min_txn_amount_{window_name}"] = Decimal(str(round(min(amounts), 2)))
                    # Simple std dev calculation
                    mean = sum(amounts) / len(amounts)
                    variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)
                    features[f"std_txn_amount_{window_name}"] = Decimal(str(round(variance ** 0.5, 2)))
            else:
                features[f"sum_txn_count_{window_name}"] = 0
                features[f"sum_txn_amount_{window_name}"] = Decimal("0")
                features[f"avg_txn_amount_{window_name}"] = Decimal("0")
                features[f"max_txn_amount_{window_name}"] = Decimal("0")

                if window_name == "w0_30":
                    features[f"min_txn_amount_{window_name}"] = Decimal("0")
                    features[f"std_txn_amount_{window_name}"] = Decimal("0")

        # Special feature for w0_180
        window_txns_180 = filter_by_window(0, 180)
        if window_txns_180:
            features["max_single_txn_w0_180"] = Decimal(str(round(max(float(t["amount"]) for t in window_txns_180), 2)))
        else:
            features["max_single_txn_w0_180"] = Decimal("0")

        # Risk indicators (0-90 days)
        window_txns_90 = filter_by_window(0, 90)
        features["count_high_risk_countries_w0_90"] = sum(1 for t in window_txns_90 if t["is_high_risk_country"])
        features["count_cash_intensive_txn_w0_90"] = sum(1 for t in window_txns_90 if t["is_cash_transaction"])
        features["count_round_amount_txn_w0_90"] = sum(1 for t in window_txns_90 if t["is_round_amount"])

        international_count = sum(1 for t in window_txns_90 if t["is_international"])
        features["ratio_international_txn_w0_90"] = round(international_count / len(window_txns_90), 2) if window_txns_90 else 0.0

        # Behavioral features
        window_txns_30 = filter_by_window(0, 30)
        features["count_atm_withdrawals_w0_30"] = sum(1 for t in window_txns_30 if t["channel"] == "atm" and t["transaction_type"] == "withdrawal")
        features["count_wire_transfers_w0_90"] = sum(1 for t in window_txns_90 if t["transaction_type"] == "wire")

        # Velocity score (transactions per day in last 30 days)
        features["velocity_score_w0_30"] = round(len(window_txns_30) / 30, 2) if window_txns_30 else 0.0

        # Network features (mock values)
        features["network_degree_centrality"] = round(random.uniform(0, 1), 3)
        features["network_community_id"] = f"COMM_{random.randint(1, 10)}"
        features["count_unique_counterparties_w0_90"] = len(set(t["counterparty_name"] for t in window_txns_90))
        features["count_shared_counterparties"] = random.randint(0, 5)

        # Knowledge graph features (mock values)
        features["pep_exposure_score"] = round(random.uniform(0, 1), 3)
        features["adverse_media_score"] = round(random.uniform(0, 1), 3)
        features["sanction_list_proximity"] = round(random.uniform(0, 1), 3)

        # Model scores
        features["ml_model_score"] = round(random.uniform(0, 1), 3)
        features["rule_based_score"] = round(random.uniform(0, 1), 3)

        return features

    def generate_alert(self, customer_id: int, alert_id: int, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate an alert based on transaction patterns.

        Args:
            customer_id: Customer database ID
            alert_id: Alert sequence number
            transactions: Customer transactions

        Returns:
            Alert dict
        """
        # Determine alert type based on transaction patterns
        high_risk_txns = [t for t in transactions if t["is_high_risk_country"]]
        structured_txns = [t for t in transactions if t["is_structured"]]
        large_txns = [t for t in transactions if float(t["amount"]) > 50000]

        if structured_txns:
            alert_type = "structuring"
            severity = "high"
        elif high_risk_txns:
            alert_type = "high_risk_country"
            severity = "medium" if len(high_risk_txns) < 5 else "high"
        elif large_txns:
            alert_type = "unusual_activity"
            severity = "medium"
        else:
            alert_type = random.choice(ALERT_TYPES)
            severity = random.choice(["low", "medium", "high"])

        # Alert date around recent transaction
        if transactions:
            recent_txn = max(transactions, key=lambda t: t["transaction_date"])
            alert_date = recent_txn["transaction_date"] + timedelta(days=random.randint(0, 3))
        else:
            alert_date = datetime.now()

        status_options = ["open", "investigating", "closed", "escalated"]
        status = random.choices(status_options, weights=[0.3, 0.4, 0.2, 0.1])[0]

        return {
            "alert_id": f"ALT{alert_id:08d}",
            "customer_id": customer_id,
            "alert_type": alert_type,
            "alert_date": alert_date,
            "severity": severity,
            "status": status,
            "assigned_to": fake.name() if status in ["investigating", "closed"] else None,
            "description": f"{alert_type.replace('_', ' ').title()} detected for customer",
            "triggered_by_model": "risk_model_v1",
            "model_confidence": round(random.uniform(0.6, 0.95), 2),
            "feature_importance": '{"top_features": ["sum_txn_amount_w0_30", "ratio_international_txn_w0_90"]}',
        }

    def generate_all(self):
        """Generate all mock data."""
        print(f"Generating {self.num_customers} customers...")

        # Determine risk profile distribution
        risk_profiles = (
            ["low"] * int(self.num_customers * 0.70) +
            ["medium"] * int(self.num_customers * 0.20) +
            ["high"] * int(self.num_customers * 0.08) +
            ["critical"] * int(self.num_customers * 0.02)
        )
        random.shuffle(risk_profiles)

        alert_id_counter = 1

        for customer_id in range(1, self.num_customers + 1):
            risk_profile = risk_profiles[customer_id - 1] if customer_id - 1 < len(risk_profiles) else "low"

            # Generate customer
            customer = self.generate_customer(customer_id, risk_profile)

            # Generate transactions
            transactions = self.generate_transactions(customer_id, customer["cif_no"], risk_profile)

            # Calculate features
            features = self.calculate_customer_features(customer_id, transactions)
            customer.update(features)

            self.customers.append(customer)
            self.transactions.extend(transactions)

            # Generate alerts for high-risk customers
            if risk_profile in ["high", "critical"]:
                num_alerts = random.randint(1, 3)
                for _ in range(num_alerts):
                    alert = self.generate_alert(customer_id, alert_id_counter, transactions)
                    self.alerts.append(alert)
                    alert_id_counter += 1

            if customer_id % 10 == 0:
                print(f"  Generated {customer_id}/{self.num_customers} customers...")

        print(f"Generated {len(self.customers)} customers, {len(self.transactions)} transactions, {len(self.alerts)} alerts")

    def load_to_database(self):
        """Load generated data into PostgreSQL."""
        print("Connecting to database...")
        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()

        try:
            print("Loading customers...")
            customer_insert = """
                INSERT INTO customers (
                    cif_no, name, date_of_birth, country, kyc_status, account_opened_date,
                    occupation, industry, risk_score,
                    sum_txn_count_w0_30, sum_txn_amount_w0_30, avg_txn_amount_w0_30,
                    max_txn_amount_w0_30, min_txn_amount_w0_30, std_txn_amount_w0_30,
                    sum_txn_count_w0_90, sum_txn_amount_w0_90, avg_txn_amount_w0_90,
                    max_txn_amount_w0_90, sum_txn_count_w30_60, avg_txn_amount_w30_60,
                    sum_txn_count_w0_180, sum_txn_amount_w0_180, max_single_txn_w0_180,
                    count_high_risk_countries_w0_90, count_cash_intensive_txn_w0_90,
                    count_round_amount_txn_w0_90, ratio_international_txn_w0_90,
                    count_atm_withdrawals_w0_30, count_wire_transfers_w0_90, velocity_score_w0_30,
                    network_degree_centrality, network_community_id, count_unique_counterparties_w0_90,
                    count_shared_counterparties, pep_exposure_score, adverse_media_score,
                    sanction_list_proximity, ml_model_score, rule_based_score
                ) VALUES (
                    %(cif_no)s, %(name)s, %(date_of_birth)s, %(country)s, %(kyc_status)s, %(account_opened_date)s,
                    %(occupation)s, %(industry)s, %(risk_score)s,
                    %(sum_txn_count_w0_30)s, %(sum_txn_amount_w0_30)s, %(avg_txn_amount_w0_30)s,
                    %(max_txn_amount_w0_30)s, %(min_txn_amount_w0_30)s, %(std_txn_amount_w0_30)s,
                    %(sum_txn_count_w0_90)s, %(sum_txn_amount_w0_90)s, %(avg_txn_amount_w0_90)s,
                    %(max_txn_amount_w0_90)s, %(sum_txn_count_w30_60)s, %(avg_txn_amount_w30_60)s,
                    %(sum_txn_count_w0_180)s, %(sum_txn_amount_w0_180)s, %(max_single_txn_w0_180)s,
                    %(count_high_risk_countries_w0_90)s, %(count_cash_intensive_txn_w0_90)s,
                    %(count_round_amount_txn_w0_90)s, %(ratio_international_txn_w0_90)s,
                    %(count_atm_withdrawals_w0_30)s, %(count_wire_transfers_w0_90)s, %(velocity_score_w0_30)s,
                    %(network_degree_centrality)s, %(network_community_id)s, %(count_unique_counterparties_w0_90)s,
                    %(count_shared_counterparties)s, %(pep_exposure_score)s, %(adverse_media_score)s,
                    %(sanction_list_proximity)s, %(ml_model_score)s, %(rule_based_score)s
                )
            """
            execute_batch(cur, customer_insert, self.customers, page_size=100)
            print(f"  Loaded {len(self.customers)} customers")

            print("Loading transactions...")
            transaction_insert = """
                INSERT INTO transactions (
                    transaction_id, customer_id, amount, currency, transaction_date,
                    transaction_type, channel, counterparty_name, counterparty_account,
                    counterparty_country, counterparty_bank, is_cash_transaction,
                    is_round_amount, is_high_risk_country, is_structured, is_international,
                    description
                ) VALUES (
                    %(transaction_id)s, %(customer_id)s, %(amount)s, %(currency)s, %(transaction_date)s,
                    %(transaction_type)s, %(channel)s, %(counterparty_name)s, %(counterparty_account)s,
                    %(counterparty_country)s, %(counterparty_bank)s, %(is_cash_transaction)s,
                    %(is_round_amount)s, %(is_high_risk_country)s, %(is_structured)s, %(is_international)s,
                    %(description)s
                )
            """
            execute_batch(cur, transaction_insert, self.transactions, page_size=1000)
            print(f"  Loaded {len(self.transactions)} transactions")

            print("Loading alerts...")
            alert_insert = """
                INSERT INTO alerts (
                    alert_id, customer_id, alert_type, alert_date, severity, status,
                    assigned_to, description, triggered_by_model, model_confidence,
                    feature_importance
                ) VALUES (
                    %(alert_id)s, %(customer_id)s, %(alert_type)s, %(alert_date)s, %(severity)s, %(status)s,
                    %(assigned_to)s, %(description)s, %(triggered_by_model)s, %(model_confidence)s,
                    %(feature_importance)s
                )
            """
            execute_batch(cur, alert_insert, self.alerts, page_size=100)
            print(f"  Loaded {len(self.alerts)} alerts")

            conn.commit()
            print("Data loaded successfully!")

        except Exception as e:
            conn.rollback()
            print(f"Error loading data: {e}")
            raise
        finally:
            cur.close()
            conn.close()


def main():
    """Generate and load mock data."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate AML mock data")
    parser.add_argument("--customers", type=int, default=100, help="Number of customers")
    parser.add_argument("--transactions-per-customer", type=int, default=50, help="Avg transactions per customer")
    args = parser.parse_args()

    generator = AMLDataGenerator(
        num_customers=args.customers,
        transactions_per_customer=args.transactions_per_customer
    )

    print("=== AML Mock Data Generator ===")
    generator.generate_all()
    generator.load_to_database()
    print("=== Complete ===")


if __name__ == "__main__":
    main()
