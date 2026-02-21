"""Parse netkeiba race result page to extract finish positions and times."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def _parse_time_to_tenths(time_str: str) -> int | None:
    """Convert race time string '1:23.4' to tenths of seconds (834)."""
    if not time_str:
        return None
    m = re.match(r"(\d+):(\d+)\.(\d)", time_str.strip())
    if m:
        minutes = int(m.group(1))
        seconds = int(m.group(2))
        tenths = int(m.group(3))
        return minutes * 600 + seconds * 10 + tenths
    return None


def _parse_weight_text(text: str) -> tuple[int | None, int | None]:
    """Parse '480(+4)' into (weight, diff)."""
    m = re.match(r"(\d+)\(([+-]?\d+)\)", text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r"(\d+)", text.strip())
    if m2:
        return int(m2.group(1)), None
    return None, None


def parse_result(html: str, race_id: str) -> dict:
    """Parse race result page.

    Returns:
        {
            "race_id": "202505021211",
            "race_name": "...",
            "race_info": {"surface": "芝", "distance_m": 2400, ...},
            "entries": [
                {
                    "finish_position": 1,
                    "bracket_number": 5,
                    "post_position": 10,
                    "horse_name": "...",
                    "horse_netkeiba_id": "2022104922",
                    "sex": "牡",
                    "age": 3,
                    "weight_carried_kg": 57.0,
                    "jockey_name": "...",
                    "total_time_tenths": 1434,
                    "margin": "クビ",
                    "win_favorite": 1,
                    "win_odds": 2.1,
                    "last_3f_time": 33.8,
                    "corner_positions": "5-5-3-2",
                    "trainer_name": "...",
                    "horse_weight_kg": 480,
                    "horse_weight_diff": 4,
                },
                ...
            ]
        }
    """
    soup = BeautifulSoup(html, "lxml")
    result_data: dict = {"race_id": race_id, "entries": []}

    # Race name
    name_el = soup.select_one("div.RaceName")
    result_data["race_name"] = name_el.get_text(strip=True) if name_el else None

    # Race info
    result_data["race_info"] = _parse_race_info(soup)

    # Result table
    table = soup.select_one("table#All_Result_Table")
    if not table:
        return result_data

    for row in table.select("tr.HorseList"):
        entry = _parse_result_row(row)
        if entry:
            result_data["entries"].append(entry)

    return result_data


def _parse_race_info(soup: BeautifulSoup) -> dict:
    """Extract race metadata from result page."""
    info: dict = {}

    data01 = soup.select_one("div.RaceData01")
    if data01:
        text = data01.get_text(strip=True)
        m = re.search(r"(芝|ダ|障)(\d+)m", text)
        if m:
            surface_map = {"芝": "芝", "ダ": "ダート", "障": "障害"}
            info["surface"] = surface_map.get(m.group(1), m.group(1))
            info["distance_m"] = int(m.group(2))

        m_dir = re.search(r"(右|左|直線)", text)
        if m_dir:
            info["direction"] = m_dir.group(1)

        m_weather = re.search(r"天候\s*[:：]\s*(\S+)", text)
        if m_weather:
            info["weather"] = m_weather.group(1)

        m_cond = re.search(r"(芝|ダート)\s*[:：]\s*(\S+)", text)
        if m_cond:
            info["track_condition"] = m_cond.group(2)

    data02 = soup.select_one("div.RaceData02")
    if data02:
        for span in data02.select("span"):
            text = span.get_text(strip=True)
            m_course = re.match(r"(\d+)回(\S+?)(\d+)日目", text)
            if m_course:
                info["racecourse_name"] = m_course.group(2)

    return info


def _parse_result_row(row) -> dict | None:
    """Parse a single result row."""
    try:
        tds = row.find_all("td")
        if len(tds) < 15:
            return None

        # Finish position - td[0]
        rank_el = tds[0].select_one("div.Rank")
        finish_text = (
            rank_el.get_text(strip=True) if rank_el else tds[0].get_text(strip=True)
        )
        finish_position = None
        finish_note = None
        try:
            finish_position = int(finish_text)
        except (ValueError, TypeError):
            finish_note = finish_text  # e.g. "中止", "除外"

        # Bracket number - td[1]
        bracket_text = tds[1].get_text(strip=True)
        bracket_number = int(bracket_text) if bracket_text.isdigit() else None

        # Post position - td[2]
        post_text = tds[2].get_text(strip=True)
        post_position = int(post_text) if post_text.isdigit() else None

        # Horse info - td[3]
        horse_td = tds[3]
        horse_link = horse_td.select_one("a[href*='/horse/']")
        horse_name = None
        horse_netkeiba_id = None
        if horse_link:
            name_span = horse_link.select_one("span")
            horse_name = (
                name_span.get_text(strip=True)
                if name_span
                else horse_link.get_text(strip=True)
            )
            href = horse_link.get("href", "")
            m = re.search(r"/horse/(\w+)", href)
            if m:
                horse_netkeiba_id = m.group(1)

        if not horse_name:
            return None

        # Sex/Age - td[4]
        sex_age = tds[4].get_text(strip=True)
        sex, age = None, None
        m_sa = re.match(r"([牡牝セ騸])(\d+)", sex_age)
        if m_sa:
            sex = m_sa.group(1)
            age = int(m_sa.group(2))

        # Weight carried - td[5]
        wc_text = tds[5].get_text(strip=True)
        weight_carried = None
        try:
            weight_carried = float(wc_text)
        except (ValueError, TypeError):
            pass

        # Jockey - td[6]
        jockey_link = tds[6].select_one("a")
        jockey_name = jockey_link.get_text(strip=True) if jockey_link else None

        # Time - td[7]
        time_text = tds[7].get_text(strip=True)
        total_time_tenths = _parse_time_to_tenths(time_text)

        # Margin - td[8]
        margin = tds[8].get_text(strip=True) or None

        # Popularity - td[9]
        pop_text = tds[9].get_text(strip=True)
        win_favorite = None
        try:
            win_favorite = int(pop_text)
        except (ValueError, TypeError):
            pass

        # Win odds - td[10]
        odds_text = tds[10].get_text(strip=True)
        win_odds = None
        try:
            win_odds = float(odds_text)
        except (ValueError, TypeError):
            pass

        # Last 3F - td[11]
        l3f_text = tds[11].get_text(strip=True)
        last_3f_time = None
        try:
            last_3f_time = float(l3f_text)
        except (ValueError, TypeError):
            pass

        # Corner positions - td[12]
        corner_text = tds[12].get_text(strip=True)

        # Trainer - td[13]
        trainer_link = tds[13].select_one("a")
        trainer_name = trainer_link.get_text(strip=True) if trainer_link else None

        # Horse weight - td[14]
        hw_text = tds[14].get_text(strip=True)
        horse_weight_kg, horse_weight_diff = _parse_weight_text(hw_text)

        # Parse corner positions "5-5-3-2" into separate values
        corners = _parse_corners(corner_text)

        return {
            "finish_position": finish_position,
            "finish_note": finish_note,
            "bracket_number": bracket_number,
            "post_position": post_position,
            "horse_name": horse_name,
            "horse_netkeiba_id": horse_netkeiba_id,
            "sex": sex,
            "age": age,
            "weight_carried_kg": weight_carried,
            "jockey_name": jockey_name,
            "total_time_tenths": total_time_tenths,
            "margin": margin,
            "win_favorite": win_favorite,
            "win_odds": win_odds,
            "last_3f_time": last_3f_time,
            "corner_pos_1": corners.get(1),
            "corner_pos_2": corners.get(2),
            "corner_pos_3": corners.get(3),
            "corner_pos_4": corners.get(4),
            "trainer_name": trainer_name,
            "horse_weight_kg": horse_weight_kg,
            "horse_weight_diff": horse_weight_diff,
        }
    except (IndexError, ValueError):
        return None


def _parse_corners(text: str) -> dict[int, str]:
    """Parse '5-5-3-2' corner passage into {1: '5', 2: '5', 3: '3', 4: '2'}."""
    if not text:
        return {}
    parts = text.split("-")
    result: dict[int, str] = {}
    for i, p in enumerate(parts[:4], start=1):
        p = p.strip()
        if p:
            result[i] = p
    return result
