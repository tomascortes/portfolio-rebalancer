# portfolio-rebalancer

Calculate buy/sell orders to rebalance a portfolio of Fintual ETFs. Three optimization strategies, live price fetching, interactive CLI.


## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

## Run

```bash
uv sync
uv run python cli.py
```

Prices are fetched live from the Fintual API on startup. If the API is unreachable it falls back to hardcoded prices from the last known date.

## How it works

1. **Pick a portfolio** — arrow keys to browse the four Fintual funds. A live preview above the menu shows each fund's ETFs, target allocation, and current price.

https://github.com/user-attachments/assets/07353d7a-8b13-4322-8ae4-610aff71f835

2. **Pick a strategy** — choose how the optimizer calculates the trades.


https://github.com/user-attachments/assets/537e50b5-7bf9-4587-8ebd-dc4bd08d909b


3. **See the orders** — current holdings, the rebalance orders, and the resulting holdings after applying them.

https://github.com/user-attachments/assets/2a6e3901-5d03-40f5-8189-390f5b04db6c



## Modules

### `cli.py`

Interactive entry point. Fetches prices, drives the arrow-key menus with live allocation previews, renders holdings and order tables via Rich.

### `src/config.py`

`FintualFund` enum — maps fund names (Norris, Pitt, Clooney, Streep) to their Fintual real-asset IDs.

### `src/models.py`

Two dataclasses: `Stock` (symbol, quantity, price) and `RebalanceOrder` (action, shares, dollar amounts, deviation from target).

### `src/portfolio.py`

`Portfolio` — holds current positions and a target allocation. Computes current allocation percentages and dispatches rebalancing to whichever strategy is selected.

### `src/optimizers/`

Three strategies, all behind the `RebalanceStrategy` ABC:

| Strategy           | File                    | Description                                                                                                                       |
| ------------------ | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Simple             | `simple.py`             | Target shares via floor division. No solver, runs instantly.                                                                      |
| Tracking Error     | `tracking_error.py`     | MILP via scipy — minimizes total absolute deviation from target weights. Closest result to the ideal allocation.                  |
| Trade Minimization | `trade_minimization.py` | MILP via scipy — minimizes total shares traded while keeping each allocation within a ±2 % band around the target. Fewest trades. |

Both MILP strategies fall back to Simple if the solver fails.

---

## Futurology

## Some of the things that werent considered here:

- Assumes stock price is always the latest available; does not accept user-provided or updated prices for specific stocks
- Transaction prices (commissions, bid/ask spread, taxes) are not modeled, so results ignore this real cost.
- No options to keep a cash buffer for liquidity, or force a portion of your portfolio to stay in cash.
