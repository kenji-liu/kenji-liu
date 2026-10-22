#!/usr/bin/env python3
"""將向量圖資 (shp/gpkg/geojson...) 轉為 GeoParquet，並可同時輸出 FlatGeobuf。

用法:
    python scripts/to_geoparquet.py data/raw/斷面.shp data/vector/cross_sections.parquet
    python scripts/to_geoparquet.py in.gpkg out.parquet --layer 構造物 --fgb
"""
import argparse
from pathlib import Path

import geopandas as gpd


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--layer", help="多圖層檔案 (如 gpkg) 要讀的圖層名")
    ap.add_argument("--crs", default=None, help="來源缺少座標系統時指定，例如 EPSG:3826")
    ap.add_argument("--encoding", default=None, help="shp 中文欄位亂碼時指定，例如 big5")
    ap.add_argument("--fgb", action="store_true", help="同時輸出同名 .fgb (FlatGeobuf)")
    args = ap.parse_args()

    read_kw = {}
    if args.layer:
        read_kw["layer"] = args.layer
    if args.encoding:
        read_kw["encoding"] = args.encoding
    gdf = gpd.read_file(args.src, **read_kw)

    if gdf.crs is None:
        if not args.crs:
            raise SystemExit("來源沒有座標系統，請加 --crs EPSG:3826")
        gdf = gdf.set_crs(args.crs)

    # Hilbert 曲線排序：讓空間相近的資料在檔案中相鄰，雲端範圍查詢更省流量
    if len(gdf) > 1 and not gdf.geometry.isna().all():
        gdf = gdf.iloc[gdf.geometry.hilbert_distance().argsort()]

    args.dst.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(args.dst, compression="zstd", write_covering_bbox=True)
    print(f"完成: {args.dst} ({len(gdf)} 筆, {gdf.crs.to_string()})")

    if args.fgb:
        fgb = args.dst.with_suffix(".fgb")
        gdf.to_file(fgb, driver="FlatGeobuf")
        print(f"完成: {fgb}")


if __name__ == "__main__":
    main()
