import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

MARKET_PROFILES = {
    "default": {
        "benchmark_symbol": "SPY",
        "currency": "USD",
    },
    "vietnam": {
        "benchmark_symbol": "VNINDEX",
        "currency": "VND",
    },
}

VIETNAM_EXCHANGE_PREFIXES = {"HOSE", "HSX", "HNX", "UPCOM"}
VIETNAM_SUFFIXES = (".HM", ".HN", ".UPCOM")
VIETNAM_INDEX_SYMBOLS = {"VNINDEX", "VN30"}
VIETNAM_DATA_VENDORS = {
    "core_stock_apis": "vnstock,yfinance",
    "technical_indicators": "vnstock,yfinance",
    "fundamental_data": "vnstock,yfinance",
    "news_data": "vnstock,yfinance",
}


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""
    return str(ticker).strip().upper()


def is_explicit_vietnam_symbol(ticker: str) -> bool:
    """Return True for ticker forms that unambiguously require Vietnam data."""
    normalized = normalize_ticker_symbol(ticker)

    if normalized in VIETNAM_INDEX_SYMBOLS:
        return True

    if ":" in normalized:
        prefix, _ = normalized.split(":", 1)
        return prefix in VIETNAM_EXCHANGE_PREFIXES

    return any(normalized.endswith(suffix) for suffix in VIETNAM_SUFFIXES)


def apply_market_profile_for_symbol(config: dict, ticker: str) -> bool:
    """Mutate config for explicit Vietnam tickers and report whether it changed."""
    if not is_explicit_vietnam_symbol(ticker):
        return False

    config["market_profile"] = "vietnam"
    config["data_vendors"] = VIETNAM_DATA_VENDORS.copy()
    return True

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "openrouter_reasoning_effort": None,  # "xhigh", "high", "medium", "low", "minimal", "none"
    "anthropic_effort": None,           # "high", "medium", "low"
    "llm_timeout": 30,
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Market metadata. Defaults preserve existing US-centric behavior; set
    # market_profile="vietnam" to default benchmark/currency to VNINDEX/VND.
    "market_profile": "default",
    "benchmark_symbol": "SPY",
    "currency": "USD",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance, vnstock
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance, vnstock
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance, vnstock
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance, vnstock
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}


def resolve_config(config=None):
    """Return a config dict with default values and market profile metadata."""
    resolved = DEFAULT_CONFIG.copy()
    resolved["data_vendors"] = DEFAULT_CONFIG["data_vendors"].copy()
    resolved["tool_vendors"] = DEFAULT_CONFIG["tool_vendors"].copy()

    user_config = config or {}
    for key, value in user_config.items():
        if key in {"data_vendors", "tool_vendors"} and isinstance(value, dict):
            merged = resolved[key].copy()
            merged.update(value)
            resolved[key] = merged
        else:
            resolved[key] = value

    profile_name = resolved.get("market_profile", "default")
    profile = MARKET_PROFILES.get(profile_name, MARKET_PROFILES["default"])

    apply_profile_defaults = profile_name != "default"
    if (
        "benchmark_symbol" not in user_config
        or (
            apply_profile_defaults
            and user_config.get("benchmark_symbol") == DEFAULT_CONFIG["benchmark_symbol"]
        )
    ):
        resolved["benchmark_symbol"] = profile["benchmark_symbol"]
    if (
        "currency" not in user_config
        or (
            apply_profile_defaults
            and user_config.get("currency") == DEFAULT_CONFIG["currency"]
        )
    ):
        resolved["currency"] = profile["currency"]

    return resolved
