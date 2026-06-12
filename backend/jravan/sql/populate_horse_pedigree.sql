-- populate_horse_pedigree.sql
-- 自宅PC専用: FDW jravan.v_pedigree（kbar_jravan の NL_UM 由来）から
-- アプリDB kbar の自己完結テーブル horse_pedigree へ血統を流し込む。
--
-- ・キー = netkeiba_id（= JV-Data kettonum）。DB間で安定なのでVPSへもそのまま同期可。
-- ・固定長cp932由来の trailing space を trim、空文字は NULL 化。
-- ・父(sire)が空の行は血統情報なしとみなしスキップ。
-- ・UPSERT。UMセットアップでカバレッジを増やした後に再実行すれば差分追加される。
--
-- 適用: docker exec -i kbar-postgres psql -U kbar -d kbar < backend/jravan/sql/populate_horse_pedigree.sql
-- 前提: jravan_fdw_mapping.sql 適用済み（jravan.v_pedigree が存在すること）。

INSERT INTO horse_pedigree
    (netkeiba_id, horse_name, sire, dam, paternal_grandsire, broodmare_sire, source, updated_at)
SELECT
    trim(p.netkeiba_id)                          AS netkeiba_id,
    NULLIF(trim(p.horse_name), '')               AS horse_name,
    NULLIF(trim(p.sire), '')                     AS sire,
    NULLIF(trim(p.dam), '')                       AS dam,
    NULLIF(trim(p.paternal_grandsire), '')        AS paternal_grandsire,
    NULLIF(trim(p.broodmare_sire), '')            AS broodmare_sire,
    'jravan_um'                                   AS source,
    now()                                          AS updated_at
FROM jravan.v_pedigree p
WHERE trim(COALESCE(p.netkeiba_id, '')) <> ''
  AND NULLIF(trim(p.sire), '') IS NOT NULL
ON CONFLICT (netkeiba_id) DO UPDATE SET
    horse_name         = EXCLUDED.horse_name,
    sire               = EXCLUDED.sire,
    dam                = EXCLUDED.dam,
    paternal_grandsire = EXCLUDED.paternal_grandsire,
    broodmare_sire     = EXCLUDED.broodmare_sire,
    source             = EXCLUDED.source,
    updated_at         = now();

-- 確認用サマリ
SELECT count(*) AS total_pedigree_rows FROM horse_pedigree;
