from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from coral.config import Config
from coral.models import Product
from coral.state_store import StateStore
from coral.scraper import CoralScraper
from coral.notifier import TelegramNotifier


# ── Fixtures ──

SAMPLE_PRODUCT_HTML = """
<li class="item product product-item">
  <div class="product-item-info" id="product-item-info_123" data-container="product-grid">
    <a class="product photo product-item-photo" href="https://www.coralhipermercados.com/test-product.html" tabindex="-1">
      <img src="https://example.com/img.jpg" alt="Test Product" />
    </a>
    <div class="product-item-details">
      <strong class="product name product-item-name">
        <a class="product-item-link" href="https://www.coralhipermercados.com/test-product">
          Aceite de Oliva Extra Virgen 500ml
        </a>
      </strong>
      <div class="price-box price-final_price" data-role="priceBox" data-product-id="123">
        <span class="old-price">
          <span class="price-container price-final_price tax weee">
            <span id="old-price-123" data-price-amount="15.99" data-price-type="oldPrice" class="price-wrapper">
              <span class="price">$15,99</span>
            </span>
          </span>
        </span>
        <span class="special-price">
          <span class="price-container price-final_price tax weee">
            <span id="product-price-123" data-price-amount="7.99" data-price-type="finalPrice" class="price-wrapper">
              <span class="price">$7,99</span>
            </span>
          </span>
        </span>
      </div>
    </div>
  </div>
</li>
"""

SAMPLE_NO_DISCOUNT_HTML = """
<li class="item product product-item">
  <div class="product-item-info">
    <a class="product-item-link" href="https://www.coralhipermercados.com/no-discount">Sin Descuento</a>
    <div class="price-box price-final_price" data-role="priceBox" data-product-id="456">
      <span class="special-price">
        <span class="price-container">
          <span data-price-amount="10.00" data-price-type="finalPrice" class="price-wrapper">
            <span class="price">$10,00</span>
          </span>
        </span>
      </span>
    </div>
  </div>
</li>
"""

SAMPLE_2X1_HTML = """
<li class="item product product-item">
  <div class="product-item-info">
    <a class="product-item-link" href="https://www.coralhipermercados.com/promo-2x1">Cerveza Pilsener 2x1</a>
    <p class="product-item-discount">- 2x1</p>
    <div class="price-box price-final_price" data-role="priceBox" data-product-id="789">
      <span class="old-price">
        <span class="price-container">
          <span data-price-amount="12.00" data-price-type="oldPrice" class="price-wrapper">
            <span class="price">$12,00</span>
          </span>
        </span>
      </span>
      <span class="special-price">
        <span class="price-container">
          <span data-price-amount="6.00" data-price-type="finalPrice" class="price-wrapper">
            <span class="price">$6,00</span>
          </span>
        </span>
      </span>
    </div>
  </div>
</li>
"""

SAMPLE_PAGE_HTML = """
<html>
<body>
  <ol class="products list items product-items">
    {products}
  </ol>
  <div class="pages">
    <ul class="items pages-items">
      <li class="item current"><strong class="page"><span>1</span></strong></li>
      <li class="item"><a href="/test.html?p=2" class="page"><span>2</span></a></li>
      <li class="item pages-item-next"><a class="action next" href="/test.html?p=2">Next</a></li>
    </ul>
  </div>
</body>
</html>
"""


@pytest.fixture
def config():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        state_file = f.name
    yield Config(state_file=state_file, dry_run=True)
    os.unlink(state_file)


@pytest.fixture
def store(config):
    return StateStore(config)


# ── Model tests ──

def test_product_from_html_discount():
    soup = BeautifulSoup(SAMPLE_PRODUCT_HTML, "html.parser")
    item = soup.select_one("li.product-item")
    product = Product.from_html(item, category="comisariato")

    assert product is not None
    assert product.name == "Aceite de Oliva Extra Virgen 500ml"
    assert product.original_price == 15.99
    assert product.discount_price == 7.99
    assert product.discount_pct == 50.0
    assert product.category == "comisariato"
    assert product.product_id == "123"
    assert product.savings == 8.0


def test_product_from_html_no_discount():
    soup = BeautifulSoup(SAMPLE_NO_DISCOUNT_HTML, "html.parser")
    item = soup.select_one("li.product-item")
    product = Product.from_html(item)

    assert product is None


def test_product_from_html_2x1():
    soup = BeautifulSoup(SAMPLE_2X1_HTML, "html.parser")
    item = soup.select_one("li.product-item")
    product = Product.from_html(item)

    assert product is not None
    assert product.is_promo_2x1 is True
    assert product.discount_pct == 50.0


def test_product_from_html_empty():
    assert Product.from_html(None) is None
    assert Product.from_html(BeautifulSoup("<div></div>", "html.parser")) is None


def test_product_savings():
    p = Product(url="t", name="t", original_price=100, discount_price=60, discount_pct=40)
    assert p.savings == 40.0

    p2 = Product(url="t", name="t", original_price=0, discount_price=0, discount_pct=0)
    assert p2.savings == 0


def test_product_to_dict():
    p = Product(url="t", name="t", original_price=10, discount_price=5, discount_pct=50)
    d = p.to_dict()
    assert d["url"] == "t"
    assert d["discount_pct"] == 50
    assert d["verdict"] == "PENDING"


# ── State Store tests ──

def test_state_store_fresh(store):
    assert store.get_stats()["tracked_products"] == 0
    assert store.get_stats()["total_runs"] == 0


def test_state_store_seen(store):
    assert not store.is_seen("https://example.com/1")
    store.mark_seen("https://example.com/1", {"name": "test"})
    assert store.is_seen("https://example.com/1")
    assert not store.is_seen("https://example.com/2")


def test_state_store_cooldown(store):
    url = "https://example.com/1"
    assert not store.is_in_cooldown(url)
    store.set_cooldown(url)
    assert store.is_in_cooldown(url)


def test_state_store_save_load(config):
    store1 = StateStore(config)
    store1.mark_seen("https://example.com/1", {"name": "test"})
    store1.save()

    store2 = StateStore(config)
    assert store2.is_seen("https://example.com/1")


def test_state_store_stats(store):
    store.increment_runs()
    store.add_alerts(3)
    stats = store.get_stats()
    assert stats["total_runs"] == 1
    assert stats["total_alerts"] == 3


# ── Config tests ──

def test_config_defaults(config):
    assert config.min_discount_pct == 40.0
    assert config.dry_run is True
    assert len(config.categories) > 0


def test_config_validate_dry_run(config):
    errors = config.validate()
    assert errors == []


# ── Scraper tests ──

@patch("coral.scraper.requests.Session.get")
def test_scrape_category_filters(mock_get, config):
    html = SAMPLE_PAGE_HTML.format(products=SAMPLE_PRODUCT_HTML + SAMPLE_NO_DISCOUNT_HTML)
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    scraper = CoralScraper(config)
    products = scraper.scrape_category("/test.html")

    assert len(products) == 1
    assert products[0].discount_pct == 50.0


@patch("coral.scraper.requests.Session.get")
def test_scrape_category_empty_page(mock_get, config):
    html = SAMPLE_PAGE_HTML.format(products="")
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    scraper = CoralScraper(config)
    products = scraper.scrape_category("/empty.html")
    assert len(products) == 0


@patch("coral.scraper.requests.Session.get")
def test_scrape_category_stops_at_empty_page(mock_get, config):
    page1_html = SAMPLE_PAGE_HTML.format(products=SAMPLE_PRODUCT_HTML)
    page2_html = SAMPLE_PAGE_HTML.format(products="")
    mock_resp1 = MagicMock(); mock_resp1.text = page1_html; mock_resp1.raise_for_status = MagicMock()
    mock_resp2 = MagicMock(); mock_resp2.text = page2_html; mock_resp2.raise_for_status = MagicMock()
    mock_get.side_effect = [mock_resp1, mock_resp2]

    scraper = CoralScraper(config)
    products = scraper.scrape_category("/test.html")

    assert mock_get.call_count == 2
    assert len(products) == 1


# ── Notifier tests ──

def test_notifier_dry_run(config):
    notifier = TelegramNotifier(config)
    p = Product(url="t", name="Test Product", original_price=20, discount_price=8, discount_pct=60, category="hogar")
    result = notifier.send_alert(p)
    assert result is True


def test_notifier_summary_dry_run(config):
    notifier = TelegramNotifier(config)
    result = notifier.send_summary(5, 100, {"total_runs": 10, "total_alerts": 30})
    assert result is True


def test_notifier_message_format(config):
    notifier = TelegramNotifier(config)
    p = Product(url="https://test.com", name="Aceite", original_price=10, discount_price=5, discount_pct=50, is_promo_2x1=True)
    msg = notifier._format_message(p)
    assert "50%" in msg
    assert "2x1" in msg
    assert "$5.00" in msg
    assert "$10.00" in msg
