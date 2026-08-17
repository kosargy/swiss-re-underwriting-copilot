# Swiss Real Estate Underwriting Copilot

Portfolio project for preliminary underwriting of Swiss income-producing real
estate. It combines an auditable Python valuation engine with a Streamlit
interface, scenario analysis, transparent market evidence, a risk register and
an Investment Committee memo.

The interface is organized by investment strategy:

- **Core Acquisition** for stabilized income-producing properties
- **Value-Add / Repositioning** for renovation, lease-up and operational change
- **Ground-Up Development** for land acquisition and new construction

Only the workflow relevant to the selected strategy is displayed.

## What the engine calculates

- Effective rental income and vacancy loss
- Net Operating Income (NOI)
- Implied cap rate and direct-cap value
- Five-year annual cash-flow projection
- Terminal value based on next year's NOI
- Selling costs and DCF value
- NPV at the asking price
- Unlevered and levered IRR
- Loan amount, interest, amortization and annual debt service
- DSCR, equity multiple and break-even occupancy
- Base, upside and downside scenarios
- Exit-cap/rent-growth sensitivity matrices
- Transparent benchmarking of rent, vacancy, price/m², expenses and cap rates
- Indicative income and comparable-price valuation cross-checks
- Editable comparable-property set with CSV import/export
- Transparent comparable relevance score and condition adjustment
- Comparable-supported value range and confidence indicator
- SQLite-backed deal library for complete save/load snapshots
- Rule-based risk register with evidence and required actions
- Preliminary recommendation and maximum supported price
- Downloadable Investment Committee memo in PDF format
- Separate development-feasibility module for land acquisitions
- Plan A / Plan B use-mix and probability comparison
- Gross development value and residual land valuation
- Maximum supportable land price at the selected target return
- Development-cost schedule, NPV, IRR and profit margin
- Construction-cost/revenue sensitivity matrix
- Value-Add transition-period and stabilized annual cash flows
- Renovation income disruption and equity-funded CapEx
- As-is value, stabilized value and value-creation bridge
- Maximum supportable acquisition price and break-even renovation budget
- Value-Add unlevered/levered IRR, equity multiple and stabilized DSCR
- Renovation-cost/stabilized-rent sensitivity matrix
- Strategy-specific Investment Committee memos for Core, Value-Add and Development
- Executive decision narrative, principal risks and required due diligence
- Downloadable maximum-bid recommendation for every investment strategy

Core calculations are separated from the user interface so an interviewer can
audit the methodology instead of treating the outputs as a black box.

## Development-feasibility module

The eighth app tab evaluates a development site before acquisition. Enter the
plot, permitted density, efficiency, timing, construction costs and market
assumptions for two alternative development plans. Each plan can combine:

- Residential units held for rent
- Condominiums built for sale
- Commercial space held for rent
- Rental and for-sale parking

The module capitalizes stabilized rental income, adds unit-sale proceeds,
deducts selling and development costs, discounts the cash flows and calculates
the residual land value. The headline output is the maximum land purchase price
that makes NPV equal to zero at the selected discount rate, including land
acquisition costs. A 5x5 sensitivity matrix shows how this limit changes when
construction costs and revenues move by plus or minus 5% and 10%.

Plan probabilities must total 100%. They produce a probability-weighted land
value, while the app separately identifies the plan with the highest residual
value. All results are preliminary decision-support outputs, not a certified
valuation.

## Value-Add / Repositioning module

The Value-Add workflow models an existing property's current operations, a
multi-year renovation period and the stabilized post-renovation case. It tracks
income disruption, operating costs, annual renovation CapEx, purchase debt,
amortization and exit proceeds. The module calculates the as-is and stabilized
values, value created after CapEx, NPV, unlevered and levered IRR, equity
multiple and stabilized DSCR.

The maximum supportable purchase price is the price that makes NPV equal to
zero at the target discount rate. The break-even renovation budget is the total
CapEx that produces the same zero-NPV result at the entered asking price. The
first version assumes renovation CapEx is equity-funded; this is stated in the
interface so the financing convention remains auditable.

## Included case

`examples/zurich_residential.json` is a fictional but realistic Swiss
residential investment:

- Asking price: CHF 15.0m
- Potential annual rent: CHF 900k
- Vacancy: 4%
- Operating expenses: CHF 220k
- Five-year holding period
- Renovation CapEx concentrated in years 2–4
- 60% LTV financing

The case is fictional so it is safe to demonstrate publicly.

## Run the command-line model

From this project folder:

```bash
python3 -m underwriting.cli examples/zurich_residential.json
```

No third-party Python libraries are required for the first deliverable.

## Run the Streamlit app

Create the local environment once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then start the interface:

```bash
.venv/bin/streamlit run app.py --server.port 8502
```

Open `http://localhost:8502` if the browser does not open automatically.

## Run the checks

```bash
python3 -m unittest discover -s tests -v
```

## Model conventions

- Cash flows occur annually at year-end.
- Vacancy is applied to potential rent.
- Other income grows at the rent-growth rate.
- Operating expenses grow independently.
- CapEx is deducted from property and equity cash flow.
- Interest is calculated on the opening annual loan balance.
- Scheduled amortization is based on the original loan amount.
- Terminal value uses the following year's NOI divided by the exit cap rate.
- Selling costs are deducted from terminal value.
- Acquisition underwriting excludes taxes and acquisition costs.
- Development construction costs are spread evenly over the selected build
  period and inflated annually.
- Development completion value is realized at the end of the final build year.
- Development land acquisition costs are applied to the land purchase price.

These conventions are explicit so an interviewer can audit the model instead
of treating it as a black box.

## Planned next deliverables

1. PDF and rent-roll extraction with source citations
2. Saved-deal pipeline and decision history
