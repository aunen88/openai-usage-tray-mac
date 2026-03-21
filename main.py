"""OpenAIUsageTray — macOS menu bar app for OpenAI API usage tracking."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

import rumps

from api import AuthError, RateLimitError, UsageData, fetch_usage
from config import Settings, load_settings, save_settings
from menu_builder import (
    build_last_updated, build_model_line, build_summary_lines, build_title,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger(__name__)


class OpenAIUsageTrayApp(rumps.App):
    def __init__(self):
        super().__init__("…", quit_button=None)
        self.settings: Settings = load_settings()
        self.usage: Optional[UsageData] = None
        self.status: str = "no_key" if not self.settings.api_key else "loading"
        self._backoff_s: int = 60
        self._backoff_pending: bool = False

        self._build_menu()

        if self.settings.api_key:
            threading.Thread(target=self._fetch, daemon=True).start()

    # ── Menu construction ──────────────────────────────────────────────────

    def _build_menu(self) -> None:
        self.menu.clear()
        if self.usage:
            today_line, month_line = build_summary_lines(self.usage)
            self.menu.add(rumps.MenuItem(today_line))
            self.menu.add(rumps.MenuItem(month_line))
            self.menu.add(rumps.separator)
            for m in self.usage.models:
                self.menu.add(rumps.MenuItem(build_model_line(m)))
            self.menu.add(rumps.separator)
            if self.status == "stale":
                self.menu.add(rumps.MenuItem("Network error — retrying…"))
            elif self.status == "ratelimit":
                self.menu.add(rumps.MenuItem(f"Rate limited, retrying in {self._backoff_s}s…"))
            else:
                self.menu.add(rumps.MenuItem(build_last_updated(self.usage)))
        elif self.status == "no_key":
            self.menu.add(rumps.MenuItem("Add API key in Settings"))
        elif self.status in ("error", "auth_error"):
            self.menu.add(rumps.MenuItem("Invalid API key — check Settings"))
        else:
            self.menu.add(rumps.MenuItem("Loading…"))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Refresh", callback=self._on_refresh))
        self.menu.add(rumps.MenuItem("Settings", callback=self._on_settings))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def _update_title(self) -> None:
        if self.status == "no_key":
            self.title = "?"
        elif self.status in ("error", "auth_error"):
            self.title = "!"
        elif self.status == "loading":
            self.title = "…"
        elif self.usage:  # ok, stale, ratelimit — show last known value
            self.title = build_title(
                self.usage,
                warning=self.settings.month_warning_usd,
                critical=self.settings.month_critical_usd,
                month_cost=self.usage.month_cost,
            )

    # ── Polling ────────────────────────────────────────────────────────────

    @rumps.timer(60)
    def _poll(self, _sender) -> None:
        """Fires every 60s; skips if not enough time has elapsed per refresh_interval.

        Note: rumps does not support cancelling a @rumps.timer after creation without
        PyObjC. The timer fires every 60s and checks elapsed time instead. This means
        refresh_interval changes take effect within 60s without a restart.
        """
        if self.status in ("ratelimit",) or self._backoff_pending:
            return
        if self.usage:
            elapsed = (datetime.now() - self.usage.fetched_at).total_seconds()
            if elapsed < self.settings.refresh_interval:
                return
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        if not self.settings.api_key:
            self.status = "no_key"
            self._update_title()
            self._build_menu()
            return
        try:
            data = fetch_usage(self.settings.api_key)
            self._backoff_s = 60
            self._backoff_pending = False
            self.usage = data
            self.status = "ok"
            log.info("Fetched: today=$%.2f month=$%.2f", data.today_cost, data.month_cost)
        except AuthError as exc:
            log.warning("Auth error: %s", exc)
            self.status = "error"
        except RateLimitError as exc:
            if exc.retry_after > 0:
                self._backoff_s = min(exc.retry_after, 900)
            else:
                self._backoff_s = min(self._backoff_s * 2, 900)
            log.warning("Rate limited — backing off %ds", self._backoff_s)
            self.status = "ratelimit"
            self._schedule_backoff()
        except Exception as exc:
            log.error("Fetch failed: %s", exc)
            self.status = "error" if not self.usage else "stale"
        self._update_title()
        self._build_menu()

    def _schedule_backoff(self) -> None:
        if self._backoff_pending:
            return
        self._backoff_pending = True
        threading.Timer(self._backoff_s, self._backoff_retry).start()

    def _backoff_retry(self) -> None:
        self._backoff_pending = False
        self.status = "loading"
        threading.Thread(target=self._fetch, daemon=True).start()

    # ── UI actions ─────────────────────────────────────────────────────────

    def _on_refresh(self, _sender) -> None:
        threading.Thread(target=self._fetch, daemon=True).start()

    def _on_settings(self, _sender) -> None:
        w = rumps.Window(
            message="Enter your OpenAI Admin API key\n(usage.read permission required):",
            title="Settings — API Key",
            default_text=self.settings.api_key,
            ok="Next", cancel="Cancel",
            dimensions=(400, 24),
        )
        resp = w.run()
        if not resp.clicked:
            return
        new_key = resp.text.strip()

        w2 = rumps.Window(
            message="Refresh interval in seconds (60–600):",
            title="Settings — Refresh Interval",
            default_text=str(self.settings.refresh_interval),
            ok="Next", cancel="Cancel",
            dimensions=(200, 24),
        )
        resp2 = w2.run()
        if not resp2.clicked:
            return
        try:
            new_interval = max(60, min(int(resp2.text.strip()), 600))
        except ValueError:
            new_interval = self.settings.refresh_interval

        w3 = rumps.Window(
            message="Monthly spend warning threshold (USD):",
            title="Settings — Warning Threshold",
            default_text=str(self.settings.month_warning_usd),
            ok="Next", cancel="Cancel",
            dimensions=(200, 24),
        )
        resp3 = w3.run()
        if not resp3.clicked:
            return
        try:
            new_warning = float(resp3.text.strip())
        except ValueError:
            new_warning = self.settings.month_warning_usd

        w4 = rumps.Window(
            message="Monthly spend critical threshold (USD):",
            title="Settings — Critical Threshold",
            default_text=str(self.settings.month_critical_usd),
            ok="Save", cancel="Cancel",
            dimensions=(200, 24),
        )
        resp4 = w4.run()
        if not resp4.clicked:
            return
        try:
            new_critical = float(resp4.text.strip())
        except ValueError:
            new_critical = self.settings.month_critical_usd

        self.settings = Settings(
            api_key=new_key,
            refresh_interval=new_interval,
            month_warning_usd=new_warning,
            month_critical_usd=new_critical,
        )
        save_settings(self.settings)

        # Trigger a fetch if key was set
        if new_key:
            rumps.alert("Testing connection…")
            threading.Thread(target=self._fetch, daemon=True).start()


def main() -> None:
    OpenAIUsageTrayApp().run()


if __name__ == "__main__":
    main()
