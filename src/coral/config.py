from __future__ import annotations

import os
from dataclasses import dataclass, field


STORES = {
    "orellana": "https://www.coralhipermercados.com",
    "salitre": "https://www.coralhipermercados.com",
}

OFFER_CATEGORIES = [
    "/ofertas/descuentos-del-mes/comisariato.html",
    "/ofertas/descuentos-del-mes/ferreteria.html",
    "/ofertas/descuentos-del-mes/hogar.html",
    "/ofertas/descuentos-del-mes/iluminacion.html",
    "/ofertas/descuentos-del-mes/material-electrico.html",
    "/ofertas/descuentos-del-mes/stanley.html",
    "/ofertas/descuentos-del-mes/textiles-y-manufactura.html",
    "/ofertas/descuentos-del-mes/automotriz.html",
    "/ofertas/descuentos-del-mes/maquinaria.html",
    "/ofertas/descuentos-del-mes/acabados.html",
    "/ofertas/fiestas-julianas/bebidas-y-licores.html",
    "/ofertas/fiestas-julianas/confiteria.html",
    "/ofertas/fiestas-julianas/hogar.html",
    "/ofertas/fiestas-julianas/snacks-y-mas.html",
]


@dataclass(frozen=True)
class Config:
    # Minimum discount % to alert
    min_discount_pct: float = 40.0

    # Store URLs
    base_url: str = "https://www.coralhipermercados.com"

    # Categories to scrape
    categories: list[str] = field(default_factory=lambda: OFFER_CATEGORIES)

    # Max pages per category
    max_pages_per_category: int = 10

    # Products per page (Magento limit param)
    products_per_page: int = 24

    # Cooldown: don't re-alert same product within N hours
    alert_cooldown_hours: int = 24

    # Telegram
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    # Dry run
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes"))

    # State file
    state_file: str = "state.json"

    # Request delay (seconds) between pages
    request_delay: float = 1.5

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.dry_run:
            if not self.telegram_bot_token:
                errors.append("TELEGRAM_BOT_TOKEN not set")
            if not self.telegram_chat_id:
                errors.append("TELEGRAM_CHAT_ID not set")
        return errors


def load_config() -> Config:
    return Config()
