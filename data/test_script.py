"""Regression checks for the synthetic generator; uses only unittest."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from script import CATEGORIES, DIWALI_DATES, generate_sales, save_sales


class SalesGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sales = generate_sales(seed=42, end_date=date(2026, 10, 25))
        cls.dates = pd.to_datetime(cls.sales["Date"])

    def test_schema_and_value_ranges(self):
        self.assertEqual(self.sales.shape, (10_000, 5))
        self.assertEqual(
            self.sales.columns.tolist(),
            ["Date", "Category", "Base_Price", "Discount_Applied", "Units_Sold"],
        )
        self.assertFalse(self.sales.isna().any().any())
        self.assertEqual(set(self.sales["Category"]), set(CATEGORIES))
        self.assertTrue(self.sales["Base_Price"].between(299, 1499).all())
        self.assertEqual(set(self.sales["Discount_Applied"]), {0, 10, 25, 40, 50})
        self.assertTrue(pd.api.types.is_integer_dtype(self.sales["Units_Sold"]))
        self.assertTrue(self.sales["Units_Sold"].ge(0).all())

    def test_daily_coverage_including_leap_day(self):
        sales = generate_sales(end_date=date(2025, 3, 1))
        expected_days = pd.date_range("2023-03-02", "2025-03-01")
        self.assertEqual(sales["Date"].nunique(), len(expected_days))
        self.assertEqual(sales["Date"].min(), "2023-03-02")
        self.assertEqual(sales["Date"].max(), "2025-03-01")
        self.assertIn("2024-02-29", set(sales["Date"]))
        self.assertTrue(sales.groupby("Date")["Category"].nunique().eq(4).all())

    def test_reproducibility_and_randomness(self):
        same = generate_sales(seed=42, end_date=date(2026, 10, 25))
        pd.testing.assert_frame_equal(self.sales, same)
        different = generate_sales(seed=43, end_date=date(2026, 10, 25))
        self.assertFalse(self.sales.equals(different))

    def test_discount_and_weekend_effects_remain_learnable(self):
        by_discount = self.sales.groupby("Discount_Applied")["Units_Sold"].mean()
        self.assertGreater(by_discount[50], 1.5 * by_discount[0])
        weekends = self.dates.dt.day_of_week >= 5
        ratio = (
            self.sales.loc[weekends, "Units_Sold"].mean()
            / self.sales.loc[~weekends, "Units_Sold"].mean()
        )
        # Realized uplift is lower than the baseline uplift after bad weather.
        self.assertGreater(ratio, 1.10)
        self.assertLess(ratio, 1.50)

    def test_seasonality(self):
        jackets = self.sales["Category"].eq("Winter Jackets")
        winter = self.dates.dt.month.isin([11, 12])
        summer = self.dates.dt.month.isin([4, 5, 6, 7, 8])
        self.assertGreater(
            self.sales.loc[jackets & winter, "Units_Sold"].mean(),
            4 * self.sales.loc[jackets & summer, "Units_Sold"].mean(),
        )
        diwali = pd.to_datetime(self.dates.dt.year.map(DIWALI_DATES))
        lead = (diwali - self.dates).dt.days
        ethnic = self.sales["Category"].eq("Womens Ethnic")
        pre_festival = ethnic & lead.between(3, 25)
        off_festival = ethnic & ~lead.between(-15, 45)
        self.assertGreater(
            self.sales.loc[pre_festival, "Units_Sold"].mean(),
            1.5 * self.sales.loc[off_festival, "Units_Sold"].mean(),
        )

    def test_anomalies_and_residual_variance(self):
        self.assertGreater(self.sales.attrs["stockout_rows"], 100)
        self.assertGreater(self.sales.attrs["weather_event_days"], 0)
        self.assertGreater(self.sales.attrs["weather_affected_rows"], 0)
        self.assertGreater(self.sales["Units_Sold"].eq(0).sum(), 50)
        strong_promo = self.sales["Discount_Applied"].ge(40)
        self.assertTrue((strong_promo & self.sales["Units_Sold"].le(3)).any())
        group = self.sales.loc[
            self.sales["Category"].eq("Mens Casual")
            & self.sales["Discount_Applied"].eq(25)
            & self.sales["Base_Price"].between(700, 900),
            "Units_Sold",
        ]
        self.assertGreater(group.std() / group.mean(), 0.20)
        self.assertTrue(np.isfinite(group).all())

    def test_csv_roundtrip_and_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "retail_sales.csv"
            save_sales(self.sales, output)
            save_sales(self.sales, output)
            saved = pd.read_csv(output)
            pd.testing.assert_frame_equal(self.sales, saved)

    def test_missing_festival_year_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Add Diwali dates"):
            generate_sales(end_date=date(2032, 1, 1))


if __name__ == "__main__":
    unittest.main()
