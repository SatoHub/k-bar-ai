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

        # ヘッダ行（レース名＋勝敗アイコン）。
        # ⚠️ LINE Flex は text に空文字を許さない（400 Bad Request になる）。
        # 賭けの無いレース(status_icon="")はアイコンのtextコンポーネント自体を省く。
        header_row: list[dict] = [
            {
                "type": "text",
                "text": race_label or "-",
                "size": "sm",
                "weight": "bold",
                "flex": 5,
                "color": "#333333",
            },
        ]
        if status_icon:
            header_row.append(
                {
                    "type": "text",
                    "text": status_icon,
                    "size": "sm",
                    "weight": "bold",
                    "flex": 2,
                    "align": "end",
                    "color": color,
                }
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
                        "contents": header_row,
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
      - hit_rates: dict (optional, per bet_type hit rates)
    """
    roi = report.get("roi", 0)
    roi_color = "#1DB446" if roi >= 100 else "#DD4444"

    body_contents: list[dict] = [
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
    ]

    # Add per bet_type hit rates if available
    hit_rates = report.get("hit_rates", {})
    if hit_rates:
        body_contents.append({"type": "separator", "margin": "md"})
        body_contents.append(
            {
                "type": "text",
                "text": "馬券種別 的中率",
                "size": "sm",
                "weight": "bold",
                "margin": "md",
                "color": "#333333",
            }
        )
        label_map = {
            "tansho": "単勝",
            "fukusho": "複勝",
            "umaren": "馬連",
            "wide": "ワイド",
            "sanrenpuku": "3連複",
        }
        for key, label in label_map.items():
            hr = hit_rates.get(key)
            if hr and hr.get("total", 0) > 0:
                body_contents.append(
                    _kv_row(label, f"{hr['hits']}/{hr['total']} ({hr['rate']}%)")
                )

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
            "contents": body_contents,
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


def build_miss_summary_flex(misses: list[dict]) -> dict:
    """Build an informational Flex Message summarizing today's AI misses.

    Each item in *misses*:
      - race_name: str
      - ai_top3: list[str]
      - actual_top3: list[str]
      - auto_reason: str (auto-detected reason from DB data)
    """
    body_contents: list[dict] = [
        {
            "type": "text",
            "text": "本日のAIハズレまとめ",
            "weight": "bold",
            "size": "md",
            "color": "#333333",
        },
        {
            "type": "text",
            "text": f"{len(misses)}レースでAI本命が3着外",
            "size": "xs",
            "color": "#888888",
            "margin": "sm",
        },
        {"type": "separator", "margin": "md"},
    ]

    for miss in misses[:5]:
        race_name = miss.get("race_name", "")
        ai = miss.get("ai_top3", [])
        actual = miss.get("actual_top3", [])
        auto_reason = miss.get("auto_reason", "")

        race_box: list[dict] = [
            {
                "type": "text",
                "text": race_name,
                "size": "sm",
                "weight": "bold",
                "color": "#333333",
                "wrap": True,
            },
        ]

        if ai and actual:
            race_box.append(
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"AI: {' > '.join(ai[:3])}",
                            "size": "xs",
                            "color": "#DD4444",
                        },
                        {
                            "type": "text",
                            "text": f"実: {' > '.join(actual[:3])}",
                            "size": "xs",
                            "color": "#1DB446",
                        },
                    ],
                }
            )

        if auto_reason:
            race_box.append(
                {
                    "type": "text",
                    "text": auto_reason,
                    "size": "xxs",
                    "color": "#999999",
                    "margin": "sm",
                }
            )

        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "margin": "lg",
                "contents": race_box,
            }
        )

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#DD4444",
            "paddingAll": "12px",
            "contents": [
                {
                    "type": "text",
                    "text": "K-Bar AI",
                    "color": "#ffffff",
                    "size": "xs",
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


def build_monthly_proposal_flex(
    month_str: str,
    proposals: list[dict],
) -> dict:
    """Build a Flex Message for monthly improvement proposals.

    Each proposal: {id, proposal_type, description, priority}
    """
    body_contents: list[dict] = [
        {
            "type": "text",
            "text": f"{month_str} 改善提案",
            "weight": "bold",
            "size": "lg",
            "color": "#333333",
        },
        {"type": "separator", "margin": "md"},
    ]

    bubbles: list[dict] = []

    for i, proposal in enumerate(proposals[:5]):
        proposal_id = proposal.get("id", "")
        desc = proposal.get("description", "")

        proposal_body: list[dict] = [
            {
                "type": "text",
                "text": f"提案 {i + 1}",
                "weight": "bold",
                "size": "md",
                "color": "#333333",
            },
            {
                "type": "text",
                "text": desc,
                "size": "sm",
                "color": "#666666",
                "wrap": True,
                "margin": "md",
            },
        ]

        proposal_buttons: list[dict] = [
            {
                "type": "button",
                "style": "primary",
                "margin": "sm",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": "承認",
                    "data": f"action=proposal_response&proposal_id={proposal_id}&response=approved",
                },
            },
            {
                "type": "button",
                "style": "secondary",
                "margin": "sm",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": "保留",
                    "data": f"action=proposal_response&proposal_id={proposal_id}&response=deferred",
                },
            },
        ]

        bubbles.append(
            {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#FF8C00",
                    "paddingAll": "15px",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"K-Bar AI 改善提案",
                            "color": "#ffffff",
                            "size": "sm",
                            "weight": "bold",
                        },
                    ],
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": proposal_body,
                },
                "footer": {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": proposal_buttons,
                },
            }
        )

    # If only one proposal, return a single bubble
    if len(bubbles) == 1:
        return bubbles[0]

    # Multiple proposals: return a carousel
    return {
        "type": "carousel",
        "contents": bubbles,
    }


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
