import unittest

import pytest

from cli.utils import (
    apply_market_profile_for_ticker,
    is_explicit_vietnam_symbol,
    normalize_ticker_symbol,
)
from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.default_config import normalize_vietnam_provider_symbol


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")
        self.assertEqual(normalize_ticker_symbol("7203.T"), "7203.T")
        self.assertEqual(normalize_ticker_symbol("BRK.B"), "BRK.B")

    def test_normalize_ticker_symbol_preserves_vietnam_forms(self):
        self.assertEqual(normalize_ticker_symbol(" fpt "), "FPT")
        self.assertEqual(normalize_ticker_symbol("vnm"), "VNM")
        self.assertEqual(normalize_ticker_symbol(" VNINDEX "), "VNINDEX")
        self.assertEqual(normalize_ticker_symbol("HOSE:FPT"), "HOSE:FPT")

    def test_detects_explicit_vietnam_symbols(self):
        self.assertTrue(is_explicit_vietnam_symbol("HOSE:VIC"))
        self.assertTrue(is_explicit_vietnam_symbol("HSX:VIC"))
        self.assertTrue(is_explicit_vietnam_symbol("HNX:SHS"))
        self.assertTrue(is_explicit_vietnam_symbol("UPCOM:ABC"))
        self.assertTrue(is_explicit_vietnam_symbol("VIC.HM"))
        self.assertTrue(is_explicit_vietnam_symbol("SHS.HN"))
        self.assertTrue(is_explicit_vietnam_symbol("VNINDEX"))
        self.assertTrue(is_explicit_vietnam_symbol("VN30"))
        self.assertFalse(is_explicit_vietnam_symbol("AAPL"))
        self.assertFalse(is_explicit_vietnam_symbol("7203.T"))
        self.assertFalse(is_explicit_vietnam_symbol("BRK.B"))

    def test_normalize_vietnam_provider_symbol(self):
        self.assertEqual(normalize_vietnam_provider_symbol("HOSE:GVR"), "GVR")
        self.assertEqual(normalize_vietnam_provider_symbol("HSX:GVR"), "GVR")
        self.assertEqual(normalize_vietnam_provider_symbol("HNX:SHS"), "SHS")
        self.assertEqual(normalize_vietnam_provider_symbol("UPCOM:ABC"), "ABC")
        self.assertEqual(normalize_vietnam_provider_symbol("GVR.HM"), "GVR")
        self.assertEqual(normalize_vietnam_provider_symbol("SHS.HN"), "SHS")
        self.assertEqual(normalize_vietnam_provider_symbol("ABC.UPCOM"), "ABC")
        self.assertEqual(normalize_vietnam_provider_symbol("VNINDEX"), "VNINDEX")
        self.assertEqual(normalize_vietnam_provider_symbol("VN30"), "VN30")
        self.assertEqual(normalize_vietnam_provider_symbol("BRK.B"), "BRK.B")

    def test_apply_market_profile_for_explicit_vietnam_symbol(self):
        config = {"data_vendors": {"core_stock_apis": "yfinance"}}

        changed = apply_market_profile_for_ticker(config, "HOSE:VIC")

        self.assertTrue(changed)
        self.assertEqual(config["market_profile"], "vietnam")
        self.assertEqual(config["data_vendors"]["core_stock_apis"], "vnstock,yfinance")
        self.assertEqual(config["data_vendors"]["technical_indicators"], "vnstock,yfinance")

    def test_apply_market_profile_ignores_non_explicit_symbol(self):
        config = {"data_vendors": {"core_stock_apis": "yfinance"}}

        changed = apply_market_profile_for_ticker(config, "AAPL")

        self.assertFalse(changed)
        self.assertNotIn("market_profile", config)
        self.assertEqual(config["data_vendors"], {"core_stock_apis": "yfinance"})

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)

    def test_build_instrument_context_mentions_vietnam_examples(self):
        context = build_instrument_context("FPT")
        self.assertIn("FPT", context)
        self.assertIn("HOSE:FPT", context)
        self.assertIn(".HM", context)


if __name__ == "__main__":
    unittest.main()
