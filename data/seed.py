from pathlib import Path
import sqlite3
import random
import datetime


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "recoveryos.db"


# ============================================================
# RANDOM SEED
# ============================================================

random.seed(42)


# ============================================================
# SYNTHETIC DATA OPTIONS
# ============================================================

failure_codes = [
    "BANK_TIMEOUT",
    "NETWORK_ERROR",
    "GATEWAY_TIMEOUT",
    "INSUFFICIENT_FUNDS",
    "CARD_EXPIRED",
    "AUTH_FAILED",
    "BANK_DECLINED",
    "LIMIT_EXCEEDED",
    "EXPIRED_CARD",
]

payment_methods = [
    "UPI",
    "CARD",
    "NETBANKING",
    "WALLET",
]

merchant_categories = [
    "FOOD",
    "E_COMMERCE",
    "TRAVEL",
    "HEALTHCARE",
    "SAAS",
    "EDUCATION",
]


# ============================================================
# DATABASE CONNECTION
# ============================================================

conn = sqlite3.connect(DB)
c = conn.cursor()


# ============================================================
# RESET TABLES
# ============================================================

c.execute("DROP TABLE IF EXISTS payments")
c.execute("DROP TABLE IF EXISTS audit_events")


# ============================================================
# PAYMENTS TABLE
# ============================================================

c.execute("""
CREATE TABLE payments (
    payment_id TEXT PRIMARY KEY,

    amount REAL,

    payment_method TEXT,

    failure_code TEXT,

    successful_payments INTEGER,

    previous_retries INTEGER,

    customer_tenure_days INTEGER,

    transaction_hour INTEGER,

    merchant_category TEXT,

    days_since_last_success INTEGER,

    customer_avg_amount REAL,

    status TEXT,

    created_at TEXT
)
""")


# ============================================================
# AUDIT EVENTS TABLE
# ============================================================
#
# Stores every RecoveryOS agent decision.
#
# This allows us to answer:
#
#   What happened?
#   Why did the agent choose this action?
#   What did the ML model predict?
#   What did Claude diagnose?
#   What tool was executed?
#   Was the action verified?
#   Did the system require human intervention?
#
# ============================================================

c.execute("""
CREATE TABLE audit_events (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,

    payment_id TEXT NOT NULL,

    timestamp TEXT NOT NULL,

    amount REAL,

    failure_code TEXT,

    base_recovery_probability REAL,

    diagnosis_source TEXT,

    diagnosis TEXT,

    severity TEXT,

    selected_action TEXT,

    selected_probability REAL,

    expected_recovery_value REAL,

    decision_reason TEXT,

    execution_status TEXT,

    verification_status TEXT,

    agent_status TEXT,

    escalation_reason TEXT,

    FOREIGN KEY (payment_id)
        REFERENCES payments(payment_id)
)
""")


# ============================================================
# GENERATE PAYMENT EVENTS
# ============================================================

now = datetime.datetime.now().isoformat(
    timespec="seconds"
)


for i in range(1000):

    # --------------------------------------------------------
    # PAYMENT AMOUNT
    # --------------------------------------------------------

    amount = round(
        random.uniform(
            200,
            50000
        ),
        2
    )


    # --------------------------------------------------------
    # PAYMENT CONTEXT
    # --------------------------------------------------------

    payment_method = random.choice(
        payment_methods
    )

    failure_code = random.choice(
        failure_codes
    )


    # --------------------------------------------------------
    # CUSTOMER HISTORY
    # --------------------------------------------------------

    successful_payments = max(
        0,
        int(
            random.gauss(
                15,
                8
            )
        )
    )

    previous_retries = random.randint(
        0,
        4
    )

    customer_tenure_days = random.randint(
        30,
        1500
    )


    # --------------------------------------------------------
    # TRANSACTION CONTEXT
    # --------------------------------------------------------

    transaction_hour = random.randint(
        0,
        23
    )

    merchant_category = random.choice(
        merchant_categories
    )

    days_since_last_success = random.randint(
        0,
        90
    )


    # --------------------------------------------------------
    # CUSTOMER SPENDING PROFILE
    # --------------------------------------------------------

    customer_avg_amount = round(
        random.uniform(
            500,
            20000
        ),
        2
    )


    # --------------------------------------------------------
    # PAYMENT ID
    # --------------------------------------------------------

    payment_id = (
        f"pay_{i + 1:05d}"
    )


    # --------------------------------------------------------
    # INSERT PAYMENT
    # --------------------------------------------------------

    c.execute(
        """
        INSERT INTO payments (
            payment_id,
            amount,
            payment_method,
            failure_code,
            successful_payments,
            previous_retries,
            customer_tenure_days,
            transaction_hour,
            merchant_category,
            days_since_last_success,
            customer_avg_amount,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_id,

            amount,

            payment_method,

            failure_code,

            successful_payments,

            previous_retries,

            customer_tenure_days,

            transaction_hour,

            merchant_category,

            days_since_last_success,

            customer_avg_amount,

            "FAILED",

            now,
        ),
    )


# ============================================================
# SAVE DATABASE
# ============================================================

conn.commit()

conn.close()


# ============================================================
# COMPLETION MESSAGE
# ============================================================

print(
    f"Seeded {DB} with 1000 payment events "
    "and created the updated audit_events table."
)