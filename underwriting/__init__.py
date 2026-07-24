"""Swiss real estate underwriting engine."""

from .benchmark import (
    BenchmarkAnalysis,
    BenchmarkIndicator,
    MarketBenchmarks,
    analyse_market_benchmarks,
)
from .comparables import (
    ComparableAnalysis,
    ComparableProperty,
    ComparableResult,
    analyse_comparables,
)
from .deal_store import DealStore, SavedDeal
from .engine import analyse_investment
from .decision import Decision, InvestmentCriteria, RiskItem, make_decision
from .models import FinancingAssumptions, InvestmentAnalysis, PropertyAssumptions
from .memo import build_ic_memo
from .scenarios import ScenarioAnalysis, standard_scenarios
from .sensitivity import SensitivityPoint, sensitivity_grid

__all__ = [
    "FinancingAssumptions",
    "InvestmentAnalysis",
    "InvestmentCriteria",
    "PropertyAssumptions",
    "Decision",
    "RiskItem",
    "ScenarioAnalysis",
    "SensitivityPoint",
    "analyse_investment",
    "build_ic_memo",
    "BenchmarkAnalysis",
    "BenchmarkIndicator",
    "MarketBenchmarks",
    "analyse_market_benchmarks",
    "ComparableAnalysis",
    "ComparableProperty",
    "ComparableResult",
    "analyse_comparables",
    "DealStore",
    "SavedDeal",
    "make_decision",
    "sensitivity_grid",
    "standard_scenarios",
]
