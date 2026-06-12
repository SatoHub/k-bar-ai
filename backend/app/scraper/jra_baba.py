"""JRA official 馬場情報 scraper — 含水率（moisture %）+ クッション値（cushion value）.

JV-Data (DataLab) does NOT expose 含水率 / クッション値; only a coarse condition
code (良/稍重/重/不良). These detailed metrics are published only on the JRA
official site (https://www.jra.go.jp/keiba/baba/), per venue, on race days, and
are NOT historically backfillable. The values are injected client-side (JS), so
Playwright rendering is required — a static fetch returns empty cells.

Page layout (per venue page index{N}.html):
  - 含水率 table: #turf_line td.gm / td.c4 (芝 goal-front / 4-corner),
                  #dirt_line td.gm / td.c4 (ダート goal-front / 4-corner)
  - クッション値: a numeric value near the "クッション値" heading (turf only)

The baba index lists which venues are racing (relative index*.html links →
venue names), so the set of venues is discovered dynamically.
"""

from __future__ import annotations

import logging
import re

from .base import BaseScraper

logger = logging.getLogger(__name__)

BABA_BASE = "https://www.jra.go.jp/keiba/baba/"


def _to_float(text: str | None) -> float | None:
    """'12.3%' / ' 10.2 ' → float; None/empty/'--' → None."""
    if not text:
        return None
    m = re.search(r"-?\d+\.?\d*", text.replace(",", ""))
    return float(m.group(0)) if m else None


class JraBabaScraper(BaseScraper):
    """Scrape per-venue 含水率 / クッション値 from the JRA official site."""

    async def _discover_venues(self) -> dict[str, str]:
        """Return {venue_name: absolute_url} for venues currently shown.

        The baba index navigation links to each racing venue's page via
        relative ``index{N}.html`` hrefs labelled with the venue name.
        """
        await self._ensure_browser()
        page = await self._browser.new_page()
        try:
            await page.goto(BABA_BASE, wait_until="networkidle", timeout=30000)
            anchors = await page.eval_on_selector_all(
                "a[href]",
                """els => els.map(a => ({
                    href: a.getAttribute('href') || '',
                    text: (a.textContent || '').trim(),
                }))""",
            )
        finally:
            await page.close()

        venues: dict[str, str] = {}
        for a in anchors:
            href = a["href"]
            # venue pages are relative 'index.html' / 'index2.html' ... and
            # are labelled with the venue name + 競馬 (e.g. 東京競馬場).
            if re.fullmatch(r"index\d*\.html", href):
                name = re.sub(r"競馬.*$", "", a["text"]).strip()
                if name:
                    venues[name] = BABA_BASE + href
        return venues

    async def _extract_venue(self, url: str) -> dict:
        """Extract moisture + cushion from one venue page (JS-rendered)."""
        await self._ensure_browser()
        page = await self._browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            async def cell(sel: str) -> str | None:
                el = await page.query_selector(sel)
                return (await el.inner_text()).strip() if el else None

            turf_goal = await cell("#turf_line td.gm")
            turf_4c = await cell("#turf_line td.c4")
            dirt_goal = await cell("#dirt_line td.gm")
            dirt_4c = await cell("#dirt_line td.c4")

            # Cushion value (turf only): the measured number near the heading.
            cushion = None
            el = await page.query_selector("[id*=cushion], .cushion")
            if el:
                block = await el.inner_text()
                # The block lists the reference scale (12/10/8/7) and the actual
                # measured value (e.g. 10.2). Take the first decimal number,
                # which the page renders as the measured value.
                m = re.search(r"クッション値\s*([0-9]+\.[0-9]+)", block)
                if not m:
                    m = re.search(r"([0-9]+\.[0-9]+)", block)
                cushion = float(m.group(1)) if m else None
        finally:
            await page.close()

        return {
            "turf_moisture_goal": _to_float(turf_goal),
            "turf_moisture_4c": _to_float(turf_4c),
            "dirt_moisture_goal": _to_float(dirt_goal),
            "dirt_moisture_4c": _to_float(dirt_4c),
            "cushion_value": cushion,
        }

    async def scrape_all_venues(self) -> list[dict]:
        """Scrape every venue currently published. Returns one dict per venue.

        Each dict: {racecourse_name, cushion_value, turf_moisture_goal,
        turf_moisture_4c, dirt_moisture_goal, dirt_moisture_4c}. Venues whose
        page fails are skipped (logged) rather than aborting the whole run.
        """
        venues = await self._discover_venues()
        logger.info("JRA baba: discovered venues=%s", list(venues))
        results: list[dict] = []
        for name, url in venues.items():
            try:
                data = await self._extract_venue(url)
            except Exception as e:  # noqa: BLE001 — one bad venue must not abort
                logger.warning("JRA baba: failed venue %s (%s): %s", name, url, e)
                continue
            data["racecourse_name"] = name
            # Skip venues with no usable data at all (e.g. condition not posted yet).
            if any(
                data.get(k) is not None
                for k in (
                    "cushion_value",
                    "turf_moisture_goal",
                    "dirt_moisture_goal",
                )
            ):
                results.append(data)
            await self._wait()
        return results
