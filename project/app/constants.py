"""Hard-coded business reference data.

TODO: both tables below are placeholders. Replace them with values derived from
real data once transaction-level history exists (`daily_sales` only has daily
aggregates, so per-transaction quantities cannot be learned from it yet).
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TransactionBaseline:
    """Hard-coded view of what a normal single transaction looks like for a product."""

    mean_quantity: float  # typical units per transaction
    std_quantity: float  # natural spread around the mean
    critical_quantity: int  # a single transaction at/above this is always a panic buy


TRANSACTION_BASELINES: dict[str, TransactionBaseline] = {
    "Winter Jackets": TransactionBaseline(
        mean_quantity=1.5, std_quantity=0.8, critical_quantity=25
    ),
    "Mens Casual": TransactionBaseline(
        mean_quantity=2.5, std_quantity=1.2, critical_quantity=40
    ),
    "Womens Ethnic": TransactionBaseline(
        mean_quantity=2.0, std_quantity=1.0, critical_quantity=30
    ),
    "Kidswear": TransactionBaseline(
        mean_quantity=3.0, std_quantity=1.5, critical_quantity=40
    ),
}

# Used for any product that is not listed above (the contract's original tripwire was 50).
DEFAULT_BASELINE = TransactionBaseline(
    mean_quantity=2.5, std_quantity=1.2, critical_quantity=50
)


def get_baseline(category: str) -> TransactionBaseline:
    return TRANSACTION_BASELINES.get(category, DEFAULT_BASELINE)


# Navratri -> post-Diwali shopping window per year. Used to label historical rows
# as "festival season" (the CSV/DB has no such column) and to default the flag.
FESTIVAL_WINDOWS: list[tuple[date, date]] = [
    (date(2024, 10, 3), date(2024, 11, 5)),
    (date(2025, 9, 22), date(2025, 10, 25)),
    (date(2026, 10, 11), date(2026, 11, 12)),
    (date(2027, 10, 1), date(2027, 11, 3)),
]
