# Portfolio Rebalancing System - Implementation Plan

## Overview
Build a Portfolio class with stock holdings and target allocations, including a rebalance method to calculate buy/sell orders. Designed for future web scraping to load portfolios (e.g., "Risky Norris" from Fintual or similar).

## Project Structure

```
portfolio-rebalancer/
├── prompts/
│   ├── plans/
│   │   └── 001_implementation_plan.md    # This plan file
│   └── 001_initial_design.md             # Original conversation + metadata
├── src/
│   ├── __init__.py
│   ├── models.py                         # Stock, RebalanceOrder dataclasses
│   ├── portfolio.py                      # Main Portfolio class
│   └── loaders.py                        # Future: web scraping loaders
├── tests/
│   └── test_portfolio.py
└── README.md (optional, only if requested)
```

## Design Decisions

### 1. Stock Model (`models.py`)
- Dataclass with `symbol`, `quantity`, `current_price`
- `update_price(price)` method to receive new prices
- `market_value` property for quantity × price
- Use `Decimal` for financial precision

### 2. Allocation Representation
- Simple `dict[str, Decimal]` mapping symbol → target percentage (0.0-1.0)
- Validation: percentages must sum to 1.0

### 3. Portfolio Class (`portfolio.py`)
```python
class Portfolio:
    holdings: dict[str, Stock]        # symbol → Stock
    target_allocation: dict[str, Decimal]

    def total_value(self) -> Decimal
    def current_allocation(self) -> dict[str, Decimal]
    def rebalance(self) -> list[RebalanceOrder]
```

### 4. Rebalance Algorithm (Detailed)

**The Problem**: Shares aren't divisible. If META costs $580/share and you need to buy $200 worth, you can't buy 0.34 shares. Perfect rebalancing is impossible.

**Algorithm Steps**:
1. Calculate `total_portfolio_value = sum(stock.quantity × stock.current_price)`
2. For each symbol in target allocation:
   - `target_value = total_portfolio_value × target_percentage`
   - `current_value = holdings[symbol].market_value` (or 0 if not held)
   - `delta_dollars = target_value - current_value`
3. For stocks in holdings but NOT in allocation → sell all
4. Convert dollar deltas to **whole share counts**:
   - `shares_to_trade = floor(abs(delta_dollars) / current_price)`
   - This means we'll always be slightly off-target (under-buy, under-sell)
5. Return orders with both `shares` (integer) and `dollar_amount` (actual trade value)

**Output includes deviation info**:
```python
@dataclass
class RebalanceOrder:
    action: Literal["BUY", "SELL"]
    symbol: str
    shares: int                      # Whole shares only
    dollar_amount: Decimal           # shares × price
    target_dollars: Decimal          # What we wanted ideally
    deviation_dollars: Decimal       # How far off we are
```

**Example**:
- Portfolio: $10,000 total
- Target: META 40% ($4,000), AAPL 60% ($6,000)
- Current: META 50% ($5,000), AAPL 50% ($5,000)
- META price: $580 → need to sell $1,000 → sell 1 share ($580), deviation: $420
- AAPL price: $185 → need to buy $1,000 → buy 5 shares ($925), deviation: $75

### 5. Future: Web Scraping Loaders (`loaders.py`)
- **Placeholder module** for future implementation
- Will scrape specific URLs to load portfolio allocations (e.g., "Risky Norris" from Fintual)
- The Portfolio class will have a `@classmethod` or factory:
```python
@classmethod
def from_url(cls, url: str, name: str) -> "Portfolio":
    # Future: scrape URL, extract allocation for named portfolio
    raise NotImplementedError("Web loading coming soon")
```
- This keeps the core Portfolio simple but signals where extension happens

## Files to Create

| File | Purpose |
|------|---------|
| `portfolio-rebalancer/prompts/001_initial_design.md` | Original conversation + Claude Code Opus 4.5 metadata |
| `portfolio-rebalancer/prompts/plans/001_implementation_plan.md` | This plan document |
| `portfolio-rebalancer/src/__init__.py` | Package exports |
| `portfolio-rebalancer/src/models.py` | Stock, RebalanceOrder dataclasses |
| `portfolio-rebalancer/src/portfolio.py` | Portfolio class with rebalance logic |
| `portfolio-rebalancer/src/loaders.py` | Placeholder for future web scraping (Risky Norris, etc.) |
| `portfolio-rebalancer/tests/test_portfolio.py` | Unit tests |

## Implementation Order
1. Create project structure and prompts folders (including `plans/`)
2. Create `prompts/001_initial_design.md` with conversation + metadata
3. Copy plan to `prompts/plans/001_implementation_plan.md`
4. Implement `models.py` (Stock, RebalanceOrder with deviation tracking)
5. Implement `portfolio.py` (Portfolio class + whole-share rebalance algorithm)
6. Create `loaders.py` placeholder (for future Risky Norris scraping)
7. Add tests
8. Document with inline comments explaining design choices

## Verification
- Run tests: `python -m pytest tests/`
- Manual test with example portfolio (META 40%, AAPL 60%)

## Prompts Folder Contents

### `prompts/001_initial_design.md`
- Original user prompt (this conversation)
- Metadata:
  - Tool: Claude Code (Opus 4.5)
  - Date: 2026-02-04
  - Decisions made during planning
- Design rationale and thinking process

### `prompts/plans/001_implementation_plan.md`
- Copy of this plan document for reference

## Key Comments in Code
Each file will include docstrings/comments explaining:
- **models.py**: Why Decimal for financial precision, why dataclasses
- **portfolio.py**: Rebalance algorithm step-by-step, edge case handling, imperfect balance explanation
- **loaders.py**: Placeholder with comments on how to implement web scraping for Fintual/Risky Norris
