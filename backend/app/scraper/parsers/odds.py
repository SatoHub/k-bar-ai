"""Parse netkeiba odds API response (JSON) to extract win odds."""

from __future__ import annotations


def parse_odds_json(data: dict, race_id: str) -> list[dict]:
    """Parse odds API JSON response into a list of odds dicts.

    The API endpoint returns JSON like:
    {
        "status": "result",
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

    if data.get("status") != "result":
        return results

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
