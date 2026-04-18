import calendar
from datetime import datetime

from src.config import CURRENCY, TIMEZONE

METHOD_LABELS = {"cash": "💵 Cash", "transfer": "🏦 Transfer"}
TYPE_LABELS = {"expense": "💸 Expense", "income": "💰 Income"}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _exp(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["type"] == "expense"]


def _inc(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["type"] == "income"]


def _total(rows: list[dict]) -> float:
    return sum(r["amount"] for r in rows)


def _by_category(rows: list[dict]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        cat = row.get("category", "Other")
        result[cat] = result.get(cat, 0.0) + row["amount"]
    return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))


def _by_method(rows: list[dict]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        m = row.get("method", "cash")
        result[m] = result.get(m, 0.0) + row["amount"]
    return result


def _savings_rate(income: float, expenses: float) -> float | None:
    if income <= 0:
        return None
    return max(0.0, (income - expenses) / income * 100)


def _bar(percent: float, length: int = 10) -> str:
    filled = round(percent / 100 * length)
    return "▓" * filled + "░" * (length - filled)


def _bar_scaled(value: float, max_value: float, length: int = 8) -> str:
    if max_value <= 0:
        return "░" * length
    filled = round(value / max_value * length)
    return "▓" * filled + "░" * (length - filled)


def _fmt(amount: float) -> str:
    return f"{CURRENCY} {amount:,.0f}"


def _rate_str(income: float, expenses: float) -> str:
    rate = _savings_rate(income, expenses)
    if rate is None:
        return "— (no income)"
    return f"{_bar(rate)}  {rate:.0f}%"


# ---------------------------------------------------------------------------
# Recent Transactions
# ---------------------------------------------------------------------------

def format_recent(rows: list[dict]) -> str:
    if not rows:
        return "No transactions recorded yet."

    lines = ["🕐 <b>Recent Transactions</b>", ""]
    for row in rows:
        sign      = "−" if row["type"] == "expense" else "+"
        type_icon = "💸" if row["type"] == "expense" else "💰"
        method    = "💵" if row.get("method") == "cash" else "🏦"
        note      = f"\n      <i>{row['note']}</i>" if row.get("note") else ""
        lines.append(f"{type_icon} {row['category']:<14} {method}  {sign} {_fmt(row['amount'])}{note}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# After-save summary (shown immediately after confirming a transaction)
# ---------------------------------------------------------------------------

def format_after_save(
    tx_type: str,
    category: str,
    amount: float,
    method: str,
    month_rows: list[dict],
) -> str:
    income_m = _total(_inc(month_rows))
    expenses_m = _total(_exp(month_rows))
    saved_m = income_m - expenses_m

    lines = [
        f"✅ <b>Saved!</b>",
        f"{TYPE_LABELS.get(tx_type, tx_type)}  ·  {category}  ·  {METHOD_LABELS.get(method, method)}",
        f"{_fmt(amount)}",
        "",
        "<b>This Month</b>",
        f"💰 Income    —  {_fmt(income_m)}",
        f"💸 Expenses  —  {_fmt(expenses_m)}",
        f"🏦 Saved     —  {_fmt(saved_m)}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Daily Report
# ---------------------------------------------------------------------------

def format_daily_report(today_rows: list[dict], month_rows: list[dict]) -> str:
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%A, %b %-d %Y")
    month_name = now.strftime("%B")

    today_exp = _exp(today_rows)
    today_inc = _inc(today_rows)
    month_exp = _exp(month_rows)
    month_inc = _inc(month_rows)

    spent_today = _total(today_exp)
    earned_today = _total(today_inc)
    income_m = _total(month_inc)
    expenses_m = _total(month_exp)
    saved_m = income_m - expenses_m
    tx_count = len(today_rows)

    lines = [
        f"📅 <b>Daily Report</b>  ·  {date_str}",
        "",
        "<b>Today</b>",
        f"💸 Spent    —  {_fmt(spent_today)}",
        f"💰 Earned   —  {_fmt(earned_today)}",
        "",
        f"<b>{month_name} So Far</b>",
        f"💰 Income    —  {_fmt(income_m)}",
        f"💸 Expenses  —  {_fmt(expenses_m)}",
        f"🏦 Saved     —  {_fmt(saved_m)}",
        f"📊 Rate         {_rate_str(income_m, expenses_m)}",
    ]

    if today_exp:
        lines += ["", "<b>Today's Expenses</b>"]
        for cat, amt in list(_by_category(today_exp).items())[:5]:
            lines.append(f"  • {cat}  —  {_fmt(amt)}")

    if today_rows:
        by_method = _by_method(today_rows)
        if len(by_method) > 0:
            lines += ["", "<b>Today by Method</b>"]
            for method in ("cash", "transfer"):
                if method in by_method:
                    lines.append(f"  {METHOD_LABELS[method]}  —  {_fmt(by_method[method])}")

    lines += ["", f"<i>📝 {tx_count} transaction{'s' if tx_count != 1 else ''} today</i>"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Monthly Report
# ---------------------------------------------------------------------------

def format_monthly_report(this_rows: list[dict], last_rows: list[dict]) -> str:
    now = datetime.now(TIMEZONE)
    month_year = now.strftime("%B %Y")

    this_exp = _exp(this_rows)
    this_inc = _inc(this_rows)
    last_exp = _exp(last_rows)
    last_inc = _inc(last_rows)

    income_t = _total(this_inc)
    expenses_t = _total(this_exp)
    saved_t = income_t - expenses_t

    income_l = _total(last_inc)
    expenses_l = _total(last_exp)
    saved_l = income_l - expenses_l

    tx_count = len(this_rows)

    lines = [
        f"📆 <b>Monthly Report</b>  ·  {month_year}",
        "",
        "<b>Overview</b>",
        f"💰 Income    —  {_fmt(income_t)}",
        f"💸 Expenses  —  {_fmt(expenses_t)}",
        f"🏦 Saved     —  {_fmt(saved_t)}",
        f"📊 Rate         {_rate_str(income_t, expenses_t)}",
    ]

    # Cash vs Transfer net balance
    exp_by_m = _by_method(this_exp)
    inc_by_m = _by_method(this_inc)
    all_methods = set(list(exp_by_m) + list(inc_by_m))
    if all_methods:
        lines += ["", "<b>Balance by Method</b>"]
        for method in ("cash", "transfer"):
            if method in all_methods:
                net = inc_by_m.get(method, 0.0) - exp_by_m.get(method, 0.0)
                lines.append(f"  {METHOD_LABELS[method]}  net  —  {_fmt(net)}")

    if this_exp:
        total_exp = expenses_t or 1.0
        lines += ["", "<b>Expense Breakdown</b>"]
        for cat, amt in list(_by_category(this_exp).items())[:6]:
            pct = amt / total_exp * 100
            lines.append(f"  • {cat}  —  {_fmt(amt)}  ({pct:.0f}%)")

    lines += ["", "<b>vs Last Month</b>"]

    if expenses_l > 0:
        pct_e = (expenses_t - expenses_l) / expenses_l * 100
        arrow_e = "↑" if pct_e > 0 else "↓"
        sign_e = "⚠️" if pct_e > 0 else "✅"
        lines.append(f"💸 Expenses  —  {_fmt(expenses_t)}   {arrow_e} {abs(pct_e):.0f}%  {sign_e}")
    else:
        lines.append(f"💸 Expenses  —  {_fmt(expenses_t)}   —")

    if saved_l != 0:
        pct_s = (saved_t - saved_l) / abs(saved_l) * 100
        arrow_s = "↑" if pct_s > 0 else "↓"
        sign_s = "✅" if pct_s > 0 else "⚠️"
        lines.append(f"🏦 Savings   —  {_fmt(saved_t)}   {arrow_s} {abs(pct_s):.0f}%  {sign_s}")
    else:
        lines.append(f"🏦 Savings   —  {_fmt(saved_t)}   —")

    lines += ["", f"<i>📝 {tx_count} transactions this month</i>"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Yearly Report
# ---------------------------------------------------------------------------

def format_yearly_report(year_rows: list[dict]) -> str:
    now = datetime.now(TIMEZONE)
    year = now.year

    year_exp = _exp(year_rows)
    year_inc = _inc(year_rows)

    income_t = _total(year_inc)
    expenses_t = _total(year_exp)
    saved_t = income_t - expenses_t
    tx_count = len(year_rows)

    lines = [
        f"🗓 <b>Year in Review</b>  ·  {year}",
        "",
        "<b>Overview</b>",
        f"💰 Income    —  {_fmt(income_t)}",
        f"💸 Expenses  —  {_fmt(expenses_t)}",
        f"🏦 Saved     —  {_fmt(saved_t)}",
        f"📊 Rate         {_rate_str(income_t, expenses_t)}",
    ]

    # Monthly savings snapshot
    monthly_income: dict[int, float] = {}
    monthly_expenses: dict[int, float] = {}

    for row in year_inc:
        try:
            m = int(row["date"].split("-")[1])
            monthly_income[m] = monthly_income.get(m, 0.0) + row["amount"]
        except (ValueError, IndexError):
            continue
    for row in year_exp:
        try:
            m = int(row["date"].split("-")[1])
            monthly_expenses[m] = monthly_expenses.get(m, 0.0) + row["amount"]
        except (ValueError, IndexError):
            continue

    months_with_data = sorted(set(list(monthly_income) + list(monthly_expenses)))

    if months_with_data:
        monthly_saved = {
            m: monthly_income.get(m, 0.0) - monthly_expenses.get(m, 0.0)
            for m in months_with_data
        }
        max_abs = max(abs(v) for v in monthly_saved.values()) or 1.0

        lines += ["", "<b>Monthly Savings</b>"]
        for m, saved in sorted(monthly_saved.items()):
            abbr = calendar.month_abbr[m]
            bar = _bar_scaled(max(saved, 0.0), max_abs)
            lines.append(f"  {abbr}  {bar}  {_fmt(saved)}")

        best_month = max(monthly_saved, key=monthly_saved.get)
        worst_month = min(monthly_saved, key=monthly_saved.get)
        lines += [
            "",
            f"🏆 Best   ·  {calendar.month_name[best_month]}  —  {_fmt(monthly_saved[best_month])}",
            f"📉 Worst  ·  {calendar.month_name[worst_month]}  —  {_fmt(monthly_saved[worst_month])}",
        ]

    if year_exp:
        total_exp = expenses_t or 1.0
        lines += ["", "<b>Top Expense Categories</b>"]
        for i, (cat, amt) in enumerate(list(_by_category(year_exp).items())[:5], 1):
            pct = amt / total_exp * 100
            lines.append(f"  {i}.  {cat}  —  {_fmt(amt)}  ({pct:.0f}%)")

    lines += ["", f"<i>📝 {tx_count} transactions in {year}</i>"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Summary — All Time
# ---------------------------------------------------------------------------

def format_summary(all_rows: list[dict], month_rows: list[dict]) -> str:
    now = datetime.now(TIMEZONE)
    month_name = now.strftime("%B")

    all_exp = _exp(all_rows)
    all_inc = _inc(all_rows)

    total_income = _total(all_inc)
    total_expenses = _total(all_exp)
    net_balance = total_income - total_expenses

    # Cash vs Transfer (all time net per method)
    cash_net = (
        sum(r["amount"] for r in all_inc if r.get("method") == "cash")
        - sum(r["amount"] for r in all_exp if r.get("method") == "cash")
    )
    transfer_net = (
        sum(r["amount"] for r in all_inc if r.get("method") == "transfer")
        - sum(r["amount"] for r in all_exp if r.get("method") == "transfer")
    )

    tx_total = len(all_rows)

    # Tracking period
    all_dates = []
    for row in all_rows:
        try:
            all_dates.append(datetime.strptime(row["date"], "%Y-%m-%d"))
        except ValueError:
            continue

    if all_dates:
        first = min(all_dates)
        tracking_since = first.strftime("%B %Y")
        delta_months = (now.year - first.year) * 12 + (now.month - first.month)
        years, months = divmod(delta_months, 12)
        if years > 0 and months > 0:
            period_str = f"{years} yr{'s' if years > 1 else ''} {months} mo{'s' if months > 1 else ''}"
        elif years > 0:
            period_str = f"{years} yr{'s' if years > 1 else ''}"
        else:
            period_str = f"{months} mo{'s' if months > 1 else ''}"
    else:
        tracking_since = "—"
        period_str = "—"

    month_inc = _inc(month_rows)
    month_exp = _exp(month_rows)
    income_m = _total(month_inc)
    expenses_m = _total(month_exp)
    saved_m = income_m - expenses_m
    rate = _savings_rate(income_m, expenses_m)
    rate_str = f"  {rate:.0f}%" if rate is not None else "  —"

    lines = [
        "📊 <b>Summary</b>  ·  All Time",
        f"<i>Since {tracking_since}  ·  {period_str}</i>",
        "",
        "<b>Overall</b>",
        f"💰 Total Income    —  {_fmt(total_income)}",
        f"💸 Total Expenses  —  {_fmt(total_expenses)}",
        f"🏦 Net Balance     —  {_fmt(net_balance)}",
        "",
        "<b>Balance by Method</b>",
        f"  💵 Cash      —  {_fmt(cash_net)}",
        f"  🏦 Transfer  —  {_fmt(transfer_net)}",
        "",
        f"<b>This Month  ({month_name})</b>",
        f"💰 Income    —  {_fmt(income_m)}",
        f"💸 Expenses  —  {_fmt(expenses_m)}",
        f"🏦 Saved     —  {_fmt(saved_m)}{rate_str}",
        "",
        f"<i>📝 {tx_total:,} total transactions</i>",
    ]
    return "\n".join(lines)
