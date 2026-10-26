# Synthetic value-fashion sales

From the repository root, install dependencies and generate the CSV:

```sh
python -m pip install -e ./project
python data/script.py
```

Or, using uv without installing into your system Python:

```sh
uv run --project project python data/script.py
```

The script writes **10,000 rows** to `retail_sales.csv` in the repository root,
with column headers and no index, replacing the CSV on subsequent runs. No external
datasets or services are used. The five exported columns are `Date` (ISO date text),
`Category`, `Base_Price` (integer rupees, 299–1499), `Discount_Applied` (integer
percentage points: 0, 10, 25, 40, 50), and `Units_Sold` (nonnegative integer).

By default, the window is the two calendar years ending yesterday in Indian
Standard Time (`Asia/Kolkata`), so it contains only complete days. Every date/category pair appears at least once. Since 10,000
rows exceed the number of date/category combinations, each row represents a
daily store/SKU observation, **not** an aggregated chain-wide category total.
Store/SKU identifiers are omitted to keep the requested schema.

For reproducible output, fix both the seed and the inclusive end date:

```sh
python data/script.py --seed 42 --end-date 2026-10-25 --output retail_sales.csv
python -m unittest discover -s data -p 'test_*.py' -v
```

## Demand assumptions

- Discounts generally increase sales through a nonlinear promotion response;
  higher prices tend to reduce volume in this price-sensitive segment.
- Winter jackets peak in November/December. Women's ethnic wear peaks roughly
  12 days before Diwali. The Diwali date table covers 2020–2030; extend it when
  generating windows outside that range. Kidswear also has a school-season bump.
- Weekend baseline uplift averages 30%, with substantial variation; individual
  weekends can underperform weekdays.
- Shared daily and independent store/SKU demand shocks introduce unobserved
  variation. Additive Gaussian noise grows with expected demand.
- About 12% of weekend dates receive a shared 30–40% reduction in expected sales
  due to weather. Final observed sales also include Gaussian noise.
- About 10% of observations in the highest expected-demand quartile become
  stock-outs with only 0–3 units sold, including zeros.

Weather and stock-out flags are printed as diagnostics, not exported as model
features. These assumptions are illustrative, not calibrated to actual chain
sales. Noise avoids a perfect deterministic target, but **does not guarantee
Random Forest generalization**. Evaluate with a chronological holdout (or
rolling time splits), keeping all rows for the same date in the same split.
