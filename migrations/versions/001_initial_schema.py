"""Initial schema for AML compliance database.

Revision ID: 001
Revises:
Create Date: 2025-11-16

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial tables for AML compliance system."""

    # Create customers table
    op.execute("""
        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            cif_no VARCHAR(50) UNIQUE NOT NULL,

            -- Basic customer info
            name VARCHAR(200) NOT NULL,
            date_of_birth DATE,
            country VARCHAR(3),
            kyc_status VARCHAR(20),
            account_opened_date DATE,
            occupation VARCHAR(100),
            industry VARCHAR(100),

            -- Engineered features - Transaction aggregations (0-30 days)
            sum_txn_count_w0_30 INTEGER DEFAULT 0,
            sum_txn_amount_w0_30 NUMERIC(15, 2) DEFAULT 0,
            avg_txn_amount_w0_30 NUMERIC(15, 2) DEFAULT 0,
            max_txn_amount_w0_30 NUMERIC(15, 2) DEFAULT 0,
            min_txn_amount_w0_30 NUMERIC(15, 2) DEFAULT 0,
            std_txn_amount_w0_30 NUMERIC(15, 2) DEFAULT 0,

            -- Engineered features - Transaction aggregations (0-90 days)
            sum_txn_count_w0_90 INTEGER DEFAULT 0,
            sum_txn_amount_w0_90 NUMERIC(15, 2) DEFAULT 0,
            avg_txn_amount_w0_90 NUMERIC(15, 2) DEFAULT 0,
            max_txn_amount_w0_90 NUMERIC(15, 2) DEFAULT 0,

            -- Engineered features - Transaction aggregations (30-60 days)
            sum_txn_count_w30_60 INTEGER DEFAULT 0,
            avg_txn_amount_w30_60 NUMERIC(15, 2) DEFAULT 0,

            -- Engineered features - Transaction aggregations (0-180 days)
            sum_txn_count_w0_180 INTEGER DEFAULT 0,
            sum_txn_amount_w0_180 NUMERIC(15, 2) DEFAULT 0,
            max_single_txn_w0_180 NUMERIC(15, 2) DEFAULT 0,

            -- Engineered features - Risk indicators
            count_high_risk_countries_w0_90 INTEGER DEFAULT 0,
            count_cash_intensive_txn_w0_90 INTEGER DEFAULT 0,
            count_round_amount_txn_w0_90 INTEGER DEFAULT 0,
            ratio_international_txn_w0_90 FLOAT DEFAULT 0.0,

            -- Engineered features - Behavioral patterns
            count_atm_withdrawals_w0_30 INTEGER DEFAULT 0,
            count_wire_transfers_w0_90 INTEGER DEFAULT 0,
            velocity_score_w0_30 FLOAT DEFAULT 0.0,

            -- Engineered features - Network/Graph features
            network_degree_centrality FLOAT DEFAULT 0.0,
            network_community_id VARCHAR(50),
            count_unique_counterparties_w0_90 INTEGER DEFAULT 0,
            count_shared_counterparties INTEGER DEFAULT 0,

            -- Engineered features - Knowledge graph features
            pep_exposure_score FLOAT DEFAULT 0.0,
            adverse_media_score FLOAT DEFAULT 0.0,
            sanction_list_proximity FLOAT DEFAULT 0.0,

            -- Model scores
            risk_score FLOAT,
            ml_model_score FLOAT,
            rule_based_score FLOAT,

            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_feature_update TIMESTAMP
        )
    """)

    # Create indexes for customers
    op.execute("CREATE INDEX idx_customers_cif_no ON customers(cif_no)")
    op.execute("CREATE INDEX idx_customers_risk_score ON customers(risk_score)")

    # Create transactions table
    op.execute("""
        CREATE TABLE transactions (
            id SERIAL PRIMARY KEY,
            transaction_id VARCHAR(100) UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL REFERENCES customers(id),

            -- Transaction details
            amount NUMERIC(15, 2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD',
            transaction_date TIMESTAMP NOT NULL,
            transaction_type VARCHAR(50),
            channel VARCHAR(50),

            -- Counterparty information
            counterparty_name VARCHAR(200),
            counterparty_account VARCHAR(100),
            counterparty_country VARCHAR(3),
            counterparty_bank VARCHAR(200),

            -- Risk indicators
            is_cash_transaction BOOLEAN DEFAULT FALSE,
            is_round_amount BOOLEAN DEFAULT FALSE,
            is_high_risk_country BOOLEAN DEFAULT FALSE,
            is_structured BOOLEAN DEFAULT FALSE,
            is_international BOOLEAN DEFAULT FALSE,

            -- Metadata
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for transactions
    op.execute("CREATE INDEX idx_transactions_transaction_id ON transactions(transaction_id)")
    op.execute("CREATE INDEX idx_transactions_customer_id ON transactions(customer_id)")
    op.execute("CREATE INDEX idx_transactions_date ON transactions(transaction_date)")

    # Create alerts table
    op.execute("""
        CREATE TABLE alerts (
            id SERIAL PRIMARY KEY,
            alert_id VARCHAR(100) UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL REFERENCES customers(id),

            -- Alert details
            alert_type VARCHAR(100) NOT NULL,
            alert_date TIMESTAMP NOT NULL,
            severity VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,

            -- Investigation
            assigned_to VARCHAR(100),
            description TEXT,
            investigation_notes TEXT,

            -- Model information
            triggered_by_model VARCHAR(100),
            model_confidence FLOAT,
            feature_importance TEXT,

            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        )
    """)

    # Create indexes for alerts
    op.execute("CREATE INDEX idx_alerts_alert_id ON alerts(alert_id)")
    op.execute("CREATE INDEX idx_alerts_customer_id ON alerts(customer_id)")
    op.execute("CREATE INDEX idx_alerts_date ON alerts(alert_date)")
    op.execute("CREATE INDEX idx_alerts_status ON alerts(status)")

    # Create reports table
    op.execute("""
        CREATE TABLE reports (
            id SERIAL PRIMARY KEY,
            report_id VARCHAR(100) UNIQUE NOT NULL,
            alert_id INTEGER REFERENCES alerts(id),

            -- Report details
            report_type VARCHAR(50) NOT NULL,
            title VARCHAR(200),
            content TEXT NOT NULL,
            summary TEXT,

            -- Status
            status VARCHAR(20),
            created_by VARCHAR(100) NOT NULL,
            reviewed_by VARCHAR(100),
            approved_by VARCHAR(100),

            -- Metadata
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_date TIMESTAMP,
            filed_date TIMESTAMP
        )
    """)

    # Create indexes for reports
    op.execute("CREATE INDEX idx_reports_report_id ON reports(report_id)")
    op.execute("CREATE INDEX idx_reports_alert_id ON reports(alert_id)")
    op.execute("CREATE INDEX idx_reports_created_date ON reports(created_date)")


def downgrade() -> None:
    """Drop all tables."""
    op.execute("DROP TABLE IF EXISTS reports CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS customers CASCADE")
