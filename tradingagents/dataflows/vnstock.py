import re
from datetime import datetime
from typing import Any, Annotated, Callable

import pandas as pd
from dateutil.relativedelta import relativedelta
from stockstats import wrap

from .errors import DataVendorUnavailableError


OHLCV_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
VIETNAM_EXCHANGE_PREFIXES = {"HOSE", "HSX", "HNX", "UPCOM"}
VIETNAM_SUFFIXES = (".HM", ".HN", ".UPCOM")

INDICATOR_DESCRIPTIONS = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. "
        "Usage: Identify trend direction and serve as dynamic support/resistance. "
        "Tips: It lags price; combine with faster indicators for timely signals."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. "
        "Usage: Confirm overall market trend and identify golden/death cross setups. "
        "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. "
        "Usage: Capture quick shifts in momentum and potential entry points. "
        "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
    ),
    "macd": (
        "MACD: Computes momentum via differences of EMAs. "
        "Usage: Look for crossovers and divergence as signals of trend changes. "
        "Tips: Confirm with other indicators in low-volatility or sideways markets."
    ),
    "macds": (
        "MACD Signal: An EMA smoothing of the MACD line. "
        "Usage: Use crossovers with the MACD line to trigger trades. "
        "Tips: Should be part of a broader strategy to avoid false positives."
    ),
    "macdh": (
        "MACD Histogram: Shows the gap between the MACD line and its signal. "
        "Usage: Visualize momentum strength and spot divergence early. "
        "Tips: Can be volatile; complement with additional filters in fast-moving markets."
    ),
    "rsi": (
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
        "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
    ),
    "boll": (
        "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
        "Usage: Acts as a dynamic benchmark for price movement. "
        "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
    ),
    "boll_ub": (
        "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
        "Usage: Signals potential overbought conditions and breakout zones. "
        "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
    ),
    "boll_lb": (
        "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
        "Usage: Indicates potential oversold conditions. "
        "Tips: Use additional analysis to avoid false reversal signals."
    ),
    "atr": (
        "ATR: Averages true range to measure volatility. "
        "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
        "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
    ),
    "vwma": (
        "VWMA: A moving average weighted by volume. "
        "Usage: Confirm trends by integrating price action with volume data. "
        "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
    ),
    "mfi": (
        "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
        "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
        "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
    ),
}


def _load_vnstock():
    """Import vnstock lazily so default installs and tests can collect without it."""
    try:
        import vnstock as vnstock_module
    except ImportError as exc:
        raise DataVendorUnavailableError(
            "vnstock is not installed. Install vnstock or configure another data vendor."
        ) from exc
    return vnstock_module


def _normalize_vietnam_symbol(symbol: str) -> str:
    """Map Vietnam exchange-qualified variants to vnstock local symbols."""
    normalized = str(symbol).strip().upper()
    if ":" in normalized:
        prefix, remainder = normalized.split(":", 1)
        if prefix in VIETNAM_EXCHANGE_PREFIXES:
            normalized = remainder

    for suffix in VIETNAM_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    return normalized


def _call_with_fallbacks(func: Callable[..., Any], kwargs_options: list[dict[str, Any]]) -> Any:
    last_error = None
    for kwargs in kwargs_options:
        try:
            return func(**kwargs)
        except TypeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return func()


def _make_quote(vnstock_module, symbol: str):
    quote_cls = getattr(vnstock_module, "Quote", None)
    if quote_cls is not None:
        return _call_with_fallbacks(
            quote_cls,
            [
                {"symbol": symbol, "source": "VCI"},
                {"symbol": symbol, "source": "KBS"},
                {"symbol": symbol},
            ],
        )

    vnstock_cls = getattr(vnstock_module, "Vnstock", None)
    if vnstock_cls is not None:
        client = vnstock_cls()
        stock_func = getattr(client, "stock", None)
        if callable(stock_func):
            stock = _call_with_fallbacks(
                stock_func,
                [
                    {"symbol": symbol, "source": "VCI"},
                    {"symbol": symbol, "source": "KBS"},
                    {"symbol": symbol},
                ],
            )
            quote = getattr(stock, "quote", None)
            if quote is not None:
                return quote

    raise DataVendorUnavailableError("vnstock quote API is not available in this environment.")


def _quote_history(quote, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    history = getattr(quote, "history", None)
    if not callable(history):
        raise DataVendorUnavailableError("vnstock quote history API is not available.")

    data = _call_with_fallbacks(
        history,
        [
            {"start": start_date, "end": end_date, "interval": "1D"},
            {"symbol": symbol, "start": start_date, "end": end_date, "interval": "1D"},
            {"start": start_date, "end": end_date, "interval": "d"},
            {"symbol": symbol, "start": start_date, "end": end_date, "interval": "d"},
            {"start": start_date, "end": end_date},
            {"symbol": symbol, "start": start_date, "end": end_date},
        ],
    )
    return pd.DataFrame(data)


def _flatten_columns(data: pd.DataFrame) -> pd.DataFrame:
    if isinstance(data.columns, pd.MultiIndex):
        data = data.copy()
        data.columns = [
            "_".join(str(part) for part in column if str(part))
            for column in data.columns
        ]
    return data


def _normalize_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    """Return a Date/Open/High/Low/Close/Volume DataFrame from provider data."""
    if data is None:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    normalized = _flatten_columns(pd.DataFrame(data).copy())
    if normalized.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    column_aliases = {
        "time": "Date",
        "date": "Date",
        "datetime": "Date",
        "timestamp": "Date",
        "trading_date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    rename_map = {}
    for column in normalized.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key in column_aliases:
            rename_map[column] = column_aliases[key]
    normalized = normalized.rename(columns=rename_map)

    if "Date" not in normalized.columns and not isinstance(normalized.index, pd.RangeIndex):
        normalized = normalized.reset_index().rename(columns={"index": "Date"})

    if "Date" not in normalized.columns or "Close" not in normalized.columns:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    for column in OHLCV_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA

    normalized = normalized[OHLCV_COLUMNS].copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
    normalized = normalized.dropna(subset=["Date", "Close"])

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.sort_values("Date").reset_index(drop=True)
    normalized["Date"] = normalized["Date"].dt.strftime("%Y-%m-%d")
    return normalized


def _filter_ohlcv_range(data: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    if data.empty:
        return data
    dates = pd.to_datetime(data["Date"], errors="coerce")
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    return data[(dates >= start) & (dates <= end)].reset_index(drop=True)


def _format_csv_report(title: str, data: pd.DataFrame, currency: str = "VND") -> str:
    header = f"# {title}\n"
    header += "# Vendor: vnstock\n"
    header += f"# Currency: {currency}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + data.to_csv(index=False)


def _fetch_ohlcv(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    provider_symbol = _normalize_vietnam_symbol(symbol)
    vnstock_module = _load_vnstock()
    quote = _make_quote(vnstock_module, provider_symbol)
    raw_data = _quote_history(quote, provider_symbol, start_date, end_date)
    return _filter_ohlcv_range(_normalize_ohlcv(raw_data), start_date, end_date)


def get_stock(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve Vietnam OHLCV data through vnstock."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    provider_symbol = _normalize_vietnam_symbol(symbol)
    data = _fetch_ohlcv(provider_symbol, start_date, end_date)
    if data.empty:
        return f"No data found for symbol '{provider_symbol}' between {start_date} and {end_date}"

    return _format_csv_report(
        f"Stock data for {provider_symbol} from {start_date} to {end_date}",
        data,
    )


def get_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """Calculate a stockstats indicator from vnstock OHLCV data."""
    indicator = indicator.lower().strip()
    if indicator not in INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(INDICATOR_DESCRIPTIONS.keys())}"
        )

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)
    warmup_start = curr_date_dt - relativedelta(days=max(look_back_days + 365, 400))
    provider_symbol = _normalize_vietnam_symbol(symbol)
    data = _fetch_ohlcv(provider_symbol, warmup_start.strftime("%Y-%m-%d"), curr_date)

    indicator_data = {}
    if not data.empty:
        stats_df = wrap(data.copy())
        stats_df["Date"] = pd.to_datetime(stats_df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        stats_df[indicator]
        for _, row in stats_df.iterrows():
            value = row[indicator]
            indicator_data[row["Date"]] = "N/A" if pd.isna(value) else str(value)

    date_values = []
    current_dt = curr_date_dt
    while current_dt >= before:
        date_str = current_dt.strftime("%Y-%m-%d")
        date_values.append(
            (date_str, indicator_data.get(date_str, "N/A: Not a trading day (weekend or holiday)"))
        )
        current_dt = current_dt - relativedelta(days=1)

    ind_string = "".join(f"{date_str}: {value}\n" for date_str, value in date_values)
    return (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + ind_string
        + "\n\n"
        + INDICATOR_DESCRIPTIONS[indicator]
    )


def _make_finance(vnstock_module, symbol: str):
    finance_cls = getattr(vnstock_module, "Finance", None)
    if finance_cls is not None:
        return _call_with_fallbacks(
            finance_cls,
            [
                {"symbol": symbol, "source": "VCI"},
                {"symbol": symbol, "source": "KBS"},
                {"symbol": symbol},
            ],
        )

    vnstock_cls = getattr(vnstock_module, "Vnstock", None)
    if vnstock_cls is not None:
        client = vnstock_cls()
        stock_func = getattr(client, "stock", None)
        if callable(stock_func):
            stock = _call_with_fallbacks(
                stock_func,
                [
                    {"symbol": symbol, "source": "VCI"},
                    {"symbol": symbol, "source": "KBS"},
                    {"symbol": symbol},
                ],
            )
            finance = getattr(stock, "finance", None)
            if finance is not None:
                return finance

    raise DataVendorUnavailableError("vnstock finance API is not available in this environment.")


def _period_from_freq(freq: str) -> str:
    return "year" if str(freq).lower() in {"annual", "year", "yearly"} else "quarter"


def _parse_date_like(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value)

    text = str(value).strip()
    if re.fullmatch(r"\d{4}", text):
        return pd.Timestamp(f"{text}-12-31")

    quarter_match = re.search(r"(?:(\d{4})\D*Q([1-4])|Q([1-4])\D*(\d{4}))", text, re.IGNORECASE)
    if quarter_match:
        year = quarter_match.group(1) or quarter_match.group(4)
        quarter = quarter_match.group(2) or quarter_match.group(3)
        return pd.Period(f"{year}Q{quarter}").end_time.normalize()

    return pd.to_datetime(text, errors="coerce")


def _filter_financials_by_curr_date(data: pd.DataFrame, curr_date: str | None) -> pd.DataFrame:
    if not curr_date or data is None:
        return pd.DataFrame(data)

    filtered = pd.DataFrame(data).copy()
    if filtered.empty:
        return filtered

    cutoff = pd.Timestamp(curr_date)
    parsed_columns = pd.Series(
        [_parse_date_like(column) for column in filtered.columns],
        index=filtered.columns,
    )
    if parsed_columns.notna().any():
        keep_columns = [
            column
            for column in filtered.columns
            if pd.isna(parsed_columns[column]) or parsed_columns[column] <= cutoff
        ]
        filtered = filtered.loc[:, keep_columns]

    date_column_names = {"date", "time", "report_date", "fiscal_date", "period", "quarter", "year"}
    for column in filtered.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key not in date_column_names:
            continue
        parsed_values = filtered[column].map(_parse_date_like)
        if parsed_values.notna().any():
            filtered = filtered[(parsed_values.isna()) | (parsed_values <= cutoff)]
            break

    return filtered.reset_index(drop=True)


def _call_finance_table(symbol: str, method_name: str, freq: str, curr_date: str | None) -> pd.DataFrame:
    provider_symbol = _normalize_vietnam_symbol(symbol)
    finance = _make_finance(_load_vnstock(), provider_symbol)
    method = getattr(finance, method_name, None)
    if not callable(method):
        raise DataVendorUnavailableError(f"vnstock finance method '{method_name}' is not available.")

    period = _period_from_freq(freq)
    raw_data = _call_with_fallbacks(
        method,
        [
            {"period": period, "lang": "en", "dropna": True},
            {"period": period, "display_mode": "en"},
            {"period": period},
            {},
        ],
    )
    return _filter_financials_by_curr_date(pd.DataFrame(raw_data), curr_date)


def _format_table_report(title: str, data: pd.DataFrame) -> str:
    header = f"# {title}\n"
    header += "# Vendor: vnstock\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + data.to_csv(index=False)


def _make_company(vnstock_module, symbol: str):
    company_cls = getattr(vnstock_module, "Company", None)
    if company_cls is not None:
        return _call_with_fallbacks(
            company_cls,
            [
                {"symbol": symbol, "source": "VCI"},
                {"symbol": symbol, "source": "KBS"},
                {"symbol": symbol},
            ],
        )

    vnstock_cls = getattr(vnstock_module, "Vnstock", None)
    if vnstock_cls is None:
        return None
    client = vnstock_cls()
    stock_func = getattr(client, "stock", None)
    if not callable(stock_func):
        return None
    stock = _call_with_fallbacks(
        stock_func,
        [
            {"symbol": symbol, "source": "VCI"},
            {"symbol": symbol, "source": "KBS"},
            {"symbol": symbol},
        ],
    )
    return getattr(stock, "company", None)


def _call_company_table(symbol: str, method_name: str) -> pd.DataFrame:
    provider_symbol = _normalize_vietnam_symbol(symbol)
    company = _make_company(_load_vnstock(), provider_symbol)
    method = getattr(company, method_name, None) if company is not None else None
    if not callable(method):
        return pd.DataFrame()
    return pd.DataFrame(method())


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get Vietnam company overview and key ratio data through vnstock."""
    provider_symbol = _normalize_vietnam_symbol(ticker)
    sections = []

    overview = _call_company_table(provider_symbol, "overview")
    if not overview.empty:
        sections.append(("Company Overview", overview))

    ratios = _call_finance_table(provider_symbol, "ratio", "quarterly", curr_date)
    if not ratios.empty:
        sections.append(("Key Ratios", ratios))

    if not sections:
        return f"No fundamentals data found for symbol '{provider_symbol}'"

    header = f"# Company Fundamentals for {provider_symbol}\n"
    header += "# Vendor: vnstock\n"
    header += "# Currency: VND\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    body = ""
    for section_title, data in sections:
        body += f"## {section_title}\n\n{data.to_csv(index=False)}\n"
    return header + body.rstrip()


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    provider_symbol = _normalize_vietnam_symbol(ticker)
    data = _call_finance_table(provider_symbol, "balance_sheet", freq, curr_date)
    if data.empty:
        return f"No balance sheet data found for symbol '{provider_symbol}'"
    return _format_table_report(f"Balance Sheet data for {provider_symbol} ({freq})", data)


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    provider_symbol = _normalize_vietnam_symbol(ticker)
    data = _call_finance_table(provider_symbol, "cash_flow", freq, curr_date)
    if data.empty:
        return f"No cash flow data found for symbol '{provider_symbol}'"
    return _format_table_report(f"Cash Flow data for {provider_symbol} ({freq})", data)


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    provider_symbol = _normalize_vietnam_symbol(ticker)
    data = _call_finance_table(provider_symbol, "income_statement", freq, curr_date)
    if data.empty:
        return f"No income statement data found for symbol '{provider_symbol}'"
    return _format_table_report(f"Income Statement data for {provider_symbol} ({freq})", data)


def _filter_news_by_date(data: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    if data.empty:
        return data
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    date_column_names = {"date", "time", "pub_date", "publish_date", "published", "created_at"}
    for column in data.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key not in date_column_names:
            continue
        parsed_values = data[column].map(_parse_date_like)
        if parsed_values.notna().any():
            return data[(parsed_values.isna()) | ((parsed_values >= start) & (parsed_values <= end))]
    return data


def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    provider_symbol = _normalize_vietnam_symbol(ticker)
    news = _call_company_table(provider_symbol, "news")
    news = _filter_news_by_date(news, start_date, end_date)
    if news.empty:
        return f"No vnstock news data available for {provider_symbol} between {start_date} and {end_date}."
    return _format_table_report(f"{provider_symbol} News, from {start_date} to {end_date}", news)


def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 10,
) -> str:
    return (
        "vnstock does not provide Vietnam macro news data through the configured adapter "
        f"for {curr_date} with a {look_back_days}-day lookback."
    )


def get_insider_transactions(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    provider_symbol = _normalize_vietnam_symbol(ticker)
    return f"vnstock does not provide insider transaction data through the configured adapter for {provider_symbol}."
