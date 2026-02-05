# Initial Design Conversation

## Metadata
- **Tool**: Claude Code (Opus 4.5)
- **Date**: 2026-02-04
- **Model ID**: claude-opus-4-5-20251101

## Original Request
Build a Portfolio class with stock holdings and target allocations, including a rebalance method to calculate buy/sell orders. Designed for future web scraping to load portfolios (e.g., "Risky Norris" from Fintual or similar).

## Design Decisions Made

### 1. Financial Precision
- Using `Decimal` instead of `float` for all monetary values
- Avoids floating-point rounding errors common in financial calculations

### 2. Whole Shares Only
- Real brokers (mostly) don't allow fractional shares
- Algorithm uses `floor()` to determine tradeable share counts
- Tracks deviation between ideal and actual trade amounts

### 3. Allocation as Dictionary
- Simple `dict[str, Decimal]` mapping symbol → percentage
- Percentages expressed as decimals (0.4 = 40%)
- Validation ensures allocations sum to 1.0

### 4. RebalanceOrder with Deviation Tracking
- Returns actionable orders (BUY/SELL with share counts)
- Includes `deviation_dollars` to show how far from ideal
- Users can see the "cost" of whole-share constraints

### 5. Future Extensibility
- `loaders.py` placeholder for web scraping
- `Portfolio.from_url()` classmethod stub for loading from Fintual
- Clean separation: Portfolio logic vs data loading

## Thinking Process

The core challenge is that perfect rebalancing is mathematically impossible with whole shares. If you need to buy $200 of a $580 stock, you can't. You either buy 0 shares ($0) or 1 share ($580).

The algorithm prioritizes:
1. **Actionability**: Returns orders you can actually execute
2. **Transparency**: Shows how far off from ideal each trade is
3. **Simplicity**: No complex optimization, just floor division

For selling stocks not in the target allocation, we sell everything (full liquidation of unwanted positions).
