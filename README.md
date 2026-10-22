# 馬太鞍溪數位身份 × RustGIS

把馬太鞍溪的多期 UAV 成果、沖淤差分、數值模擬與向量圖資，整理成一份**雲端原生、可被 STAC 搜尋**的資料集，
讓 [RustGIS](https://github.com/opengeos/RustGIS)（以及 QGIS、Python、DuckDB 等任何支援這些格式的工具）都能直接開啟。

「數位身份」= 一份 STAC Collection：每個觀測日期是一個 Item，每種產品（正射、DSM、DoD…）是該 Item 的 Asset，
並附上座標系統、解析度、精度、事件背景等後設資料。

## 目錄結構

```
config/collection.json     集合的名稱、說明、授權、提供者（請依實際情況修改）
data/cog/                  YYYYMMDD_<產品>.tif（Cloud-Optimized GeoTIFF）、YYYYMMDD.meta.json
data/vector/               GeoParquet (.parquet) / FlatGeobuf (.fgb)
data/pointcloud/           COPC / LAZ 點雲（選用）
catalog/                   由 build_stac.py 產生的 STAC 目錄（可版控）
scripts/                   轉檔與建目錄腳本
sql/examples.sql           DuckDB 查詢範例
```

`data/` 內的大型檔案不進版控（見 `.gitignore`），只保留目錄結構。

## 使用流程

```bash
pip install -r requirements.txt

# 1. 轉成 COG（DSM/DEM/正射用預設 bilinear；分類圖加 --resampling nearest）
python scripts/to_cog.py 原始/dsm.tif data/cog/20251005_dsm.tif
python scripts/to_cog.py 原始/ortho.tif data/cog/20251005_ortho.tif

# 2. 向量轉 GeoParquet（中文 shp 亂碼加 --encoding big5；缺座標系統加 --crs EPSG:3826）
python scripts/to_geoparquet.py 原始/斷面.shp data/vector/cross_sections.parquet --fgb

# 3. （選用）補觀測說明，見下方 meta.json 欄位
# 4. 建立 STAC 目錄
python scripts/build_stac.py
```

### `YYYYMMDD.meta.json` 欄位（皆為選用）

```json
{
  "title": "馬太鞍溪 2025-10-05 UAV 航拍",
  "platform": "uav",
  "instruments": ["RTK UAV"],
  "gsd": 0.05,
  "description": "...",
  "event": "堰塞湖溢流後",
  "accuracy_h_m": 0.05,
  "accuracy_v_m": 0.08,
  "gcp_count": 12,
  "processing_software": "..."
}
```

`event`、`accuracy_*`、`gcp_count`、`processing_software` 會以 `mataian:` 前綴寫入 Item properties。

## 在 RustGIS 開啟

- **本機**：直接開啟 `data/cog/*.tif`、`data/vector/*.parquet`。
- **雲端**：資料上傳到 S3 / Source Cooperative 等公開位置後，執行
  `python scripts/build_stac.py --base-url https://你的網址/mataian`，
  再把 `catalog/` 一起放上去；在 RustGIS 以網址開啟 COG 或 GeoParquet，或加入該 STAC 目錄搜尋。
- **SQL**：RustGIS 的 DuckDB Spatial 面板可直接執行 `sql/examples.sql`。
- **Python / Jupyter**：`pip install rustgis`，或用 `pystac.Catalog.from_file("catalog/catalog.json")` 讀目錄。

## 驗證狀態

在合成資料（2 期、DSM + 正射 + 斷面向量）上驗證過：

- ✅ `to_cog.py`、`to_geoparquet.py`、`build_stac.py` 可執行，產出的 STAC JSON 結構與相對路徑正確。
- ✅ GeoParquet 可被 DuckDB 讀取並做屬性篩選。
- ⚠️ **未驗證**：STAC schema 驗證（該環境無法下載 schema，請在可連網處執行 `python scripts/build_stac.py`，預設會驗證）。
- ⚠️ **未驗證**：DuckDB `spatial` 空間函式（`sql/examples.sql` 第 3 段起）。
- ⚠️ **未驗證**：RustGIS v0.3.0 實際開啟這些檔案與 STAC 目錄的行為；功能清單來自發布文，請以官方文件為準。
- ⚠️ 尚未用真實馬太鞍溪資料測試；`proj:*` 與資產欄位是依 COG 內容自動讀取。

## 資料使用提醒

若 RustGIS 啟用 AI 助理，傳給模型的內容會離開本機。計畫成果、未公開竣工圖資請先確認授權後再使用，
`config/collection.json` 的 `license` 預設為 `proprietary`。
