"""LINE Flex Message templates for K-Bar AI notifications.

All builders return a dict that can be passed to FlexContainer.from_dict().
"""

from __future__ import annotations


def build_prediction_flex(predictions: list[dict]) -> dict:
    """Build a Flex Message for tomorrow's AI prediction summary.

    Each item in *predictions* should have:
      - race_name: str
      - racecourse_name: str
      - race_number: int
      - top_horses: list[dict]  (name, score, odds)
    """
    body_contents: list[dict] = [
        {
            "type": "text",
            "text": "明日のAI予想",
            "weight": "bold",
            "size": "xl",
            "color": "#1a1a1a",
        },
        {"type": "separator", "margin": "md"},
    ]

    for pred in predictions[:5]:  # 最大5レース
        race_label = f"{pred.get('racecourse_name', '')} {pred.get('race_number', '')}R"
        race_name = pred.get("race_name", "")

        race_section: list[dict] = [
            {
                "type": "text",
                "text": f"{race_label} {race_name}",
                "weight": "bold",
                "size": "md",
                "margin": "lg",
                "color": "#333333",
            },
        ]

        for i, horse in enumerate(pred.get("top_horses", [])[:3], 1):
            mark = ["", ""][0] if i == 1 else ""
            score = horse.get("score", 0)
            odds = horse.get("odds", "-")
            race_section.append(
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{mark}{i}. {horse.get('name', '?')}",
                            "size": "sm",
                            "flex": 4,
                            "color": "#555555",
                        },
                        {
                            "type": "text",
                            "text": f"{score:.0f}pt",
                            "size": "sm",
                            "flex": 2,
                            "align": "end",
                            "color": "#111111",
                        },
                        {
                            "type": "text",
                            "text": f"{odds}倍",
                            "size": "sm",
                            "flex": 2,
                            "align": "end",
                            "color": "#888888",
                        },
                    ],
                }
            )

        body_contents.extend(race_section)

    if len(predictions) > 5:
        body_contents.append(
            {
                "type": "text",
                "text": f"... 他 {len(predictions) - 5} レース",
                "size": "xs",
                "color": "#aaaaaa",
                "margin": "md",
            }
        )

    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1DB446",
            "paddingAll": "15px",
            "contents": [
                {
                    "type": "text",
                    "text": "K-Bar AI",
                    "color": "#ffffff",
                    "size": "sm",
                    "weight": "bold",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
        },
    }


def build_results_flex(results: list[dict]) -> dict:
    """Build a Flex Message for today's race results summary.

    Each item in *results* should have:
      - race_name: str
      - racecourse_name: str
      - race_number: int
      - bet_result: str ("win" / "lose" / "none")
      - return_rate: float | None
      - top3: list[dict]  (position, name)
    """
    body_contents: list[dict] = [
        {
            "type": "text",
            "text": "本日のレース結果",
            "weight": "bold",
            "size": "xl",
            "color": "#1a1a1a",
        },
        {"type": "separator", "margin": "md"},
    ]

    wins = 0
    total_bets = 0

    for res in results[:8]:
        race_label = f"{res.get('racecourse_name', '')} {res.get('race_number', '')}R"
        bet = res.get("bet_result", "none")

        if bet == "win":
            status_icon = "[WIN]"
            color = "#1DB446"
            wins += 1
            total_bets += 1
        elif bet == "lose":
            status_icon = "[LOSE]"
            color = "#DD4444"
            total_bets += 1
        else:
            status_icon = ""
            color = "#888888"

        top3_text = " > ".join(
            h.get("name", "?") for h in res.get("top3", [])[:3]
        )

        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "margin": "lg",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": race_label,
                                "size": "sm",
                                "weight": "bold",
                                "flex": 5,
                                "color": "#333333",
                            },
                            {
                                "type": "text",
                                "text": status_icon,
                                "size": "sm",
                                "weight": "bold",
                                "flex": 2,
                                "align": "end",
                                "color": color,
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": top3_text or "-",
                        "size": "xs",
                        "color": "#888888",
                        "wrap": True,
                    },
                ],
            }
        )

    # Summary footer
    if total_bets > 0:
        body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.append(
            {
                "type": "text",
                "text": f"的中: {wins}/{total_bets}",
                "size": "md",
                "weight": "bold",
                "margin": "md",
                "color": "#1DB446" if wins > 0 else "#DD4444",
            }
        )

    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0367D3",
            "paddingAll": "15px",
            "contents": [
                {
                    "type": "text",
                    "text": "K-Bar AI",
                    "color": "#ffffff",
                    "size": "sm",
                    "weight": "bold",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
        },
    }


def build_weekly_report_flex(report: dict) -> dict:
    """Build a Flex Message for weekly performance report.

    *report* should have:
      - period: str (e.g. "2/14 - 2/21")
      - total_bets: int
      - wins: int
      - total_invested: int
      - total_returned: int
      - roi: float (percent)
    """
    roi = report.get("roi", 0)
    roi_color = "#1DB446" if roi >= 100 else "#DD4444"

    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#7B61FF",
            "paddingAll": "15px",
            "contents": [
                {
                    "type": "text",
                    "text": "K-Bar AI 週次レポート",
                    "color": "#ffffff",
                    "size": "sm",
                    "weight": "bold",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": report.get("period", ""),
                    "size": "xs",
                    "color": "#888888",
                },
                {"type": "separator", "margin": "md"},
                _kv_row("総ベット数", str(report.get("total_bets", 0))),
                _kv_row("的中数", str(report.get("wins", 0))),
                _kv_row("投資額", f"{report.get('total_invested', 0):,}円"),
                _kv_row("回収額", f"{report.get('total_returned', 0):,}円"),
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": "回収率",
                            "size": "md",
                            "weight": "bold",
                            "flex": 3,
                            "color": "#333333",
                        },
                        {
                            "type": "text",
                            "text": f"{roi:.1f}%",
                            "size": "xl",
                            "weight": "bold",
                            "flex": 3,
                            "align": "end",
                            "color": roi_color,
                        },
                    ],
                },
            ],
        },
    }


def build_interactive_flex(
    title: str,
    body_text: str,
    actions: list[dict] | None = None,
) -> dict:
    """Build a generic Flex Message with action buttons.

    *actions* should be a list of dicts with keys: label, data (for postback).
    This serves as a foundation for Step 5/6 interactive features.
    """
    button_contents: list[dict] = []
    for action in (actions or []):
        button_contents.append(
            {
                "type": "button",
                "style": "primary",
                "margin": "sm",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": action.get("label", ""),
                    "data": action.get("data", ""),
                },
            }
        )

    bubble: dict = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "lg",
                    "color": "#333333",
                },
                {
                    "type": "text",
                    "text": body_text,
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
    }

    if button_contents:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": button_contents,
        }

    return bubble


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _kv_row(label: str, value: str) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "margin": "md",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "sm",
                "flex": 3,
                "color": "#555555",
            },
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "flex": 3,
                "align": "end",
                "color": "#111111",
            },
        ],
    }
