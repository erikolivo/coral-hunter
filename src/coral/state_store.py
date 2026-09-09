from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from .config import Config

logger = logging.getLogger(__name__)


class StateStore:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._state: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if os.path.exists(self.config.state_file):
            try:
                with open(self.config.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state: %s", e)
        return {"seen_products": {}, "alert_cooldowns": {}, "stats": {"total_runs": 0, "total_alerts": 0}}

    def save(self) -> None:
        try:
            with open(self.config.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
            logger.info("State saved")
        except OSError as e:
            logger.error("Failed to save state: %s", e)

    def is_seen(self, url: str) -> bool:
        return url in self._state.get("seen_products", {})

    def mark_seen(self, url: str, product_data: dict[str, Any]) -> None:
        seen = self._state.setdefault("seen_products", {})
        seen[url] = {
            **product_data,
            "seen_at": datetime.now(timezone.utc).isoformat(),
        }
        # Keep last 5000 products
        if len(seen) > 5000:
            oldest = sorted(seen.keys(), key=lambda k: seen[k].get("seen_at", ""))[:1000]
            for k in oldest:
                del seen[k]

    def is_in_cooldown(self, url: str) -> bool:
        cooldowns = self._state.get("alert_cooldowns", {})
        last_alert = cooldowns.get(url)
        if not last_alert:
            return False
        try:
            last_time = datetime.fromisoformat(last_alert)
            now = datetime.now(timezone.utc)
            diff_hours = (now - last_time).total_seconds() / 3600
            return diff_hours < self.config.alert_cooldown_hours
        except (ValueError, TypeError):
            return False

    def set_cooldown(self, url: str) -> None:
        self._state.setdefault("alert_cooldowns", {})[url] = datetime.now(timezone.utc).isoformat()

    def increment_runs(self) -> None:
        self._state.setdefault("stats", {})["total_runs"] = self._state["stats"].get("total_runs", 0) + 1

    def add_alerts(self, count: int) -> None:
        self._state.setdefault("stats", {})["total_alerts"] = self._state["stats"].get("total_alerts", 0) + count

    def get_stats(self) -> dict[str, Any]:
        return {
            "tracked_products": len(self._state.get("seen_products", {})),
            "active_cooldowns": len(self._state.get("alert_cooldowns", {})),
            "total_runs": self._state.get("stats", {}).get("total_runs", 0),
            "total_alerts": self._state.get("stats", {}).get("total_alerts", 0),
        }
