from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Product:
    url: str
    name: str
    original_price: float
    discount_price: float
    discount_pct: float
    image_url: str = ""
    product_id: str = ""
    category: str = ""
    is_promo_2x1: bool = False
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Veredicto
    verdict: str = "PENDING"

    @property
    def savings(self) -> float:
        return round(max(self.original_price - self.discount_price, 0.0), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "name": self.name,
            "original_price": self.original_price,
            "discount_price": self.discount_price,
            "discount_pct": self.discount_pct,
            "image_url": self.image_url,
            "product_id": self.product_id,
            "category": self.category,
            "is_promo_2x1": self.is_promo_2x1,
            "verdict": self.verdict,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_html(cls, item: Any, category: str = "") -> Product | None:
        """Parse a BeautifulSoup <li> product item."""
        try:
            # Product URL and name
            name_tag = item.select_one("a.product-item-link")
            if not name_tag:
                return None
            url = name_tag.get("href", "")
            name = name_tag.get_text(strip=True)
            if not url or not name:
                return None

            # Product ID
            price_box = item.select_one("div.price-box")
            product_id = price_box.get("data-product-id", "") if price_box else ""

            # Discounted price (finalPrice)
            final_tag = item.select_one("span[data-price-type='finalPrice']")
            discount_price = float(final_tag.get("data-price-amount", 0)) if final_tag else 0.0

            # Original price (oldPrice)
            old_tag = item.select_one("span[data-price-type='oldPrice']")
            original_price = float(old_tag.get("data-price-amount", 0)) if old_tag else 0.0

            if discount_price <= 0:
                return None

            # If no old price, there's no discount
            if original_price <= 0 or original_price <= discount_price:
                return None

            # Calculate discount percentage
            discount_pct = round((original_price - discount_price) / original_price * 100, 1)

            # Image
            img_tag = item.select_one("a.product-item-photo img")
            image_url = img_tag.get("src", "") if img_tag else ""

            # Check for 2x1 or promo badges
            badge_tag = item.select_one("p.product-item-discount")
            badge_text = badge_tag.get_text(strip=True).lower() if badge_tag else ""
            is_2x1 = "2x1" in badge_text or "dos por uno" in badge_text

            return cls(
                url=url,
                name=name[:200],
                original_price=round(original_price, 2),
                discount_price=round(discount_price, 2),
                discount_pct=discount_pct,
                image_url=image_url,
                product_id=str(product_id),
                category=category,
                is_promo_2x1=is_2x1,
            )
        except (ValueError, TypeError, AttributeError):
            return None
