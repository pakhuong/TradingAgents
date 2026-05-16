import pytest

from tradingagents.dataflows import vietnam_sentiment


DNSE_HTML = """
<html><body>
  <a href="/tin-tuc/gvr-chot-quyen-co-tuc">GVR chot quyen tra co tuc bang tien</a>
  <a href="javascript:void(0)">Skip me</a>
</body></html>
"""

CAFEF_RSS_MATCH = """
<rss><channel>
  <item>
    <title>GVR duoc khoi ngoai mua rong trong phien moi</title>
    <description><![CDATA[GVR ghi nhan dong tien tich cuc tren san HOSE.]]></description>
    <link>https://cafef.vn/gvr-duoc-khoi-ngoai-mua-rong.chn</link>
    <pubDate>Fri, 15 May 2026 07:00:00 +0700</pubDate>
  </item>
  <item>
    <title>VNINDEX hoi phuc</title>
    <description>Khong lien quan den ma dang theo doi.</description>
    <link>https://cafef.vn/vnindex-hoi-phuc.chn</link>
    <pubDate>Fri, 15 May 2026 08:00:00 +0700</pubDate>
  </item>
</channel></rss>
"""

RSS_NO_MATCH = """
<rss><channel>
  <item>
    <title>VNINDEX tang diem</title>
    <description>Thanh khoan cai thien.</description>
    <link>https://example.test/vnindex</link>
    <pubDate>Fri, 15 May 2026 07:00:00 +0700</pubDate>
  </item>
</channel></rss>
"""

F319_RSS_MATCH = """
<rss><channel>
  <item>
    <title>SHS co cau lai danh muc</title>
    <description>Thanh vien dien dan ban ve SHS va dong chung khoan.</description>
    <link>https://f319.com/threads/shs.1/</link>
    <pubDate>Fri, 15 May 2026 09:00:00 +0700</pubDate>
  </item>
</channel></rss>
"""


@pytest.mark.unit
def test_fetch_vietnam_sources_parses_dnse_and_cafef(monkeypatch):
    def fake_request(url, timeout):
        if "dnse.com.vn" in url:
            return DNSE_HTML, None
        if "doanh-nghiep" in url:
            return CAFEF_RSS_MATCH, None
        if "cafef.vn" in url:
            return RSS_NO_MATCH, None
        if "finance.vietstock.vn" in url:
            return "<html><body><a href='/GVR/news'>GVR cong bo tin moi</a></body></html>", None
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(vietnam_sentiment, "_request_text", fake_request)

    result = vietnam_sentiment.fetch_vietnam_sentiment_sources(
        "HOSE:GVR",
        "2026-05-09",
        "2026-05-16",
        issuer_news_block="Issuer-scoped GVR news block",
        limit_per_source=3,
    )

    assert "Vietnam sentiment and news sources for HOSE:GVR (provider symbol: GVR)" in result
    assert "Issuer-scoped GVR news block" in result
    assert "GVR chot quyen tra co tuc bang tien" in result
    assert "GVR duoc khoi ngoai mua rong" in result
    assert "GVR cong bo tin moi" in result
    assert "matched provider symbol GVR" in result


@pytest.mark.unit
def test_fetch_vietnam_sources_returns_placeholders_for_unavailable_sources(monkeypatch):
    def fake_request(url, timeout):
        if "dnse.com.vn" in url:
            return None, "<unavailable: HTTP 403>"
        if "cafef.vn" in url:
            return "<rss><channel>", None
        if "finance.vietstock.vn" in url:
            return None, "<unavailable: HTTP 403>"
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(vietnam_sentiment, "_request_text", fake_request)

    result = vietnam_sentiment.fetch_vietnam_sentiment_sources(
        "GVR.HM",
        "2026-05-09",
        "2026-05-16",
    )

    assert "Source: DNSE Senses" in result
    assert "<unavailable: HTTP 403>" in result
    assert "CafeF RSS" in result
    assert "<unavailable: invalid RSS XML>" in result
    assert "Source: VietstockFinance" in result


@pytest.mark.unit
def test_fetch_vietnam_sources_skips_forums_by_default(monkeypatch):
    requested_urls = []

    def fake_request(url, timeout):
        requested_urls.append(url)
        if "cafef.vn" in url:
            return RSS_NO_MATCH, None
        return "<html><body></body></html>", None

    monkeypatch.setattr(vietnam_sentiment, "_request_text", fake_request)

    result = vietnam_sentiment.fetch_vietnam_sentiment_sources(
        "HOSE:GVR",
        "2026-05-09",
        "2026-05-16",
    )

    assert "<disabled by default; enable include_forums=True" in result
    assert not any("f319.com" in url for url in requested_urls)


@pytest.mark.unit
def test_fetch_vietnam_sources_includes_forum_when_enabled(monkeypatch):
    requested_urls = []

    def fake_request(url, timeout):
        requested_urls.append(url)
        if "f319.com" in url:
            return F319_RSS_MATCH, None
        if "cafef.vn" in url:
            return RSS_NO_MATCH, None
        return "<html><body></body></html>", None

    monkeypatch.setattr(vietnam_sentiment, "_request_text", fake_request)

    result = vietnam_sentiment.fetch_vietnam_sentiment_sources(
        "HNX:SHS",
        "2026-05-09",
        "2026-05-16",
        include_forums=True,
    )

    assert any("f319.com" in url for url in requested_urls)
    assert "SHS co cau lai danh muc" in result
    assert "forum-style investor discussion" in result