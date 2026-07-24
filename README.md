# Swiss Real Estate Underwriting Copilot

Portfolio project for preliminary underwriting of Swiss income-producing real
estate. It combines an auditable Python valuation engine with a Streamlit
interface, scenario analysis, transparent market evidence, a risk register and
an Investment Committee memo.

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

Core calculations are separated from the user interface so an interviewer can
audit the methodology instead of treating the outputs as a black box.

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
- Taxes and acquisition costs are outside the first-deliverable scope.

These conventions are explicit so an interviewer can audit the model instead
of treating it as a black box.

## Planned next deliverables

1. PDF and rent-roll extraction with source citations
2. Saved-deal pipeline and decision history
