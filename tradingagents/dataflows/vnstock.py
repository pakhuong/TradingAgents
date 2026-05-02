import os
import re
from importlib import import_module
from datetime import datetime
from typing import Any, Annotated, Callable

import pandas as pd
from dateutil.relativedelta import relativedelta
from stockstats import wrap

from .errors import DataVendorUnavailableError


OHLCV_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
VIETNAM_EXCHANGE_PREFIXES = {"HOSE", "HSX", "HNX", "UPCOM"}
VIETNAM_SUFFIXES = (".HM", ".HN", ".UPCOM")
_VNSTOCK_AUTH_INITIALIZED = False

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

SPONSOR_TA_MAPPING = {
    "close_50_sma": {"method": "sma", "kwargs": {"length": 50}},
    "close_200_sma": {"method": "sma", "kwargs": {"length": 200}},
    "close_10_ema": {"method": "ema", "kwargs": {"length": 10}},
    "macd": {"method": "macd", "kwargs": {"fast": 12, "slow": 26, "signal": 9}},
    "macds": {"method": "macd", "kwargs": {"fast": 12, "slow": 26, "signal": 9}},
    "macdh": {"method": "macd", "kwargs": {"fast": 12, "slow": 26, "signal": 9}},
    "rsi": {"method": "rsi", "kwargs": {"length": 14}},
    "boll": {"method": "bbands", "kwargs": {"length": 20, "std": 2}},
    "boll_ub": {"method": "bbands", "kwargs": {"length": 20, "std": 2}},
    "boll_lb": {"method": "bbands", "kwargs": {"length": 20, "std": 2}},
    "atr": {"method": "atr", "kwargs": {"length": 14}},
    "vwma": {"method": "vwma", "kwargs": {"length": 20}},
    "mfi": {"method": "mfi", "kwargs": {"length": 14}},
}

SPONSOR_TA_COLUMN_TOKENS = {
    "macds": ["signal", "macds"],
    "macdh": ["hist", "macdh"],
    "boll": ["middle", "mid", "basis", "bbm"],
    "boll_ub": ["upper", "bbu", "boll_ub"],
    "boll_lb": ["lower", "bbl", "boll_lb"],
}


def _load_vnstock():
    """Import vnstock lazily so default installs and tests can collect without it."""
    try:
        import vnstock as vnstock_module
    except ImportError as exc:
        raise DataVendorUnavailableError(
            "vnstock is not installed. Install vnstock or configure another data vendor."
        ) from exc
    _initialize_vnstock_auth(vnstock_module)
    return vnstock_module


def _resolve_vnstock_register_user(vnstock_module) -> Callable[..., Any] | None:
    register_user = getattr(vnstock_module, "register_user", None)
    if callable(register_user):
        return register_user

    core_module = getattr(vnstock_module, "core", None)
    utils_module = getattr(core_module, "utils", None) if core_module is not None else None
    auth_module = getattr(utils_module, "auth", None) if utils_module is not None else None
    register_user = getattr(auth_module, "register_user", None) if auth_module is not None else None
    if callable(register_user):
        return register_user

    try:
        from vnstock.core.utils.auth import register_user as register_user_func
    except ImportError:
        return None
    return register_user_func


def _call_register_user(register_user: Callable[..., Any], api_key: str) -> Any:
    last_error = None
    for args, kwargs in (((), {"api_key": api_key}), ((api_key,), {})):
        try:
            return register_user(*args, **kwargs)
        except TypeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return register_user()


def _initialize_vnstock_auth(vnstock_module) -> None:
    global _VNSTOCK_AUTH_INITIALIZED

    if _VNSTOCK_AUTH_INITIALIZED:
        return

    api_key = os.getenv("VNSTOCK_API_KEY", "").strip()
    if not api_key:
        return

    register_user = _resolve_vnstock_register_user(vnstock_module)
    if register_user is None:
        raise RuntimeError(
            "VNSTOCK_API_KEY is set but the installed vnstock package does not expose register_user()."
        )

    try:
        result = _call_register_user(register_user, api_key)
    except Exception as exc:
        raise RuntimeError(
            "VNSTOCK_API_KEY is set but vnstock auth initialization failed."
        ) from exc

    if result is False:
        raise RuntimeError(
            "VNSTOCK_API_KEY is set but vnstock rejected the configured API key."
        )

    _VNSTOCK_AUTH_INITIALIZED = True


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


def _optional_import(module_name: str):
    try:
        return import_module(module_name)
    except ImportError:
        return None


def _load_vnstock_capabilities(
    base_module=None,
    include_base: bool = False,
    include_pipeline: bool = False,
) -> dict[str, Any]:
    if base_module is None and include_base:
        base_module = _load_vnstock()

    return {
        "base": base_module,
        "data": _optional_import("vnstock_data"),
        "ta": _optional_import("vnstock_ta"),
        "news": _optional_import("vnstock_news"),
        "pipeline": _optional_import("vnstock_pipeline") if include_pipeline else None,
    }


def _resolve_module_attr(module, attr_name: str):
    if module is None:
        return None
    return getattr(module, attr_name, None)


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


def _construct_with_sources(factory: Callable[..., Any], symbol: str) -> Any:
    return _call_with_fallbacks(
        factory,
        [
            {"symbol": symbol, "source": "VCI"},
            {"symbol": symbol, "source": "KBS"},
            {"symbol": symbol},
        ],
    )


def _ensure_base_vnstock(capabilities: dict[str, Any]):
    base_module = capabilities.get("base")
    if base_module is not None:
        return base_module
    return _load_vnstock()


def _make_base_quote(vnstock_module, symbol: str):
    quote_cls = getattr(vnstock_module, "Quote", None)
    if quote_cls is not None:
        return _construct_with_sources(quote_cls, symbol)

    vnstock_cls = getattr(vnstock_module, "Vnstock", None)
    if vnstock_cls is not None:
        client = vnstock_cls()
        stock_func = getattr(client, "stock", None)
        if callable(stock_func):
            stock = _construct_with_sources(stock_func, symbol)
            quote = getattr(stock, "quote", None)
            if quote is not None:
                return quote

    raise DataVendorUnavailableError("vnstock quote API is not available in this environment.")


def _make_base_finance(vnstock_module, symbol: str):
    finance_cls = getattr(vnstock_module, "Finance", None)
    if finance_cls is not None:
        return _construct_with_sources(finance_cls, symbol)

    vnstock_cls = getattr(vnstock_module, "Vnstock", None)
    if vnstock_cls is not None:
        client = vnstock_cls()
        stock_func = getattr(client, "stock", None)
        if callable(stock_func):
            stock = _construct_with_sources(stock_func, symbol)
            finance = getattr(stock, "finance", None)
            if finance is not None:
                return finance

    raise DataVendorUnavailableError("vnstock finance API is not available in this environment.")


def _make_base_company(vnstock_module, symbol: str):
    company_cls = getattr(vnstock_module, "Company", None)
    if company_cls is not None:
        return _construct_with_sources(company_cls, symbol)

    vnstock_cls = getattr(vnstock_module, "Vnstock", None)
    if vnstock_cls is None:
        return None
    client = vnstock_cls()
    stock_func = getattr(client, "stock", None)
    if not callable(stock_func):
        return None
    stock = _construct_with_sources(stock_func, symbol)
    return getattr(stock, "company", None)


def _make_quote(vnstock_module, symbol: str):
    capabilities = _load_vnstock_capabilities(vnstock_module)
    sponsor_quote_cls = _resolve_module_attr(capabilities["data"], "Quote")
    if sponsor_quote_cls is not None:
        return _construct_with_sources(sponsor_quote_cls, symbol)
    return _make_base_quote(_ensure_base_vnstock(capabilities), symbol)


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
    quote = _make_quote(None, provider_symbol)
    raw_data = _quote_history(quote, provider_symbol, start_date, end_date)
    return _filter_ohlcv_range(_normalize_ohlcv(raw_data), start_date, end_date)


def _build_sponsor_ta_indicator(indicator_cls, data: pd.DataFrame):
    for args, kwargs in (
        ((data.copy(),), {}),
        ((), {"data": data.copy()}),
        ((), {"df": data.copy()}),
    ):
        try:
            return indicator_cls(*args, **kwargs)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _extract_sponsor_indicator_series(result: Any, indicator: str) -> pd.Series | None:
    if isinstance(result, pd.Series):
        return result.reset_index(drop=True)

    if isinstance(result, dict):
        result = pd.DataFrame(result)

    if not isinstance(result, pd.DataFrame):
        return None

    if result.empty:
        return None

    lowered_columns = {str(column).lower(): column for column in result.columns}
    exact_match = lowered_columns.get(indicator)
    if exact_match is not None:
        return result[exact_match].reset_index(drop=True)

    for token in SPONSOR_TA_COLUMN_TOKENS.get(indicator, []):
        matches = [column for column in result.columns if token in str(column).lower()]
        if len(matches) == 1:
            return result[matches[0]].reset_index(drop=True)

    if len(result.columns) == 1:
        return result.iloc[:, 0].reset_index(drop=True)

    return None


def _compute_indicator_with_sponsor_ta(data: pd.DataFrame, indicator: str) -> pd.DataFrame | None:
    mapping = SPONSOR_TA_MAPPING.get(indicator)
    ta_module = _load_vnstock_capabilities()["ta"]
    if mapping is None or ta_module is None:
        return None

    indicator_cls = _resolve_module_attr(ta_module, "Indicator")
    if indicator_cls is None:
        return None

    ta_indicator = _build_sponsor_ta_indicator(indicator_cls, data)
    if ta_indicator is None:
        return None

    method = getattr(ta_indicator, mapping["method"], None)
    if not callable(method):
        return None

    try:
        result = method(**mapping["kwargs"])
    except Exception:
        return None

    series = _extract_sponsor_indicator_series(result, indicator)
    if series is None or len(series) != len(data):
        return None

    return pd.DataFrame({
        "Date": pd.to_datetime(data["Date"], errors="coerce").dt.strftime("%Y-%m-%d"),
        indicator: series,
    })


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

    indicator_rows = pd.DataFrame(columns=["Date", indicator])
    if not data.empty:
        indicator_rows = _compute_indicator_with_sponsor_ta(data, indicator)
        if indicator_rows is None:
            stats_df = wrap(data.copy())
            stats_df["Date"] = pd.to_datetime(stats_df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
            stats_df[indicator]
            indicator_rows = stats_df[["Date", indicator]].copy()
        indicator_rows = indicator_rows.dropna(subset=["Date"])
        indicator_rows = indicator_rows[indicator_rows["Date"] <= curr_date].reset_index(drop=True)

    if indicator_rows.empty:
        return (
            f"## {indicator} values up to {curr_date}:\n\n"
            + "No trading-session data available.\n\n"
            + INDICATOR_DESCRIPTIONS[indicator]
        )

    rendered_rows = indicator_rows.tail(max(look_back_days + 1, 1)).reset_index(drop=True)
    latest_session = rendered_rows["Date"].iloc[-1]
    header_start = rendered_rows["Date"].iloc[0]
    note = ""
    if latest_session != curr_date:
        note = (
            f"Note: {curr_date} is not a trading day. Using the latest available trading session on {latest_session}.\n\n"
        )

    ind_string = "".join(
        f"{row['Date']}: {'N/A' if pd.isna(row[indicator]) else row[indicator]}\n"
        for _, row in rendered_rows.iterrows()
    )
    return (
        f"## {indicator} values from {header_start} to {latest_session}:\n\n"
        + note
        + ind_string
        + "\n\n"
        + INDICATOR_DESCRIPTIONS[indicator]
    )


def _make_finance(vnstock_module, symbol: str):
    capabilities = _load_vnstock_capabilities(vnstock_module)
    sponsor_finance_cls = _resolve_module_attr(capabilities["data"], "Finance")
    if sponsor_finance_cls is not None:
        return _construct_with_sources(sponsor_finance_cls, symbol)
    return _make_base_finance(_ensure_base_vnstock(capabilities), symbol)


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
    finance = _make_finance(None, provider_symbol)
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
    capabilities = _load_vnstock_capabilities(vnstock_module)
    sponsor_company_cls = _resolve_module_attr(capabilities["data"], "Company")
    if sponsor_company_cls is not None:
        return _construct_with_sources(sponsor_company_cls, symbol)
    return _make_base_company(_ensure_base_vnstock(capabilities), symbol)


def _call_company_table(symbol: str, method_name: str) -> pd.DataFrame:
    provider_symbol = _normalize_vietnam_symbol(symbol)
    company = _make_company(None, provider_symbol)
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


def _coerce_news_records(records: Any, site_name: str | None = None) -> pd.DataFrame:
    if isinstance(records, pd.DataFrame):
        frame = records.copy()
    elif isinstance(records, list):
        frame = pd.DataFrame(records)
    elif isinstance(records, dict):
        frame = pd.DataFrame([records])
    else:
        return pd.DataFrame()

    if site_name and not frame.empty and "site" not in frame.columns:
        frame["site"] = site_name
    return frame


def _sort_news_by_date(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data

    date_column_names = {"date", "time", "pub_date", "publish_date", "published", "created_at", "publish_time"}
    for column in data.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key not in date_column_names:
            continue
        parsed_values = data[column].map(_parse_date_like)
        if parsed_values.notna().any():
            return (
                data.assign(_sort_date=parsed_values)
                .sort_values("_sort_date", ascending=False)
                .drop(columns=["_sort_date"])
                .reset_index(drop=True)
            )
    return data.reset_index(drop=True)


def _list_supported_news_sites(news_module) -> list[str]:
    list_supported_sites = _resolve_module_attr(news_module, "list_supported_sites")
    supported_sites = []
    if callable(list_supported_sites):
        try:
            supported_sites = list_supported_sites()
        except Exception:
            supported_sites = []
    elif isinstance(getattr(news_module, "SUPPORTED_SITES", None), (list, tuple, set, dict)):
        supported_sites = getattr(news_module, "SUPPORTED_SITES")

    if isinstance(supported_sites, dict):
        supported_sites = list(supported_sites.values())

    site_names = []
    for site in supported_sites or []:
        if isinstance(site, str):
            site_names.append(site)
            continue
        if isinstance(site, dict):
            name = site.get("site_name") or site.get("name") or site.get("site")
            if name:
                site_names.append(str(name))
    return site_names


def _resolve_news_crawler_cls(news_module):
    crawler_cls = _resolve_module_attr(news_module, "Crawler")
    if crawler_cls is not None:
        return crawler_cls

    for module_name in ("vnstock_news.crawler", "vnstock_news.core.crawler"):
        crawler_module = _optional_import(module_name)
        crawler_cls = _resolve_module_attr(crawler_module, "Crawler")
        if crawler_cls is not None:
            return crawler_cls

    return None


def _fetch_global_news_with_sponsor(curr_date: str, look_back_days: int, limit: int) -> pd.DataFrame:
    news_module = _load_vnstock_capabilities()["news"]
    if news_module is None:
        return pd.DataFrame()

    crawler_cls = _resolve_news_crawler_cls(news_module)
    site_names = _list_supported_news_sites(news_module)
    if crawler_cls is None or not site_names:
        return pd.DataFrame()

    start_date = (pd.Timestamp(curr_date) - pd.Timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    article_frames = []
    for site_name in site_names:
        try:
            crawler = _call_with_fallbacks(
                crawler_cls,
                [
                    {"site_name": site_name},
                    {"site": site_name},
                    {"source": site_name},
                    {},
                ],
            )
        except Exception:
            continue

        get_articles = getattr(crawler, "get_articles", None)
        if not callable(get_articles):
            continue

        try:
            records = _call_with_fallbacks(get_articles, [{"limit": max(limit, 1)}, {}])
        except Exception:
            continue

        frame = _coerce_news_records(records, site_name)
        if frame.empty:
            continue

        article_frames.append(frame)
        filtered = _filter_news_by_date(pd.concat(article_frames, ignore_index=True), start_date, curr_date)
        if len(filtered) >= limit:
            break

    if not article_frames:
        return pd.DataFrame()

    data = _filter_news_by_date(pd.concat(article_frames, ignore_index=True), start_date, curr_date)
    if data.empty:
        return data
    return _sort_news_by_date(data).head(max(limit, 1)).reset_index(drop=True)


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
    datetime.strptime(curr_date, "%Y-%m-%d")

    news = _fetch_global_news_with_sponsor(curr_date, look_back_days, limit)
    if news.empty:
        return (
            "vnstock does not provide Vietnam macro news data through the configured adapter "
            f"for {curr_date} with a {look_back_days}-day lookback."
        )
    return _format_table_report(
        f"Vietnam Global News up to {curr_date} ({look_back_days}-day lookback)",
        news,
    )


def get_insider_transactions(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    provider_symbol = _normalize_vietnam_symbol(ticker)
    insider_transactions = _call_company_table(provider_symbol, "insider_trading")
    if insider_transactions.empty:
        return f"No vnstock insider transaction data available for {provider_symbol}."
    return _format_table_report(f"Insider Transactions data for {provider_symbol}", insider_transactions)
