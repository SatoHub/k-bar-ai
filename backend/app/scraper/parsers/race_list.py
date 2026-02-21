"""Parse netkeiba race list page (race_list_sub.html) to extract race IDs."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


def parse_race_list(html: str) -> list[dict]:
    """Parse race_list_sub.html and return list of race info dicts.

    Each dict: {"race_id": "202505010701", "race_number": 1,
                "race_name": "3歳未勝利", "course_info": "ダ1400m",
                "head_count": 16, "post_time": "10:10"}
    """
    soup = BeautifulSoup(html, "lxml")
    races: list[dict] = []

    for item in soup.select("li.RaceList_DataItem"):
        link = item.select_one("a[href*='race_id=']")
        if not link:
            continue

        href = link.get("href", "")
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        race_id = qs.get("race_id", [None])[0]
        if not race_id:
            continue

        # Race number
        num_el = item.select_one("div.Race_Num span")
        race_number = None
        if num_el:
            m = re.search(r"(\d+)", num_el.get_text(strip=True))
            if m:
                race_number = int(m.group(1))

        # Race name
        title_el = item.select_one("span.ItemTitle")
        race_name = title_el.get_text(strip=True) if title_el else None

        # Course info (e.g. "ダ1400m")
        course_el = item.select_one("span.RaceList_ItemLong")
        course_info = course_el.get_text(strip=True) if course_el else None

        # Head count (e.g. "16頭")
        count_el = item.select_one("span.RaceList_Itemnumber")
        head_count = None
        if count_el:
            m = re.search(r"(\d+)", count_el.get_text(strip=True))
            if m:
                head_count = int(m.group(1))

        # Post time
        time_el = item.select_one("span.RaceList_Itemtime")
        post_time = time_el.get_text(strip=True) if time_el else None

        races.append(
            {
                "race_id": race_id,
                "race_number": race_number,
                "race_name": race_name,
                "course_info": course_info,
                "head_count": head_count,
                "post_time": post_time,
            }
        )

    return races
