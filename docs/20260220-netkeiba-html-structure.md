# netkeiba.com HTMLパース構造リファレンス

**調査日:** 2026-02-20
**調査対象:** 実際のHTMLをPython urllib で取得・検証済み

---

## 1. レース一覧ページ (race_list_sub)

### URL
```
https://race.netkeiba.com/top/race_list_sub.html?kaisai_date=YYYYMMDD
```

> **重要:** `race_list.html` は AJAX でコンテンツを動的ロードするため直接パースできない。
> `race_list_sub.html` が実データを含む静的HTMLフラグメント。

### 全体構造
```html
<div class="RaceList_Body RaceList_Top" id="RaceTopRace">
  <div class="RaceList_Box clearfix">
    <dl class="RaceList_DataList">
      <dt class="RaceList_DataHeader">
        <!-- 開催場名 -->
      </dt>
      <dd class="RaceList_Data">
        <ul>
          <li class="RaceList_DataItem">...</li>
          <li class="RaceList_DataItem">...</li>
        </ul>
      </dd>
    </dl>
  </div>
</div>
```

### 各レースアイテム構造
```html
<li class="RaceList_DataItem">
  <a href="../race/result.html?race_id=202505010701&rf=race_list" class="">
    <div class="Race_Num Race_Fixed">
      <span>
        <span class="MyRace_List_Item" id="myrace_202505010701" style="display: none;"></span>
        1R
      </span>
    </div>
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
```

### BeautifulSoup パース方法
```python
from bs4 import BeautifulSoup
import re

def parse_race_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    races = []
    for li in soup.select("li.RaceList_DataItem"):
        a = li.find("a", href=re.compile(r"race_id="))
        if not a:
            continue
        href = a["href"]
        race_id = re.search(r"race_id=(\d+)", href).group(1)
        race_num_span = a.select_one(".Race_Num span")
        race_num = race_num_span.get_text(strip=True).replace("R", "").strip() if race_num_span else ""
        title = a.select_one(".ItemTitle")
        time_span = a.select_one(".RaceList_Itemtime")
        distance_span = a.select_one(".RaceList_ItemLong")
        horses_span = a.select_one(".RaceList_Itemnumber")
        races.append({
            "race_id": race_id,
            "race_num": race_num,
            "title": title.get_text(strip=True) if title else "",
            "start_time": time_span.get_text(strip=True) if time_span else "",
            "distance": distance_span.get_text(strip=True) if distance_span else "",
            "num_horses": horses_span.get_text(strip=True) if horses_span else "",
        })
    return races
```

### Race ID フォーマット
- パターン: `YYYYVVCCRRNN` (12桁)
  - YYYY = 年
  - VV = 会場コード (01=札幌, 02=函館, 03=福島, 04=新潟, 05=東京, 06=中山, 07=中京, 08=京都, 09=阪神, 10=小倉)
  - CC = 開催回次
  - RR = 開催日次
  - NN = レース番号
- 例: `202505010701` → 2025年 東京(05) 1回 7日 1R

---

## 2. 出馬表ページ (shutuba)

### URL
```
https://race.netkeiba.com/race/shutuba.html?race_id=XXXXXXXXXXXX
```

### テーブル構造
```html
<div class="RaceTableArea">
  <table class="Shutuba_Table RaceTable01 ShutubaTable">
    <thead>
      <tr class="Header">
        <th rowspan="2" class="Waku">枠</th>
        <th rowspan="2" class="Umaban sort_common">馬番</th>
        <th rowspan="2" class="CheckMark">印</th>
        <th rowspan="2" class="HorseInfo sort_common" id="sort_cell_name">馬名</th>
        <th rowspan="2" class="Barei">性齢</th>
        <th rowspan="2" class="Dredging sort_common">斤量</th>
        <th rowspan="2" class="Jockey">騎手</th>
        <th rowspan="2" class="Trainer">厩舎</th>
        <th rowspan="2" class="Weight sort_common" id="sort_cell_weight">馬体重(増減)</th>
        <th rowspan="2" class="Popular" id="sort_cell_odds">単勝オッズ</th>
        <th rowspan="2" class="Popular Popular_Ninki Txt_C" id="sort_cell_ninki">人気</th>
        <th colspan="2" class="FavHorse">お気に入り馬</th>
        <th rowspan="2" class="Memo Note0">馬メモ</th>
      </tr>
      <tr class="Header FavHorseSub">
        <th class="FavRegist">登録</th>
        <th class="FavGroup">グループ</th>
      </tr>
    </thead>
    <tbody>
      <tr class="HorseList" id="tr_11">
        <!-- 各馬の行 -->
      </tr>
    </tbody>
  </table>
</div>
```

### tbody 各行の構造
```html
<tr class="HorseList" id="tr_11">
  <!-- 枠番: class="Waku{N} Txt_C" -->
  <td class="Waku1 Txt_C"><span>1</span></td>
  <!-- 馬番: class="Umaban{N} Txt_C" -->
  <td class="Umaban1 Txt_C">1</td>
  <!-- 印 (チェックマーク) -->
  <td class="CheckMark Horse_Select">...</td>
  <!-- 馬名 + 馬ID -->
  <td class="HorseInfo">
    <span class="HorseName">
      <a href="https://db.netkeiba.com/horse/2022104922" target="_blank" title="リラエンブレム">
        リラエンブレム
      </a>
    </span>
  </td>
  <!-- 性齢 -->
  <td class="Barei Txt_C">牡3</td>
  <!-- 斤量 -->
  <td class="Txt_C">57.0</td>
  <!-- 騎手 + 騎手ID -->
  <td class="Jockey">
    <a href="https://db.netkeiba.com/jockey/result/recent/01115/" target="_blank" title="浜中">
      浜中
    </a>
  </td>
  <!-- 調教師 + 所属(美浦/栗東) + 調教師ID -->
  <td class="Trainer">
    <span class="Label2">栗東</span>
    <a href="https://db.netkeiba.com/trainer/result/recent/01160/" target="_blank" title="武幸">
      武幸
    </a>
  </td>
  <!-- 馬体重(増減) -->
  <td class="Weight">484<small>(+4)</small></td>
  <!-- 単勝オッズ (JS動的更新) -->
  <td class="Txt_R Popular"><span id="odds-1_01" style="font-weight: bold">---.-</span></td>
  <!-- 人気 (JS動的更新) -->
  <td class="Popular Popular_Ninki Txt_C"><span id="ninki-1_01">**</span></td>
</tr>
```

### BeautifulSoup パース方法
```python
import re
from bs4 import BeautifulSoup

def parse_shutuba(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.Shutuba_Table")
    if not table:
        return []
    entries = []
    for tr in table.select("tr.HorseList"):
        # 枠番
        waku_td = tr.find("td", class_=re.compile(r"^Waku\d"))
        waku = waku_td.get_text(strip=True) if waku_td else ""
        # 馬番
        umaban_td = tr.find("td", class_=re.compile(r"^Umaban\d"))
        umaban = umaban_td.get_text(strip=True) if umaban_td else ""
        # 馬名 + 馬ID
        horse_td = tr.select_one("td.HorseInfo")
        horse_a = horse_td.select_one("a") if horse_td else None
        horse_name = horse_a["title"] if horse_a and horse_a.get("title") else ""
        horse_id = re.search(r"/horse/(\d+)", horse_a["href"]).group(1) if horse_a else ""
        # 性齢
        barei_td = tr.select_one("td.Barei")
        sex_age = barei_td.get_text(strip=True) if barei_td else ""
        # 斤量 (class="Txt_C" 6番目のtd)
        tds = tr.find_all("td")
        kinryo = tds[5].get_text(strip=True) if len(tds) > 5 else ""
        # 騎手 + 騎手ID
        jockey_td = tr.select_one("td.Jockey")
        jockey_a = jockey_td.select_one("a") if jockey_td else None
        jockey_name = jockey_a.get_text(strip=True) if jockey_a else ""
        jockey_id_m = re.search(r"/jockey/result/recent/(\d+)/", jockey_a["href"]) if jockey_a else None
        jockey_id = jockey_id_m.group(1) if jockey_id_m else ""
        # 調教師 + 所属 + 調教師ID
        trainer_td = tr.select_one("td.Trainer")
        trainer_label = trainer_td.select_one("span.Label1, span.Label2") if trainer_td else None
        affiliation = trainer_label.get_text(strip=True) if trainer_label else ""  # 美浦/栗東
        trainer_a = trainer_td.select_one("a") if trainer_td else None
        trainer_name = trainer_a.get_text(strip=True) if trainer_a else ""
        trainer_id_m = re.search(r"/trainer/result/recent/(\d+)/", trainer_a["href"]) if trainer_a else None
        trainer_id = trainer_id_m.group(1) if trainer_id_m else ""
        # 馬体重
        weight_td = tr.select_one("td.Weight")
        weight_text = weight_td.get_text(strip=True) if weight_td else ""
        # 例: "484(+4)" → weight=484, weight_diff=+4
        w_match = re.match(r"(\d+)\(([+-]?\d+)\)", weight_text.replace(" ", ""))
        body_weight = int(w_match.group(1)) if w_match else None
        weight_diff = int(w_match.group(2)) if w_match else None

        entries.append({
            "waku": int(waku) if waku.isdigit() else None,
            "umaban": int(umaban) if umaban.isdigit() else None,
            "horse_name": horse_name,
            "horse_id": horse_id,
            "sex_age": sex_age,
            "kinryo": float(kinryo) if kinryo else None,
            "jockey_name": jockey_name,
            "jockey_id": jockey_id,
            "trainer_name": trainer_name,
            "trainer_id": trainer_id,
            "affiliation": affiliation,
            "body_weight": body_weight,
            "weight_diff": weight_diff,
        })
    return entries
```

### 注意点
- オッズ・人気は JS が動的更新するため、HTML取得時点では `---.-` / `**`
- 実際のオッズは別途 Odds API から取得（後述）
- 除外馬は `tr.HorseList` に含まれず、別クラスで表示される可能性あり
- `id="tr_{horse_number}"` の horse_number は馬番ではなく内部ID

---

## 3. オッズページ (odds)

### URL
```
https://race.netkeiba.com/odds/index.html?race_id=XXXXXXXXXXXX&type=b1
```
- `type=b1`: 単勝・複勝
- `type=b3`: 馬連
- `type=b4`: 馬単
- etc.

### HTMLテーブル構造（単勝・複勝）
```html
<table class="RaceOdds_HorseList_Table">
  <tbody>
    <tr>
      <th>枠</th>
      <th class="Waku">馬番</th>
      <th class="Mark">印</th>
      <th>選択</th>
      <th>馬名</th>
      <th>オッズ</th>
    </tr>
    <tr>
      <td class="Waku1 W31">1</td>          <!-- 枠番 -->
      <td class="W31">1</td>                 <!-- 馬番 -->
      <td class="Mark_User">...</td>
      <td class="Horse_Select">...</td>
      <td class="Horse_Name">リラエンブレム</td>  <!-- 馬名 -->
      <td class="Odds Popular">
        <span class="Odds" id="odds-1_01">---.-</span>  <!-- 単勝オッズ (JS更新) -->
      </td>
    </tr>
  </tbody>
</table>
```

### オッズ動的更新API (推奨: こちらを使う)
```
GET https://race.netkeiba.com/api/api_get_jra_odds.html
    ?race_id=XXXXXXXXXXXX&type=1&action=update
```

**レスポンス (JSON):**
```json
{
  "status": "result",
  "data": {
    "official_datetime": "2025-06-01 15:52:10",
    "odds": {
      "1": {
        "01": ["76.9", "", "10"],   // 馬番01: [単勝オッズ, ?, 人気順]
        "02": ["14.4", "", "6"],
        "13": ["2.1",  "", "1"],    // 1番人気
        ...
      },
      "2": {
        "01": ["11.6", "22.1", "15"],  // 馬番01: [複勝下限, 複勝上限, 人気順]
        ...
      }
    }
  }
}
```

**キー:** `"1"` = 単勝, `"2"` = 複勝
**馬番:** ゼロ埋め2桁文字列 `"01"`, `"02"` ... `"18"`

### BeautifulSoup パース方法 (HTMLから)
```python
def parse_odds_html(html: str) -> dict[int, float]:
    """馬番 → 単勝オッズ のマッピングを返す"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.RaceOdds_HorseList_Table")
    if not table:
        return {}
    odds_map = {}
    for tr in table.select("tr"):
        waku_td = tr.find("td", class_=re.compile(r"^Waku\d"))
        if not waku_td:
            continue
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        umaban = tds[1].get_text(strip=True)
        odds_span = tds[5].select_one("span.Odds")
        odds_val = odds_span.get_text(strip=True) if odds_span else ""
        try:
            odds_map[int(umaban)] = float(odds_val)
        except ValueError:
            pass  # "---.-" など
    return odds_map
```

### APIから取得する方法 (推奨)
```python
import json

def fetch_odds_from_api(race_id: str, session) -> dict[int, float]:
    """単勝オッズを API から取得する (確定後は確定値)"""
    url = f"https://race.netkeiba.com/api/api_get_jra_odds.html?race_id={race_id}&type=1&action=update"
    # session は requests.Session または Playwright等
    data = json.loads(session.get(url).text)
    if data.get("status") != "result":
        return {}
    tan_odds = data["data"]["odds"].get("1", {})
    return {int(k): float(v[0]) for k, v in tan_odds.items() if v[0] not in ("", None)}
```

---

## 4. レース結果ページ (result)

### URL
```
https://race.netkeiba.com/race/result.html?race_id=XXXXXXXXXXXX
```

### テーブル構造
```html
<div class="ResultTableWrap">
  <table summary="全着順" class="RaceTable01 RaceCommon_Table ResultRefund Table_Show_All"
         id="All_Result_Table">
    <thead>
      <tr class="Header">
        <th class="Result_Num">着順</th>
        <th class="Waku">枠</th>
        <th class="Num">馬番</th>
        <th class="Horse_Info"><div class="Horse_Name">馬名</div></th>
        <th>性齢</th>
        <th>斤量</th>
        <th>騎手</th>
        <th class="Time">タイム</th>
        <th>着差</th>
        <th>人気</th>
        <th class="Odds">単勝オッズ</th>
        <th>後3F</th>
        <th>コーナー通過順</th>
        <th>厩舎</th>
        <th class="Weight">馬体重(増減)</th>
      </tr>
    </thead>
    <tbody>
      <tr class="FirstDisplay HorseList">...</tr>
    </tbody>
  </table>
</div>
```

### tbody 各行の構造
```html
<tr class="FirstDisplay HorseList">
  <!-- 着順 -->
  <td class="Result_Num"><div class="Rank">1</div></td>
  <!-- 枠番: class="Num Waku{N}" -->
  <td class="Num Waku7"><div>7</div></td>
  <!-- 馬番 -->
  <td class="Num Txt_C"><div>13</div></td>
  <!-- 馬名 + 馬ID -->
  <td class="Horse_Info">
    <span class="Horse_Name">
      <a href="https://db.netkeiba.com/horse/2022105102" target="_blank" title="クロワデュノール">
        <span class="HorseNameSpan">クロワデュノール</span>
      </a>
    </span>
  </td>
  <!-- 性齢 -->
  <td class="Horse_Info Txt_C">
    <span class="Lgt_Txt Txt_C">牡3</span>
  </td>
  <!-- 斤量 -->
  <td class="Jockey_Info">
    <span class="JockeyWeight">57.0</span>
  </td>
  <!-- 騎手 + 騎手ID -->
  <td class="Jockey">
    <a href="https://db.netkeiba.com/jockey/result/recent/01102/" target="_blank">
      <span class="JockeyNameSpan">北村友</span>
    </a>
  </td>
  <!-- タイム -->
  <td class="Time"><span class="RaceTime">2:23.7</span></td>
  <!-- 着差 -->
  <td class="Time"><span class="RaceTime"></span></td>  <!-- 1着は空 -->
  <!-- 人気 (色: BgYellow=1位, BgOrange=2-3位, それ以外は無色) -->
  <td class="Odds BgYellow Txt_C"><span class="OddsPeople">1</span></td>
  <!-- 単勝オッズ -->
  <td class="Odds Txt_R"><span class="Odds_Ninki">2.1</span></td>
  <!-- 後3F -->
  <td class="Time">34.2</td>
  <!-- コーナー通過順 -->
  <td class="PassageRate">4-3-2-3</td>
  <!-- 調教師 + 所属 + 調教師ID -->
  <td class="Trainer">
    <span class="Label2">栗東</span>
    <a href="https://db.netkeiba.com/trainer/result/recent/01151/" target="_blank" title="斉藤崇">
      <span class="TrainerNameSpan">斉藤崇</span>
    </a>
  </td>
  <!-- 馬体重(増減) -->
  <td class="Weight">504<small>(+4)</small></td>
</tr>
```

### BeautifulSoup パース方法
```python
import re
from bs4 import BeautifulSoup

def parse_result(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#All_Result_Table")
    if not table:
        return []
    results = []
    for tr in table.select("tr.HorseList"):
        # 着順
        rank_div = tr.select_one("td.Result_Num .Rank")
        rank = rank_div.get_text(strip=True) if rank_div else ""
        # 枠番
        waku_td = tr.find("td", class_=re.compile(r"Num Waku\d"))
        waku = waku_td.get_text(strip=True) if waku_td else ""
        # 馬番
        tds = tr.find_all("td")
        umaban = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        # 馬名 + 馬ID
        horse_a = tr.select_one("td.Horse_Info a[href*='/horse/']")
        horse_name = horse_a.select_one(".HorseNameSpan").get_text(strip=True) if horse_a and horse_a.select_one(".HorseNameSpan") else ""
        horse_id = re.search(r"/horse/(\d+)", horse_a["href"]).group(1) if horse_a else ""
        # 性齢
        sex_age_span = tr.select_one("td.Horse_Info.Txt_C .Lgt_Txt")
        sex_age = sex_age_span.get_text(strip=True) if sex_age_span else ""
        # 斤量
        kinryo_span = tr.select_one("td.Jockey_Info .JockeyWeight")
        kinryo = kinryo_span.get_text(strip=True) if kinryo_span else ""
        # 騎手 + 騎手ID
        jockey_a = tr.select_one("td.Jockey a")
        jockey_name = jockey_a.select_one(".JockeyNameSpan").get_text(strip=True) if jockey_a and jockey_a.select_one(".JockeyNameSpan") else ""
        jockey_id_m = re.search(r"/jockey/result/recent/(\d+)/", jockey_a["href"]) if jockey_a else None
        jockey_id = jockey_id_m.group(1) if jockey_id_m else ""
        # タイム
        time_tds = tr.select("td.Time")
        finish_time = time_tds[0].select_one(".RaceTime").get_text(strip=True) if time_tds else ""
        margin = time_tds[1].select_one(".RaceTime").get_text(strip=True) if len(time_tds) > 1 else ""
        # 後3F
        last3f = time_tds[2].get_text(strip=True) if len(time_tds) > 2 else ""
        # 人気
        popularity_span = tr.select_one("td.Odds.Txt_C .OddsPeople")
        popularity = popularity_span.get_text(strip=True) if popularity_span else ""
        # 単勝オッズ
        odds_span = tr.select_one("td.Odds.Txt_R span")
        odds = odds_span.get_text(strip=True) if odds_span else ""
        # コーナー通過順
        passage_td = tr.select_one("td.PassageRate")
        passage = passage_td.get_text(strip=True) if passage_td else ""
        # 調教師
        trainer_td = tr.select_one("td.Trainer")
        trainer_label = trainer_td.select_one("span.Label1, span.Label2") if trainer_td else None
        affiliation = trainer_label.get_text(strip=True) if trainer_label else ""
        trainer_span = trainer_td.select_one(".TrainerNameSpan") if trainer_td else None
        trainer_name = trainer_span.get_text(strip=True) if trainer_span else ""
        trainer_a = trainer_td.select_one("a") if trainer_td else None
        trainer_id_m = re.search(r"/trainer/result/recent/(\d+)/", trainer_a["href"]) if trainer_a else None
        trainer_id = trainer_id_m.group(1) if trainer_id_m else ""
        # 馬体重
        weight_td = tr.select_one("td.Weight")
        weight_text = weight_td.get_text(strip=True) if weight_td else ""
        w_match = re.match(r"(\d+)\(([+-]?\d+)\)", weight_text.replace(" ", ""))
        body_weight = int(w_match.group(1)) if w_match else None
        weight_diff = int(w_match.group(2)) if w_match else None

        results.append({
            "rank": int(rank) if rank.isdigit() else None,
            "waku": int(waku) if waku.isdigit() else None,
            "umaban": int(umaban) if umaban.isdigit() else None,
            "horse_name": horse_name,
            "horse_id": horse_id,
            "sex_age": sex_age,
            "kinryo": float(kinryo) if kinryo else None,
            "jockey_name": jockey_name,
            "jockey_id": jockey_id,
            "finish_time": finish_time,
            "margin": margin,
            "last3f": float(last3f) if last3f else None,
            "popularity": int(popularity) if popularity.isdigit() else None,
            "win_odds": float(odds) if odds else None,
            "passage_rate": passage,
            "trainer_name": trainer_name,
            "trainer_id": trainer_id,
            "affiliation": affiliation,
            "body_weight": body_weight,
            "weight_diff": weight_diff,
        })
    return results
```

---

## 5. URL・IDリンクパターン まとめ

| データ | URL パターン | ID抽出方法 |
|--------|-------------|-----------|
| 馬 | `https://db.netkeiba.com/horse/{horse_id}` | `/horse/(\d+)` |
| 騎手 | `https://db.netkeiba.com/jockey/result/recent/{jockey_id}/` | `/jockey/result/recent/(\d+)/` |
| 調教師 | `https://db.netkeiba.com/trainer/result/recent/{trainer_id}/` | `/trainer/result/recent/(\d+)/` |
| オッズAPI | `https://race.netkeiba.com/api/api_get_jra_odds.html?race_id={race_id}&type=1&action=update` | JSONレスポンス |

## 6. エンコーディング

- netkeiba.com はページによって EUC-JP を使用
- `requests.get(url)` 後に `response.encoding = 'euc-jp'` を設定するか、
  `response.content.decode('euc-jp', errors='replace')` で処理する
- BeautifulSoup の parser は `"html.parser"` または `"lxml"` を使用
