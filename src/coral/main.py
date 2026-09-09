from __future__ import annotations

import logging
import sys

from .config import Config, load_config
from .scraper import CoralScraper
from .state_store import StateStore
from .notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("coral")


def run(config: Config | None = None) -> None:
    cfg = config or load_config()
    errors = cfg.validate()
    if errors:
        for e in errors:
            logger.error("Config error: %s", e)
        sys.exit(1)

    logger.info("Coral Hunter starting (dry_run=%s)", cfg.dry_run)

    scraper = CoralScraper(cfg)
    state = StateStore(cfg)
    notifier = TelegramNotifier(cfg)

    # Scrape all categories
    products = scraper.scrape_all()
    logger.info("Found %d deals with ≥%.0f%% discount", len(products), cfg.min_discount_pct)

    # Filter: only new products (not seen before)
    new_products = [p for p in products if not state.is_seen(p.url)]
    logger.info("New deals (not seen before): %d", len(new_products))

    # Alert on new deals
    alerts_sent = 0
    for p in new_products:
        if not state.is_in_cooldown(p.url):
            if notifier.send_alert(p):
                state.set_cooldown(p.url)
                alerts_sent += 1

    # Mark all products as seen
    for p in products:
        state.mark_seen(p.url, p.to_dict())

    # Update stats
    state.increment_runs()
    state.add_alerts(alerts_sent)
    state.save()

    # Send summary only if there were new deals
    if new_products:
        stats = state.get_stats()
        notifier.send_summary(len(new_products), stats["tracked_products"], stats)

    logger.info("Run complete: %d deals found, %d new, %d alerts sent",
                len(products), len(new_products), alerts_sent)


if __name__ == "__main__":
    run()
