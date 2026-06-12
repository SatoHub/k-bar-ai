-- populate_confirmed_jravan.sql
-- 自宅PC専用: JV-Data由来の確定単勝オッズ・確定払戻を、アプリDB kbar の
-- 自己完結テーブル confirmed_win_odds / confirmed_payouts へ流し込む。
--
-- ・キー = netkeiba race_id（+ 馬番）。アプリ races テーブルに依存しない純レースデータ。
-- ・本番(VPS)の races は race_id でこれらに結合できる（日付が重なるため）。
-- ・UPSERT。日次同期でJV-Dataが増えた後に再実行すれば差分追加される。
--
-- 適用: docker exec -i kbar-postgres psql -U kbar -d kbar < backend/jravan/sql/populate_confirmed_jravan.sql
-- 前提: jravan_fdw_mapping.sql 適用済み（jravan.v_confirmed_* ビューが存在すること）。

-- 1) 確定単勝オッズ -----------------------------------------------------------
INSERT INTO confirmed_win_odds (race_id, umaban, win_odds, win_favorite, updated_at)
SELECT race_id, umaban::smallint, win_odds, win_favorite::smallint, now()
FROM jravan.v_confirmed_win_odds
WHERE umaban IS NOT NULL
ON CONFLICT (race_id, umaban) DO UPDATE SET
    win_odds     = EXCLUDED.win_odds,
    win_favorite = EXCLUDED.win_favorite,
    updated_at   = now();

-- 2) 確定払戻 ---------------------------------------------------------------
INSERT INTO confirmed_payouts (
    race_id, runners,
    tan_umaban, tan_pay, tan_ninki,
    fuku_umaban, fuku_pay, fuku_ninki,
    umaren_kumi, umaren_pay,
    wide_kumi, wide_pay,
    umatan_kumi, umatan_pay,
    sanrenfuku_kumi, sanrenfuku_pay,
    sanrentan_kumi, sanrentan_pay,
    updated_at)
SELECT
    race_id, runners,
    tan_umaban, tan_pay, tan_ninki,
    fuku_umaban, fuku_pay, fuku_ninki,
    umaren_kumi, umaren_pay,
    wide_kumi, wide_pay,
    umatan_kumi, umatan_pay,
    sanrenfuku_kumi, sanrenfuku_pay,
    sanrentan_kumi, sanrentan_pay,
    now()
FROM jravan.v_confirmed_payouts
ON CONFLICT (race_id) DO UPDATE SET
    runners         = EXCLUDED.runners,
    tan_umaban      = EXCLUDED.tan_umaban,      tan_pay      = EXCLUDED.tan_pay,      tan_ninki = EXCLUDED.tan_ninki,
    fuku_umaban     = EXCLUDED.fuku_umaban,     fuku_pay     = EXCLUDED.fuku_pay,     fuku_ninki = EXCLUDED.fuku_ninki,
    umaren_kumi     = EXCLUDED.umaren_kumi,     umaren_pay   = EXCLUDED.umaren_pay,
    wide_kumi       = EXCLUDED.wide_kumi,       wide_pay     = EXCLUDED.wide_pay,
    umatan_kumi     = EXCLUDED.umatan_kumi,     umatan_pay   = EXCLUDED.umatan_pay,
    sanrenfuku_kumi = EXCLUDED.sanrenfuku_kumi, sanrenfuku_pay = EXCLUDED.sanrenfuku_pay,
    sanrentan_kumi  = EXCLUDED.sanrentan_kumi,  sanrentan_pay  = EXCLUDED.sanrentan_pay,
    updated_at      = now();

-- 確認用サマリ
SELECT
    (SELECT count(*) FROM confirmed_win_odds) AS win_odds_rows,
    (SELECT count(DISTINCT race_id) FROM confirmed_win_odds) AS win_odds_races,
    (SELECT count(*) FROM confirmed_payouts) AS payout_races;
