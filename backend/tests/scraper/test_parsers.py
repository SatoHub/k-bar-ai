"""Unit tests for netkeiba HTML parsers.

Tests use inline HTML fixtures mimicking netkeiba's structure.
These are pure-function tests — no Playwright or DB needed.
"""

from app.scraper.parsers.odds import parse_odds_json
from app.scraper.parsers.race_list import parse_race_list
from app.scraper.parsers.result import parse_result
from app.scraper.parsers.shutuba import parse_shutuba


# ---------------------------------------------------------------------------
# race_list parser
# ---------------------------------------------------------------------------

RACE_LIST_HTML = """
<html><body>
<dl class="RaceList_DataList">
  <dt class="RaceList_DataHeader">東京</dt>
  <dd class="RaceList_Data">
    <ul>
      <li class="RaceList_DataItem">
        <a href="../race/shutuba.html?race_id=202505020101&rf=race_list">
          <div class="Race_Num"><span>1R</span></div>
          <div class="RaceList_ItemContent">
            <div class="RaceList_ItemTitle">
              <span class="ItemTitle">3歳未勝利</span>
            </div>
            <div class="RaceData">
              <span class="RaceList_Itemtime">10:10 </span>
              <span class="RaceList_ItemLong Dart">ダ1400m</span>
              <span class="RaceList_Itemnumber">16頭 </span>
            </div>
          </div>
        </a>
      </li>
      <li class="RaceList_DataItem">
        <a href="../race/shutuba.html?race_id=202505020102&rf=race_list">
          <div class="Race_Num"><span>2R</span></div>
          <div class="RaceList_ItemContent">
            <div class="RaceList_ItemTitle">
              <span class="ItemTitle">3歳未勝利</span>
            </div>
            <div class="RaceData">
              <span class="RaceList_Itemtime">10:45 </span>
              <span class="RaceList_ItemLong">芝1800m</span>
              <span class="RaceList_Itemnumber">12頭 </span>
            </div>
          </div>
        </a>
      </li>
    </ul>
  </dd>
</dl>
</body></html>
"""


def test_parse_race_list():
    races = parse_race_list(RACE_LIST_HTML)
    assert len(races) == 2

    r1 = races[0]
    assert r1["race_id"] == "202505020101"
    assert r1["race_number"] == 1
    assert r1["race_name"] == "3歳未勝利"
    assert r1["course_info"] == "ダ1400m"
    assert r1["head_count"] == 16
    assert r1["post_time"] == "10:10"

    r2 = races[1]
    assert r2["race_id"] == "202505020102"
    assert r2["race_number"] == 2
    assert r2["head_count"] == 12


def test_parse_race_list_empty():
    races = parse_race_list("<html><body></body></html>")
    assert races == []


# ---------------------------------------------------------------------------
# shutuba parser
# ---------------------------------------------------------------------------

SHUTUBA_HTML = """
<html><body>
<div class="RaceName">東京11R 日本ダービー</div>
<div class="RaceData01">
  芝2400m (左) / 天候：晴 / 芝：良
</div>
<div class="RaceData02">
  <span>3回東京8日目</span>
</div>
<div class="RaceTableArea">
<table class="Shutuba_Table RaceTable01 ShutubaTable">
  <thead><tr><th>枠</th><th>馬番</th><th>印</th><th>馬名</th><th>性齢</th><th>斤量</th><th>騎手</th><th>厩舎</th><th>馬体重</th></tr></thead>
  <tbody>
    <tr class="HorseList">
      <td class="Waku1">1</td>
      <td class="Umaban1">1</td>
      <td></td>
      <td class="HorseInfo"><a href="https://db.netkeiba.com/horse/2022104922" title="テスト馬">テスト馬</a></td>
      <td class="Barei">牡3</td>
      <td class="Txt_C">57.0</td>
      <td class="Jockey"><a href="/jockey/01115/">ルメール</a></td>
      <td class="Trainer"><span class="Label1">美浦</span><a href="/trainer/01234/">友道</a></td>
      <td class="Weight">480(+4)</td>
    </tr>
    <tr class="HorseList">
      <td class="Waku2">2</td>
      <td class="Umaban2">3</td>
      <td></td>
      <td class="HorseInfo"><a href="https://db.netkeiba.com/horse/2022105000" title="テスト馬2">テスト馬2</a></td>
      <td class="Barei">牝3</td>
      <td class="Txt_C">55.0</td>
      <td class="Jockey"><a href="/jockey/01200/">武豊</a></td>
      <td class="Trainer"><span class="Label2">栗東</span><a href="/trainer/02000/">矢作</a></td>
      <td class="Weight">460(-2)</td>
    </tr>
  </tbody>
</table>
</div>
</body></html>
"""


def test_parse_shutuba():
    result = parse_shutuba(SHUTUBA_HTML, "202505021211")
    assert result["race_id"] == "202505021211"
    assert result["race_name"] == "東京11R 日本ダービー"

    info = result["race_info"]
    assert info["surface"] == "芝"
    assert info["distance_m"] == 2400
    assert info["direction"] == "左"
    assert info["racecourse_name"] == "東京"

    entries = result["entries"]
    assert len(entries) == 2

    e1 = entries[0]
    assert e1["bracket_number"] == 1
    assert e1["post_position"] == 1
    assert e1["horse_name"] == "テスト馬"
    assert e1["horse_netkeiba_id"] == "2022104922"
    assert e1["sex"] == "牡"
    assert e1["age"] == 3
    assert e1["weight_carried_kg"] == 57.0
    assert e1["jockey_name"] == "ルメール"
    assert e1["trainer_name"] == "友道"
    assert e1["trainer_region"] == "美浦"
    assert e1["horse_weight_kg"] == 480
    assert e1["horse_weight_diff"] == 4

    e2 = entries[1]
    assert e2["post_position"] == 3
    assert e2["sex"] == "牝"
    assert e2["horse_weight_diff"] == -2
    assert e2["trainer_region"] == "栗東"


def test_parse_shutuba_empty_table():
    html = "<html><body><div class='RaceName'>Test</div></body></html>"
    result = parse_shutuba(html, "test")
    assert result["entries"] == []


# ---------------------------------------------------------------------------
# odds parser
# ---------------------------------------------------------------------------


def test_parse_odds_json():
    api_response = {
        "status": "result",
        "data": {
            "official_datetime": "2025-06-01 15:52:10",
            "odds": {
                "1": {
                    "01": ["76.9", "", "10"],
                    "02": ["2.1", "", "1"],
                    "13": ["5.5", "", "3"],
                },
                "2": {
                    "01": ["11.6", "22.1", "15"],
                },
            },
        },
    }

    odds = parse_odds_json(api_response, "202505021211")
    assert len(odds) == 3

    # Sorted by post_position
    assert odds[0]["post_position"] == 1
    assert odds[0]["win_odds"] == 76.9
    assert odds[0]["win_favorite"] == 10

    assert odds[1]["post_position"] == 2
    assert odds[1]["win_odds"] == 2.1
    assert odds[1]["win_favorite"] == 1

    assert odds[2]["post_position"] == 13
    assert odds[2]["win_odds"] == 5.5
    assert odds[2]["win_favorite"] == 3


def test_parse_odds_json_empty():
    assert parse_odds_json({"status": "error"}, "test") == []
    assert parse_odds_json({}, "test") == []


# ---------------------------------------------------------------------------
# result parser
# ---------------------------------------------------------------------------

RESULT_HTML = """
<html><body>
<div class="RaceName">東京11R 日本ダービー</div>
<div class="RaceData01">
  芝2400m (左) / 天候：晴 / 芝：良
</div>
<div class="RaceData02">
  <span>3回東京8日目</span>
</div>
<div class="ResultTableWrap">
<table id="All_Result_Table" class="RaceTable01 RaceCommon_Table">
  <thead><tr>
    <th>着順</th><th>枠</th><th>馬番</th><th>馬名</th><th>性齢</th>
    <th>斤量</th><th>騎手</th><th>タイム</th><th>着差</th>
    <th>人気</th><th>単勝</th><th>後3F</th><th>通過</th>
    <th>厩舎</th><th>馬体重</th>
  </tr></thead>
  <tbody>
    <tr class="HorseList FirstDisplay">
      <td class="Result_Num"><div class="Rank">1</div></td>
      <td class="Num Waku5">5</td>
      <td class="Num Txt_C">10</td>
      <td class="Horse_Info"><a href="/horse/2022104922"><span>テスト馬</span></a></td>
      <td>牡3</td>
      <td>57.0</td>
      <td class="Jockey"><a href="/jockey/01115/">ルメール</a></td>
      <td class="Time"><span class="RaceTime">2:23.4</span></td>
      <td class="Time"></td>
      <td class="Odds Txt_C"><span class="OddsPeople">1</span></td>
      <td class="Odds Txt_R"><span>2.1</span></td>
      <td class="Time">33.8</td>
      <td class="PassageRate">5-5-3-2</td>
      <td class="Trainer"><a href="/trainer/01234/"><span class="TrainerNameSpan">友道</span></a></td>
      <td class="Weight">480(+4)</td>
    </tr>
    <tr class="HorseList">
      <td class="Result_Num"><div class="Rank">2</div></td>
      <td class="Num Waku3">3</td>
      <td class="Num Txt_C">5</td>
      <td class="Horse_Info"><a href="/horse/2022105000"><span>テスト馬2</span></a></td>
      <td>牝3</td>
      <td>55.0</td>
      <td class="Jockey"><a href="/jockey/01200/">武豊</a></td>
      <td class="Time"><span class="RaceTime">2:23.6</span></td>
      <td class="Time">1 1/4</td>
      <td class="Odds Txt_C"><span class="OddsPeople">3</span></td>
      <td class="Odds Txt_R"><span>5.5</span></td>
      <td class="Time">34.0</td>
      <td class="PassageRate">3-3-4-4</td>
      <td class="Trainer"><a href="/trainer/02000/"><span class="TrainerNameSpan">矢作</span></a></td>
      <td class="Weight">460(-2)</td>
    </tr>
  </tbody>
</table>
</div>
</body></html>
"""


def test_parse_result():
    result = parse_result(RESULT_HTML, "202505021211")
    assert result["race_id"] == "202505021211"
    assert result["race_name"] == "東京11R 日本ダービー"

    info = result["race_info"]
    assert info["surface"] == "芝"
    assert info["distance_m"] == 2400

    entries = result["entries"]
    assert len(entries) == 2

    e1 = entries[0]
    assert e1["finish_position"] == 1
    assert e1["bracket_number"] == 5
    assert e1["post_position"] == 10
    assert e1["horse_name"] == "テスト馬"
    assert e1["horse_netkeiba_id"] == "2022104922"
    assert e1["sex"] == "牡"
    assert e1["age"] == 3
    assert e1["weight_carried_kg"] == 57.0
    assert e1["jockey_name"] == "ルメール"
    assert e1["total_time_tenths"] == 1434  # 2:23.4 = 2*600 + 23*10 + 4
    assert e1["win_favorite"] == 1
    assert e1["win_odds"] == 2.1
    assert e1["last_3f_time"] == 33.8
    assert e1["corner_pos_1"] == "5"
    assert e1["corner_pos_2"] == "5"
    assert e1["corner_pos_3"] == "3"
    assert e1["corner_pos_4"] == "2"
    assert e1["trainer_name"] == "友道"
    assert e1["horse_weight_kg"] == 480
    assert e1["horse_weight_diff"] == 4

    e2 = entries[1]
    assert e2["finish_position"] == 2
    assert e2["post_position"] == 5
    assert e2["margin"] == "1 1/4"


def test_parse_result_empty():
    html = "<html><body></body></html>"
    result = parse_result(html, "test")
    assert result["entries"] == []
