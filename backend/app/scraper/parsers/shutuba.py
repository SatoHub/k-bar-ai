"""Parse netkeiba shutuba (出馬表) page to extract horse entries."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def _extract_netkeiba_id(href: str | None, pattern: str) -> str | None:
    """Extract ID from netkeiba URL path."""
    if not href:
        return None
    m = re.search(pattern, href)
    return m.group(1) if m else None


def _parse_weight_text(text: str) -> tuple[int | None, int | None]:
    """Parse '480(+4)' or '480(-2)' into (weight, diff)."""
    m = re.match(r"(\d+)\(([+-]?\d+)\)", text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    # Weight only, no diff
    m2 = re.match(r"(\d+)", text.strip())
    if m2:
        return int(m2.group(1)), None
    return None, None


def _parse_sex_age(text: str) -> tuple[str | None, int | None]:
    """Parse '牡3' into ('牡', 3)."""
    m = re.match(r"([牡牝セ騸])(\d+)", text.strip())
    if m:
        return m.group(1), int(m.group(2))
    return None, None


def parse_shutuba(html: str, race_id: str) -> dict:
    """Parse shutuba page and return race + entries data.

    Returns:
        {
            "race_id": "202505021211",
            "race_name": "...",
            "race_info": {"surface": "芝", "distance_m": 2400, ...},
            "entries": [
                {
                    "bracket_number": 1,
                    "post_position": 1,
                    "horse_name": "...",
                    "horse_netkeiba_id": "2022104922",
                    "sex": "牡",
                    "age": 3,
                    "weight_carried_kg": 57.0,
                    "jockey_name": "...",
                    "trainer_name": "...",
                    "trainer_region": "美浦" or "栗東",
                    "horse_weight_kg": 480,
                    "horse_weight_diff": 4,
                },
                ...
            ]
        }
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict = {"race_id": race_id, "entries": []}

    # Race name
    name_el = soup.select_one("div.RaceName")
    result["race_name"] = name_el.get_text(strip=True) if name_el else None

    # Race info (surface, distance, etc.)
    race_info = _parse_race_info(soup)
    result["race_info"] = race_info

    # Parse entry rows
    table = soup.select_one("table.Shutuba_Table")
    if not table:
        return result

    for row in table.select("tr.HorseList"):
        tds = row.find_all("td")
        if len(tds) < 9:
            continue

        entry = _parse_entry_row(tds)
        if entry:
            result["entries"].append(entry)

    return result


def _parse_race_info(soup: BeautifulSoup) -> dict:
    """Extract race metadata (surface, distance, weather, etc.)."""
    info: dict = {}

    # RaceData01 contains surface/distance/weather/condition
    data01 = soup.select_one("div.RaceData01")
    if data01:
        text = data01.get_text(strip=True)

        # Surface and distance: "芝2400m" or "ダ1200m"
        m = re.search(r"(芝|ダ|障)(\d+)m", text)
        if m:
            surface_map = {"芝": "芝", "ダ": "ダート", "障": "障害"}
            info["surface"] = surface_map.get(m.group(1), m.group(1))
            info["distance_m"] = int(m.group(2))

        # Direction
        m_dir = re.search(r"(右|左|直線)", text)
        if m_dir:
            info["direction"] = m_dir.group(1)

        # Weather
        m_weather = re.search(r"天候\s*[:：]\s*(\S+)", text)
        if m_weather:
            info["weather"] = m_weather.group(1)

        # Track condition
        m_cond = re.search(r"(芝|ダート)\s*[:：]\s*(\S+)", text)
        if m_cond:
            info["track_condition"] = m_cond.group(2)

    # RaceData02 contains racecourse, race number, etc.
    data02 = soup.select_one("div.RaceData02")
    if data02:
        spans = data02.select("span")
        for span in spans:
            text = span.get_text(strip=True)
            # Racecourse name
            m_course = re.match(r"(\d+)回(\S+?)(\d+)日目", text)
            if m_course:
                info["racecourse_name"] = m_course.group(2)

    return info


def _parse_entry_row(tds) -> dict | None:
    """Parse a single entry row from shutuba table."""
    try:
        # Bracket number (枠番) - td[0]
        bracket = tds[0].get_text(strip=True)
        bracket_number = int(bracket) if bracket.isdigit() else None

        # Post position (馬番) - td[1]
        umaban = tds[1].get_text(strip=True)
        post_position = int(umaban) if umaban.isdigit() else None

        # Horse info - td[3] (skip checkbox td[2])
        horse_td = tds[3]
        horse_link = horse_td.select_one("a[href*='/horse/']")
        horse_name = None
        horse_netkeiba_id = None
        if horse_link:
            horse_name = horse_link.get("title") or horse_link.get_text(strip=True)
            horse_netkeiba_id = _extract_netkeiba_id(
                horse_link.get("href"), r"/horse/(\w+)"
            )

        if not horse_name:
            return None

        # Sex/Age - td[4]
        sex_age_text = tds[4].get_text(strip=True)
        sex, age = _parse_sex_age(sex_age_text)

        # Weight carried (斤量) - td[5]
        weight_text = tds[5].get_text(strip=True)
        weight_carried = None
        try:
            weight_carried = float(weight_text)
        except (ValueError, TypeError):
            pass

        # Jockey - td[6]
        jockey_td = tds[6]
        jockey_link = jockey_td.select_one("a")
        jockey_name = jockey_link.get_text(strip=True) if jockey_link else None

        # Trainer - td[7]
        trainer_td = tds[7]
        trainer_link = trainer_td.select_one("a")
        trainer_name = trainer_link.get_text(strip=True) if trainer_link else None
        # Trainer region (美浦/栗東)
        region_label = trainer_td.select_one("span.Label1, span.Label2")
        trainer_region = region_label.get_text(strip=True) if region_label else None

        # Horse weight - td[8]
        weight_td = tds[8]
        hw_text = weight_td.get_text(strip=True)
        horse_weight_kg, horse_weight_diff = _parse_weight_text(hw_text)

        return {
            "bracket_number": bracket_number,
            "post_position": post_position,
            "horse_name": horse_name,
            "horse_netkeiba_id": horse_netkeiba_id,
            "sex": sex,
            "age": age,
            "weight_carried_kg": weight_carried,
            "jockey_name": jockey_name,
            "trainer_name": trainer_name,
            "trainer_region": trainer_region,
            "horse_weight_kg": horse_weight_kg,
            "horse_weight_diff": horse_weight_diff,
        }
    except (IndexError, ValueError):
        return None
