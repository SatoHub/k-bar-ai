"""Parse netkeiba odds API response (JSON) to extract win odds and combo odds."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Accepted API status values:
#   "result" = confirmed odds (after race finalized)
#   "middle" = interim odds (during betting, before race start)
#   "yoso"   = forecast odds (day-before estimates, lower accuracy)
_ACCEPTED_STATUSES = {"result", "middle", "yoso"}

# Mapping from our bet_type to netkeiba API type param and response key
NETKEIBA_ODDS_TYPE_MAP: dict[str, dict] = {
    "tansho": {"api_type": 1, "odds_key": "1"},
    "fukusho": {"api_type": 1, "odds_key": "2"},
    "wakuren": {"api_type": 2, "odds_key": "3"},
    "umaren": {"api_type": 4, "odds_key": "4"},
    "wide": {"api_type": 5, "odds_key": "5"},
    "umatan": {"api_type": 6, "odds_key": "6"},
    "sanrenpuku": {"api_type": 7, "odds_key": "7"},
    "sanrentan": {"api_type": 8, "odds_key": "8"},
}


def parse_combo_odds(data: dict, bet_type: str, selections: list[int]) -> float | None:
    """Parse netkeiba odds API JSON and return odds for a specific combination.

    Args:
        data: Raw API JSON response.
        bet_type: One of tansho, fukusho, wakuren, umaren, umatan, wide, sanrenpuku, sanrentan.
        selections: List of horse numbers (post_position) or bracket numbers (for wakuren).
                    For ordered bets (umatan, sanrentan), order matters.

    Returns:
        The odds value as float, or None if not found.
    """
    status = data.get("status")
    if status not in _ACCEPTED_STATUSES:
        logger.debug("Combo odds: skipping status=%s", status)
        return None

    type_info = NETKEIBA_ODDS_TYPE_MAP.get(bet_type)
    if not type_info:
        return None

    odds_data = data.get("data", {}).get("odds", {})
    section = odds_data.get(type_info["odds_key"], {})

    if not section:
        return None

    # Single-horse bets (tansho, fukusho)
    if bet_type in ("tansho", "fukusho"):
        key = f"{selections[0]:02d}"
        values = section.get(key)
        if not isinstance(values, list) or not values:
            return None
        # fukusho may return range like "1.2-1.5"; take the midpoint
        odds_str = values[0]
        if odds_str and "-" in odds_str:
            parts = odds_str.split("-")
            lo = _safe_float(parts[0])
            hi = _safe_float(parts[1]) if len(parts) > 1 else lo
            if lo is not None and hi is not None:
                return round((lo + hi) / 2, 1)
            return lo
        return _safe_float(odds_str)

    # Combination bets - build the lookup key
    if bet_type in ("umatan", "sanrentan"):
        # Ordered: keep the order as given
        parts = [f"{s:02d}" for s in selections]
    else:
        # Unordered: sort ascending
        parts = [f"{s:02d}" for s in sorted(selections)]
    combo_key = "-".join(parts)

    values = section.get(combo_key)
    if not isinstance(values, list) or not values:
        return None
    return _safe_float(values[0])


def parse_odds_json(data: dict, race_id: str) -> list[dict]:
    """Parse odds API JSON response into a list of odds dicts.

    The API endpoint returns JSON like:
    {
        "status": "result" | "middle" | "yoso",
        "data": {
            "official_datetime": "2025-06-01 15:52:10",
            "odds": {
                "1": {  // 単勝
                    "01": ["76.9", "", "10"],  // [odds, _, popularity]
                    "13": ["2.1", "", "1"],
                },
                "2": { ... }  // 複勝
            }
        }
    }

    Returns:
        [
            {
                "race_id": "202505021211",
                "post_position": 1,
                "win_odds": 76.9,
                "win_favorite": 10,
            },
            ...
        ]
    """
    results: list[dict] = []

    status = data.get("status")
    if status not in _ACCEPTED_STATUSES:
        logger.warning("Odds API returned unexpected status=%s for %s", status, race_id)
        return results

    if status != "result":
        logger.info("Odds %s: using %s odds (not yet confirmed)", race_id, status)

    odds_data = data.get("data", {}).get("odds", {})
    win_odds = odds_data.get("1", {})  # Key "1" = 単勝

    for umaban_str, values in win_odds.items():
        if not isinstance(values, list) or len(values) < 3:
            continue

        try:
            post_position = int(umaban_str)
        except (ValueError, TypeError):
            continue

        odds_val = _safe_float(values[0])
        favorite = _safe_int(values[2])

        results.append(
            {
                "race_id": race_id,
                "post_position": post_position,
                "win_odds": odds_val,
                "win_favorite": favorite,
            }
        )

    # Sort by post position
    results.sort(key=lambda x: x["post_position"])
    return results


def _safe_float(val: str | None) -> float | None:
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
