"""Generate noisy daily retail observations and save them to CSV.

Run from the repository root: python data/script.py
Requires numpy and pandas. See data/README.md for assumptions and options.
"""

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

CATEGORIES = ("Mens Casual", "Womens Ethnic", "Kidswear", "Winter Jackets")
DISCOUNTS = np.array([0, 10, 25, 40, 50])
ROW_COUNT = 10_000
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "retail_sales.csv"

# Diwali moves each year; these are dates, not a fixed October/November proxy.
# Regional observances can differ by a day. Extend this table for later years.
DIWALI_DATES = {
    2020: "2020-11-14",
    2021: "2021-11-04",
    2022: "2022-10-24",
    2023: "2023-11-12",
    2024: "2024-10-31",
    2025: "2025-10-20",
    2026: "2026-11-08",
    2027: "2027-10-29",
    2028: "2028-10-17",
    2029: "2029-11-05",
    2030: "2030-10-26",
}


def generate_sales(*, seed: int = 42, end_date: date | None = None) -> pd.DataFrame:
    """Return exactly 10,000 rows over two calendar years ending yesterday.

    Rows represent daily store/SKU-level observations, not unique chain-wide
    date/category totals. Store/SKU identifiers are intentionally not exported.
    An explicit end_date (inclusive) and seed make the output reproducible.
    """
    rng = np.random.default_rng(seed)
    yesterday = datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)
    end = pd.Timestamp(end_date or yesterday).normalize()
    start = end + pd.Timedelta(days=1) - pd.DateOffset(years=2)
    days = pd.date_range(start, end, freq="D")
    missing_years = sorted(set(days.year) - DIWALI_DATES.keys())
    if missing_years:
        raise ValueError(f"Add Diwali dates to DIWALI_DATES for years: {missing_years}")

    # Guarantee every day and category appears, then sample extra observations.
    pair_count = len(days) * len(CATEGORIES)
    pairs = np.concatenate(
        [np.arange(pair_count), rng.integers(0, pair_count, ROW_COUNT - pair_count)]
    )
    rng.shuffle(pairs)
    day_index, category_index = np.divmod(pairs, len(CATEGORIES))
    dates = days[day_index]
    categories = np.asarray(CATEGORIES)[category_index]
    months = dates.month.to_numpy()
    weekend_days = np.asarray(days.day_of_week >= 5)
    weekends = weekend_days[day_index]
    prices = rng.integers(299, 1500, ROW_COUNT)
    discounts = rng.choice(DISCOUNTS, ROW_COUNT, p=[0.30, 0.25, 0.22, 0.15, 0.08])

    # Festival demand rises before Diwali, rather than throughout a fixed month.
    diwali = pd.DatetimeIndex([DIWALI_DATES[year] for year in dates.year])
    days_to_diwali = (diwali - dates).days.to_numpy()
    festival_peak = np.exp(-0.5 * ((days_to_diwali - 12) / 9.0) ** 2)
    seasonal = np.ones(ROW_COUNT)
    mens = categories == "Mens Casual"
    ethnic = categories == "Womens Ethnic"
    kids = categories == "Kidswear"
    jackets = categories == "Winter Jackets"
    seasonal[mens] = 1.0 + 0.12 * np.cos((months[mens] - 5) * np.pi / 6)
    seasonal[ethnic] = 1.0 + 1.9 * festival_peak[ethnic]
    seasonal[kids] = (
        1.0 + 0.35 * np.isin(months[kids], [5, 6]) + 0.3 * festival_peak[kids]
    )
    jacket_seasons = np.array(
        [2.5, 1.4, 0.7, 0.3, 0.25, 0.25, 0.25, 0.3, 0.4, 0.9, 3.6, 4.4]
    )
    seasonal[jackets] = jacket_seasons[months[jackets] - 1]

    baseline = np.array([42.0, 38.0, 47.0, 22.0])[category_index]
    price_effect = (799.0 / prices) ** 0.35
    discount_fraction = discounts / 100.0
    # Vary promotion responsiveness across unobserved stores/SKUs.
    elasticity = rng.uniform(0.7, 1.3, ROW_COUNT)
    promo_effect = 1 + elasticity * (
        1.5 * discount_fraction + 1.8 * discount_fraction**2
    )
    weekend_effect = np.where(
        weekends, np.clip(rng.normal(1.30, 0.16, ROW_COUNT), 0.8, 1.9), 1.0
    )
    # Shared daily footfall shocks plus independent store/SKU variation.
    daily_shock = rng.lognormal(-(0.20**2) / 2, 0.20, len(days))[day_index]
    local_shock = rng.lognormal(-(0.25**2) / 2, 0.25, ROW_COUNT)
    expected_units = (
        baseline
        * seasonal
        * price_effect
        * promo_effect
        * weekend_effect
        * daily_shock
        * local_shock
    )

    # Rain/heatwaves affect all observations on selected weekend dates.
    weather_days = weekend_days & (rng.random(len(days)) < 0.12)
    weather_factor = np.where(weather_days, rng.uniform(0.60, 0.70, len(days)), 1.0)
    expected_units *= weather_factor[day_index]

    # Heteroscedastic Gaussian noise keeps even identical inputs uncertain.
    noisy_units = expected_units + rng.normal(0.0, 4.0 + 0.22 * expected_units)
    units = np.rint(np.maximum(noisy_units, 0)).astype(np.int64)

    # Override the final count so noise cannot erase high-demand stock-outs.
    high_demand = expected_units >= np.quantile(expected_units, 0.75)
    stockouts = high_demand & (rng.random(ROW_COUNT) < 0.10)
    units[stockouts] = rng.choice(
        [0, 1, 2, 3], stockouts.sum(), p=[0.55, 0.20, 0.15, 0.10]
    )

    sales = pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Category": categories,
            "Base_Price": prices,
            "Discount_Applied": discounts,
            "Units_Sold": units,
        }
    ).sort_values(["Date", "Category"], kind="stable", ignore_index=True)
    # Diagnostics only: these flags are deliberately NOT saved as model inputs.
    sales.attrs["stockout_rows"] = int(stockouts.sum())
    sales.attrs["weather_event_days"] = int(weather_days.sum())
    sales.attrs["weather_affected_rows"] = int(weather_days[day_index].sum())
    return sales


def save_sales(sales: pd.DataFrame, output: Path | str) -> None:
    """Write a CSV with column headers and no pandas index."""
    sales.to_csv(output, index=False, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--end-date", type=date.fromisoformat, help="Inclusive end date: YYYY-MM-DD"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="CSV output path"
    )
    args = parser.parse_args()
    sales = generate_sales(seed=args.seed, end_date=args.end_date)
    save_sales(sales, args.output)
    print(f"Saved {len(sales):,} rows to {args.output.resolve()}")
    print(f"Date range: {sales['Date'].min()} through {sales['Date'].max()}")
    print(
        f"Injected {sales.attrs['stockout_rows']} high-demand stock-out observations and "
        f"{sales.attrs['weather_event_days']} weekend weather events "
        f"({sales.attrs['weather_affected_rows']} affected rows)."
    )
    print(
        sales.groupby("Category")["Units_Sold"].agg(["count", "mean", "std"]).round(2)
    )


if __name__ == "__main__":
    main()
