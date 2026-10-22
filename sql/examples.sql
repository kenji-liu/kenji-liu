-- 馬太鞍溪向量圖資的 DuckDB 查詢範例（可貼進 RustGIS 的 SQL 面板，或用 duckdb CLI 執行）
-- 注意：空間函式需要 spatial 擴充；以下範例的欄位名稱請依您的實際資料調整。

INSTALL spatial;
LOAD spatial;

-- 1. 本機或雲端的 GeoParquet 都能直接讀（雲端路徑需 INSTALL httpfs; LOAD httpfs;）
SELECT * FROM read_parquet('data/vector/cross_sections.parquet') LIMIT 10;

-- 2. 屬性篩選：粒徑 D50 大於 10 mm 的斷面
SELECT 斷面, d50_mm
FROM read_parquet('data/vector/cross_sections.parquet')
WHERE d50_mm > 10
ORDER BY d50_mm DESC;

-- 3. 空間計算：GeoParquet 的 geometry 欄位是 WKB，需先轉成 GEOMETRY
--    EPSG:3826 單位為公尺，可直接算長度與面積
SELECT 斷面, ST_Length(ST_GeomFromWKB(geometry)) AS 長度_m
FROM read_parquet('data/vector/cross_sections.parquet');

-- 4. 只讀取範圍內的資料：GeoParquet 1.1 的 bbox 欄位可讓 DuckDB 略過不相關的列群組
SELECT count(*)
FROM read_parquet('data/vector/cross_sections.parquet')
WHERE bbox.xmin < 300100 AND bbox.xmax > 300000
  AND bbox.ymin < 2600000 AND bbox.ymax > 2599800;
