-- ============================================================
-- JRA-VAN (kbar_jravan) ↔ アプリDB(kbar) ID突合マッピング層
-- ------------------------------------------------------------
-- 同一PostgreSQLインスタンス内の別DB kbar_jravan を postgres_fdw で
-- アプリDB kbar から参照可能にし、netkeiba ID で結合するビューを定義する。
--
-- 【突合キー（2026-06-11 実証済み・確率的マッチ不要の完全一致）】
--   レース: race_id = year || lpad(jyocd,2) || lpad(kaiji,2) || lpad(nichiji,2) || lpad(racenum,2)
--           = アプリ races.race_id（2026-02-21/22で 72/72 完全一致）
--   競走馬: JV-Data NL_SE.kettonum（血統登録番号）= アプリ horses.netkeiba_id
--           （1027/1027 完全一致。netkeibaの馬IDがJRA血統登録番号そのものであるため）
--
-- 適用: psql -U kbar -d kbar -f backend/jravan/sql/jravan_fdw_mapping.sql
--   （Docker: docker exec -i kbar-postgres psql -U kbar -d kbar < この.sql）
-- ============================================================

-- 1) FDW 拡張・外部サーバ・ユーザマッピング ---------------------------------
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_foreign_server WHERE srvname = 'jravan_srv') THEN
    CREATE SERVER jravan_srv FOREIGN DATA WRAPPER postgres_fdw
      OPTIONS (host '127.0.0.1', port '5432', dbname 'kbar_jravan');
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_user_mappings WHERE srvname = 'jravan_srv' AND usename = 'kbar'
  ) THEN
    CREATE USER MAPPING FOR kbar SERVER jravan_srv
      OPTIONS (user 'kbar', password 'kbar_dev_password');
  END IF;
END $$;

-- 2) 外部テーブルを jravan スキーマに取込 -----------------------------------
CREATE SCHEMA IF NOT EXISTS jravan;

-- 既存の外部テーブルを作り直す（IMPORT は既存があると失敗するため一旦掃除）
DROP VIEW IF EXISTS jravan.v_confirmed_payouts CASCADE;
DROP VIEW IF EXISTS jravan.v_confirmed_win_odds CASCADE;
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT ft.relname FROM pg_foreign_table f
    JOIN pg_class ft ON ft.oid = f.ftrelid
    JOIN pg_namespace n ON n.oid = ft.relnamespace
    WHERE n.nspname = 'jravan'
  LOOP
    EXECUTE format('DROP FOREIGN TABLE IF EXISTS jravan.%I CASCADE', r.relname);
  END LOOP;
END $$;

IMPORT FOREIGN SCHEMA public
  LIMIT TO (nl_ra, nl_se, nl_hr, nl_um, nl_o1, nl_o2, nl_o3, nl_o4, nl_o5, nl_o6)
  FROM SERVER jravan_srv INTO jravan;

-- 3) netkeiba race_id 構築関数 --------------------------------------------
CREATE OR REPLACE FUNCTION jravan.build_race_id(
  p_year int, p_jyocd text, p_kaiji int, p_nichiji int, p_racenum int
) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT p_year::text
       || lpad(p_jyocd, 2, '0')
       || lpad(p_kaiji::text, 2, '0')
       || lpad(p_nichiji::text, 2, '0')
       || lpad(p_racenum::text, 2, '0');
$$;

-- 4) 確定払戻ビュー（NL_HR・netkeiba race_id キー） -------------------------
--    単勝/複勝/枠連/馬連/ワイド/馬単/三連複/三連単の払戻金・人気を1行/レース。
CREATE VIEW jravan.v_confirmed_payouts AS
SELECT
  jravan.build_race_id(year, jyocd, kaiji, nichiji, racenum) AS race_id,
  syussotosu                              AS runners,
  tanumaban  AS tan_umaban,  tanpay  AS tan_pay,  tanninki  AS tan_ninki,
  fukuumaban AS fuku_umaban, fukupay AS fuku_pay, fukuninki AS fuku_ninki,
  umarenkumi AS umaren_kumi, umarenpay AS umaren_pay,
  widekumi   AS wide_kumi,   widepay AS wide_pay,
  umatankumi AS umatan_kumi, umatanpay AS umatan_pay,
  sanrenfukukumi AS sanrenfuku_kumi, sanrenfukupay AS sanrenfuku_pay,
  sanrentankumi  AS sanrentan_kumi,  sanrentanpay  AS sanrentan_pay
FROM jravan.nl_hr;

-- 4b) 血統ビュー（NL_UM・kettonum=アプリ horses.netkeiba_id キー） ------------
--    父/母/父父/母父 を抜き出す（3代血統 ketto3infobamei: 1父 2母 3父父 4父母 5母父 6母母）。
DROP VIEW IF EXISTS jravan.v_pedigree CASCADE;
CREATE VIEW jravan.v_pedigree AS
SELECT
  kettonum                AS netkeiba_id,
  bamei                   AS horse_name,
  ketto3infobamei1        AS sire,             -- 父
  ketto3infobamei2        AS dam,              -- 母
  ketto3infobamei3        AS paternal_grandsire, -- 父父
  ketto3infobamei5        AS broodmare_sire    -- 母父
FROM jravan.nl_um;

-- 5) 確定単勝オッズビュー（NL_O1・datakubun=5確定・netkeiba race_id+馬番キー） --
CREATE VIEW jravan.v_confirmed_win_odds AS
SELECT
  jravan.build_race_id(year, jyocd, kaiji, nichiji, racenum) AS race_id,
  umaban      AS umaban,
  tanodds     AS win_odds,
  tanninki    AS win_favorite
FROM jravan.nl_o1
WHERE tanodds IS NOT NULL
  AND umaban IS NOT NULL AND umaban > 0;
