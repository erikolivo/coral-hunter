from __future__ import annotations

import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from .config import Config
from .models import Product

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
}


class CoralScraper:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape_category(self, category_path: str) -> list[Product]:
        """Scrape all pages of a category, return products with discount >= min."""
        all_products: list[Product] = []
        seen_urls: set[str] = set()
        category_name = category_path.split("/")[-1].replace(".html", "")

        for page in range(1, self.config.max_pages_per_category + 1):
            url = f"{self.config.base_url}{category_path}"
            params = {
                "product_list_limit": str(self.config.products_per_page),
            }
            if page > 1:
                params["p"] = str(page)

            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.warning("Request failed for %s page %d: %s", category_path, page, e)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("li.product-item")

            if not items:
                logger.info("No products on %s page %d — done", category_name, page)
                break

            new_count = 0
            for item in items:
                product = Product.from_html(item, category=category_name)
                if product is None:
                    continue

                # Filter: only products with discount >= min
                if product.discount_pct < self.config.min_discount_pct:
                    continue

                if product.url not in seen_urls:
                    seen_urls.add(product.url)
                    product.verdict = "DEAL"
                    all_products.append(product)
                    new_count += 1

            logger.info("%s page %d: %d items, %d deals (≥%.0f%%)",
                        category_name, page, len(items), new_count, self.config.min_discount_pct)

            if new_count == 0 and page > 1:
                break

            if page < self.config.max_pages_per_category:
                time.sleep(self.config.request_delay)

        return all_products

    def scrape_all(self) -> list[Product]:
        """Scrape all configured categories."""
        all_products: list[Product] = []
        seen_urls: set[str] = set()

        for cat in self.config.categories:
            logger.info("Scraping category: %s", cat)
            products = self.scrape_category(cat)
            for p in products:
                if p.url not in seen_urls:
                    seen_urls.add(p.url)
                    all_products.append(p)

        logger.info("Total unique deals across all categories: %d", len(all_products))
        return all_products
