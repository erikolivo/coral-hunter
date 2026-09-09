from __future__ import annotations

import logging
from typing import Any

import requests

from .config import Config
from .models import Product

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def send_alert(self, product: Product) -> bool:
        text = self._format_message(product)
        if self.config.dry_run:
            logger.info("[DRY RUN] Alert:\n%s", text)
            return True

        url = TELEGRAM_API.format(token=self.config.telegram_bot_token)
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            logger.info("Alert sent: %s", product.name[:40])
            return True
        except requests.RequestException as e:
            logger.error("Failed to send alert: %s", e)
            return False

    def send_summary(self, new_deals: int, total_tracked: int, stats: dict[str, Any]) -> bool:
        lines = [
            "<b>\U0001f3ea Coral Hunter Summary</b>",
            "",
            f"\U0001f525 Nuevos descuentos: {new_deals}",
            f"\U0001f4ca Productos rastreados: {total_tracked}",
            f"\U0001f4c8 Corridas totales: {stats.get('total_runs', 0)}",
            f"\U0001f514 Alertas enviadas: {stats.get('total_alerts', 0)}",
        ]
        text = "\n".join(lines)

        if self.config.dry_run:
            logger.info("[DRY RUN] Summary:\n%s", text)
            return True

        url = TELEGRAM_API.format(token=self.config.telegram_bot_token)
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error("Failed to send summary: %s", e)
            return False

    def _format_message(self, p: Product) -> str:
        promo_badge = " \U0001f195 2x1" if p.is_promo_2x1 else ""
        lines = [
            f"\U0001f525 <b>DESCUENTO {p.discount_pct:.0f}%</b>{promo_badge}",
            "",
            f"\U0001f4f1 <b>{_escape(p.name[:80])}</b>",
            "",
            f"\U0001f4b2 Antes: <s>${p.original_price:.2f}</s>",
            f"\U0001f4b0 Ahora: <b>${p.discount_price:.2f}</b>",
            f"\U0001f4b5 Ahorras: ${p.savings:.2f}",
        ]
        if p.category:
            lines.append(f"\U0001f4c2 Categoría: {p.category}")
        if p.url:
            lines.append(f"\U0001f517 <a href=\"{p.url}\">Ver producto</a>")
        return "\n".join(lines)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
