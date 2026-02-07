#!/usr/bin/env python3
import json
import logging
import os
import random
import select
import sys
import termios
import tty
from decimal import Decimal
from functools import partial
from io import StringIO
from typing import Callable, TypeVar
from urllib.request import Request, urlopen

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from src import FintualFund, Portfolio, RebalanceOrder, Stock

logger = logging.getLogger(__name__)
console = Console()

# ANSI escape codes for terminal styling
ANSI_BOLD_CYAN = "\033[1;36m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"
ANSI_MOVE_UP = "\033[{}A"
ANSI_CLEAR_LINE = "\033[2K\n"

# Thresholds and defaults
DRIFT_THRESHOLD = Decimal("0.02")
DEFAULT_FUND_INDEX = 3
DEFAULT_STRATEGY_INDEX = 0
DEFAULT_RANDOM_BUDGET = Decimal("50000")

# Each entry: (fintual real_asset id, fallback price from 2026-02-04)
ETFS: dict[str, tuple[int, Decimal]] = {
    "ESGV": (15581, Decimal("119.97")),
    "QQQM": (19179, Decimal("249.38")),
    "FTEC": (15903, Decimal("215.16")),
    "SOXX": (22435, Decimal("330.38")),
    "XLY": (22691, Decimal("120.10")),
    "FLCH": (22687, Decimal("23.96")),
    "FLIN": (22690, Decimal("38.14")),
    "VUG": (22688, Decimal("467.37")),
    "IAUM": (22689, Decimal("49.25")),
    "BND": (226, Decimal("73.90")),
    "BLV": (15814, Decimal("69.17")),
    "TIP": (16724, Decimal("110.25")),
}

ETF_NAMES: dict[str, str] = {
    "ESGV": "Vanguard ESG US Stock",
    "QQQM": "Invesco NASDAQ 100",
    "FTEC": "Fidelity MSCI Info Tech",
    "SOXX": "iShares Semiconductor",
    "XLY": "Consumer Discret SPDR",
    "FLCH": "Franklin FTSE China",
    "FLIN": "Franklin FTSE India",
    "VUG": "Vanguard Growth",
    "IAUM": "iShares Gold Micro",
    "BND": "Vanguard Total Bond",
    "BLV": "Vanguard Long-Term Bond",
    "TIP": "iShares TIPS",
}

# Risky Norris: top holdings from public fund data (normalized to 100%)
# Pitt / Clooney / Streep: Chilean fixed-income portion (~35-100% of fund)
# is opaque sub-funds; approximated here with BND/BLV/TIP as proxies
PORTFOLIOS: dict[FintualFund, dict[str, Decimal]] = {
    FintualFund.RISKY_NORRIS: {
        "ESGV": Decimal("0.31"),
        "QQQM": Decimal("0.18"),
        "FTEC": Decimal("0.18"),
        "SOXX": Decimal("0.10"),
        "XLY": Decimal("0.05"),
        "FLCH": Decimal("0.04"),
        "FLIN": Decimal("0.04"),
        "VUG": Decimal("0.05"),
        "IAUM": Decimal("0.05"),
    },
    FintualFund.MODERATE_PITT: {
        "ESGV": Decimal("0.25"),
        "QQQM": Decimal("0.10"),
        "IAUM": Decimal("0.06"),
        "FLCH": Decimal("0.04"),
        "FLIN": Decimal("0.03"),
        "BND": Decimal("0.25"),
        "BLV": Decimal("0.14"),
        "TIP": Decimal("0.13"),
    },
    FintualFund.CONSERVATIVE_CLOONEY: {
        "ESGV": Decimal("0.12"),
        "IAUM": Decimal("0.03"),
        "BND": Decimal("0.40"),
        "BLV": Decimal("0.25"),
        "TIP": Decimal("0.20"),
    },
    FintualFund.VERY_CONSERVATIVE_STREEP: {
        "BND": Decimal("0.65"),
        "TIP": Decimal("0.20"),
        "BLV": Decimal("0.15"),
    },
}

FUND_LABELS: dict[FintualFund, str] = {
    FintualFund.VERY_CONSERVATIVE_STREEP: "Very Conservative (Streep)",
    FintualFund.CONSERVATIVE_CLOONEY: "Conservative (Clooney)",
    FintualFund.MODERATE_PITT: "Moderate (Pitt)",
    FintualFund.RISKY_NORRIS: "Risky (Norris)",
}

STRATEGIES: list[str] = ["simple", "tracking_error", "trade_minimization"]
STRATEGY_LABELS: dict[str, str] = {
    "simple": "Simple (floor division)",
    "tracking_error": "Tracking Error (min deviation)",
    "trade_minimization": "Trade Minimization (min trades)",
}

T = TypeVar("T")


def fetch_prices() -> tuple[dict[str, Decimal], str | None]:
    """Fetch ETF prices from Fintual. Returns (fallback, None) if any request fails."""
    prices: dict[str, Decimal] = {}
    last_date: str | None = None

    for sym, (real_id, _) in ETFS.items():
        try:
            req = Request(
                f"https://fintual.cl/api/real_assets/{real_id}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            day = json.loads(urlopen(req, timeout=5).read())["data"]["attributes"][
                "last_day"
            ]
            prices[sym] = Decimal(str(day.get("net_asset_value") or day["close_price"]))
            last_date = day["date"]
        except Exception as e:
            logger.warning("Failed to fetch price for %s: %s", sym, e)
            return _get_fallback_prices(), None

    return prices, last_date


def _get_fallback_prices() -> dict[str, Decimal]:
    """Return fallback prices for all ETFs."""
    return {sym: fallback for sym, (_, fallback) in ETFS.items()}


def build_random_portfolio(
    prices: dict[str, Decimal],
    allocation: dict[str, Decimal],
    budget: Decimal = DEFAULT_RANDOM_BUDGET,
) -> Portfolio:
    """Distribute budget with random weights to simulate a drifted portfolio."""
    portfolio = Portfolio()
    portfolio.set_target_allocation(allocation)

    weights = [random.random() for _ in allocation]
    total_w = sum(weights)
    for (sym, _), w in zip(allocation.items(), weights):
        qty = max(1, int(budget * Decimal(str(w / total_w)) / prices[sym]))
        portfolio.add_stock(Stock(symbol=sym, quantity=qty, current_price=prices[sym]))

    return portfolio


def smallest_sell(orders: list[RebalanceOrder]) -> Decimal:
    """Dollar amount of the smallest sell order, or 0 if no sells."""
    sells = [o.dollar_amount for o in orders if o.action == "SELL"]
    return min(sells) if sells else Decimal("0")


def _drift_color(drift: Decimal) -> str:
    """Return color based on drift magnitude and direction."""
    if abs(drift) < DRIFT_THRESHOLD:
        return "green"
    return "red" if drift > 0 else "blue"


def holdings_table(portfolio: Portfolio, title: str) -> Table:
    """Build a Rich table showing portfolio holdings and drift from target."""
    t = Table(title=title, box=box.ROUNDED, title_style="bold white")
    t.add_column("ETF", style="cyan")
    t.add_column("Shares", justify="right")
    t.add_column("Price", justify="right")
    t.add_column("Value", justify="right")
    t.add_column("Alloc", justify="right", style="yellow")
    t.add_column("Target", justify="right", style="green")
    t.add_column("Drift", justify="right")

    alloc = portfolio.current_allocation()
    for sym, stock in portfolio.holdings.items():
        cur = alloc.get(sym, Decimal(0))
        tgt = portfolio.target_allocation.get(sym, Decimal(0))
        drift = cur - tgt
        t.add_row(
            sym,
            str(stock.quantity),
            f"${stock.current_price:,.2f}",
            f"${stock.market_value:,.2f}",
            f"{float(cur):.1%}",
            f"{float(tgt):.1%}",
            Text(f"{float(drift):+.1%}", style=_drift_color(drift)),
        )

    t.add_section()
    t.add_row(
        "", "", "Total", f"[bold]${portfolio.total_value():,.2f}[/bold]", "", "", ""
    )
    return t


def orders_table(
    orders: list[RebalanceOrder],
    portfolio_value: Decimal = Decimal("0"),
    extra_cash: Decimal = Decimal("0"),
) -> Table:
    """Build a Rich table showing rebalance orders."""
    t = Table(title="Rebalance Orders", box=box.ROUNDED, title_style="bold white")
    t.add_column("Action", no_wrap=True)
    t.add_column("ETF", style="cyan")
    t.add_column("Shares", justify="right")
    t.add_column("Amount", justify="right")
    t.add_column("Deviation", justify="right")

    buy_total = sell_total = Decimal(0)
    for o in orders:
        style = "green" if o.action == "BUY" else "red"
        if o.action == "BUY":
            buy_total += o.dollar_amount
        else:
            sell_total += o.dollar_amount
        t.add_row(
            Text(o.action, style=f"bold {style}"),
            o.symbol,
            str(o.shares),
            f"${o.dollar_amount:,.2f}",
            f"${o.deviation_dollars:,.2f}",
        )

    t.add_section()
    uninvested = extra_cash + sell_total - buy_total

    if extra_cash > 0:
        t.add_row("", "[dim]Cash injected[/dim]", "", f"[dim]${extra_cash:,.2f}[/dim]", "")
    t.add_row(
        "",
        "[bold]Trades[/bold]",
        "",
        f"[green]+${buy_total:,.2f}[/green]  [red]-${sell_total:,.2f}[/red]",
        "",
    )
    if uninvested > 0:
        t.add_row("", "[yellow]Uninvested[/yellow]", "", f"[yellow]${uninvested:,.2f}[/yellow]", "")
    return t


def apply_orders(portfolio: Portfolio, orders: list[RebalanceOrder]) -> Portfolio:
    """Apply orders to a portfolio and return the resulting portfolio."""
    result = Portfolio()
    result.set_target_allocation(portfolio.target_allocation.copy())

    qty_map = {sym: stock.quantity for sym, stock in portfolio.holdings.items()}
    price_map = {sym: stock.current_price for sym, stock in portfolio.holdings.items()}

    for o in orders:
        if o.symbol not in qty_map:
            price_map[o.symbol] = o.dollar_amount / Decimal(o.shares)
            qty_map[o.symbol] = 0
        qty_map[o.symbol] += o.shares if o.action == "BUY" else -o.shares

    for sym, qty in qty_map.items():
        if qty > 0:
            result.add_stock(
                Stock(symbol=sym, quantity=qty, current_price=price_map[sym])
            )

    return result


def _rich_to_str(renderable) -> str:
    """Convert a Rich renderable to a string with ANSI codes."""
    buf = StringIO()
    Console(file=buf, width=console.width, force_terminal=True).print(renderable)
    return buf.getvalue().rstrip("\n")


def _getch() -> str:
    """Read a single keypress from stdin, handling escape sequences."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1).decode()
        if ch == "\x1b" and select.select([fd], [], [], 0.05)[0]:
            ch += os.read(fd, 1).decode()
            if select.select([fd], [], [], 0.05)[0]:
                ch += os.read(fd, 1).decode()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def _render_menu(options: list[T], labels: dict[T, str], selected: int) -> str:
    """Render the menu options with the selected item highlighted."""
    lines = []
    for i, opt in enumerate(options):
        if i == selected:
            lines.append(f"{ANSI_BOLD_CYAN}  ▸ {labels[opt]}{ANSI_RESET}")
        else:
            lines.append(f"{ANSI_DIM}    {labels[opt]}{ANSI_RESET}")
    return "\n".join(lines)


def _full_render(
    options: list[T],
    labels: dict[T, str],
    selected: int,
    preview: Callable[[T], Table] | None,
) -> str:
    """Render the full picker UI including preview and menu."""
    parts = []
    if preview:
        parts.append(_rich_to_str(preview(options[selected])))
    parts.append(_render_menu(options, labels, selected))
    return "\n".join(parts) + "\n"


def _clear_lines(count: int) -> None:
    """Clear the specified number of lines above cursor."""
    sys.stdout.write(
        ANSI_MOVE_UP.format(count)
        + "".join(ANSI_CLEAR_LINE for _ in range(count))
        + ANSI_MOVE_UP.format(count)
    )


def pick(
    options: list[T],
    labels: dict[T, str],
    default: int = 0,
    preview: Callable[[T], Table] | None = None,
) -> T:
    """Interactive picker for selecting from a list of options."""
    selected = default

    output = _full_render(options, labels, selected, preview)
    sys.stdout.write(output)
    sys.stdout.flush()
    prev_lines = output.count("\n")

    while True:
        key = _getch()
        if key == "\x1b[A":
            selected = (selected - 1) % len(options)
        elif key == "\x1b[B":
            selected = (selected + 1) % len(options)
        elif key in ("\r", "\n"):
            break
        else:
            continue

        _clear_lines(prev_lines)
        output = _full_render(options, labels, selected, preview)
        sys.stdout.write(output)
        sys.stdout.flush()
        prev_lines = output.count("\n")

    _clear_lines(prev_lines)
    sys.stdout.flush()

    console.print(f"  [bold cyan]▸ {labels[options[selected]]}[/bold cyan]")
    return options[selected]


def _allocation_preview(
    fund: FintualFund, prices: dict[str, Decimal], source: str
) -> Table:
    """Build a preview table for a fund's target allocation."""
    alloc = PORTFOLIOS[fund]
    t = Table(
        box=box.ROUNDED,
        title=FUND_LABELS[fund],
        title_style="bold white",
        caption=source,
        caption_style="dim",
    )
    t.add_column("ETF", style="cyan")
    t.add_column("Name", style="dim")
    t.add_column("Alloc", justify="right", style="yellow")
    t.add_column("Price", justify="right")
    for sym, pct in sorted(alloc.items(), key=lambda x: x[1], reverse=True):
        t.add_row(sym, ETF_NAMES[sym], f"{float(pct):.0%}", f"${prices[sym]:,.2f}")
    return t


def display_rebalance_results(
    portfolio: Portfolio,
    strategy: str,
    orders: list[RebalanceOrder],
    extra_cash: Decimal = Decimal("0"),
) -> None:
    """Display rebalance orders and resulting portfolio."""
    if not orders:
        console.print("[green]  Already balanced — no trades needed.[/green]")
        return

    portfolio_value = portfolio.total_value()
    console.print(orders_table(orders, portfolio_value, extra_cash))

    result = apply_orders(portfolio, orders)
    console.print()
    console.print(
        holdings_table(
            result,
            f"After rebalancing ({STRATEGY_LABELS[strategy]})",
        )
    )


def _pick_fund(preview_fn) -> tuple[FintualFund, dict[str, Decimal]]:
    funds = list(FUND_LABELS.keys())
    console.print()
    console.print("[bold]Portfolio:[/bold]")
    fund = pick(funds, FUND_LABELS, default=DEFAULT_FUND_INDEX, preview=preview_fn)
    return fund, PORTFOLIOS[fund]


def _pick_strategy() -> str:
    console.print()
    console.print("[bold]Strategy:[/bold]")
    return pick(STRATEGIES, STRATEGY_LABELS, default=DEFAULT_STRATEGY_INDEX)


def _prompt_extra_cash(portfolio: Portfolio, strategy: str) -> Decimal:
    if strategy != "trade_minimization":
        return Decimal("0")

    baseline = portfolio.rebalance(strategy=strategy)
    min_cash = smallest_sell(baseline)
    if min_cash <= 0:
        return Decimal("0")

    console.print()
    console.print(
        "  [dim]Adding cash lets the optimizer buy under-weighted positions"
        " without selling, reducing trades.[/dim]"
    )
    console.print(f"  [dim]Minimum to avoid one sell:[/dim] [bold]${min_cash:,.2f}[/bold]")
    return Decimal(Prompt.ask("  Extra cash to inject", default="0"))


def run_cli_loop(prices: dict[str, Decimal], source: str) -> None:
    preview_fn = partial(_allocation_preview, prices=prices, source=source)

    while True:
        fund, allocation = _pick_fund(preview_fn)

        console.print()
        portfolio = build_random_portfolio(prices, allocation)
        console.print(holdings_table(portfolio, f"{FUND_LABELS[fund]} — randomized"))

        strategy = _pick_strategy()
        extra_cash = _prompt_extra_cash(portfolio, strategy)

        console.print()
        orders = portfolio.rebalance(strategy=strategy, extra_cash=extra_cash)
        display_rebalance_results(portfolio, strategy, orders, extra_cash=extra_cash)

        console.print()
        if not Confirm.ask("  Run again?", default=True):
            break


def main() -> None:
    """Entry point for the CLI application."""
    console.print()
    console.print(
        Panel("[bold]Portfolio Rebalancer[/bold] · test & visualize", box=box.DOUBLE)
    )
    console.print()

    with console.status("[bold]Fetching ETF prices from Fintual...[/bold]"):
        prices, price_date = fetch_prices()

    source = (
        f"Fintual · {price_date}" if price_date else "fallback prices (API unreachable)"
    )

    run_cli_loop(prices, source)


if __name__ == "__main__":
    main()
