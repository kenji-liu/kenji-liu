#!/usr/bin/env python3
"""將 GeoTIFF 轉為 Cloud-Optimized GeoTIFF (COG)。

用法:
    python scripts/to_cog.py data/raw/dsm.tif data/cog/20251005_dsm.tif
    python scripts/to_cog.py in.tif out.tif --resampling nearest   # 分類/二值圖
"""
import argparse
from pathlib import Path

import rasterio
from rasterio.shutil import copy as rio_copy


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument(
        "--resampling",
        default="bilinear",
        choices=["nearest", "bilinear", "cubic", "average"],
        help="金字塔重取樣方式；DSM/DEM/正射用 bilinear，分類圖用 nearest",
    )
    ap.add_argument("--compress", default="deflate", choices=["deflate", "lzw", "zstd"])
    args = ap.parse_args()

    with rasterio.open(args.src) as ds:
        if ds.crs is None:
            raise SystemExit(f"{args.src} 沒有座標系統，請先指定 (例如 gdal_edit.py -a_srs EPSG:3826)")
        is_float = ds.dtypes[0].startswith("float")

    args.dst.parent.mkdir(parents=True, exist_ok=True)
    opts = dict(
        driver="COG",
        compress=args.compress.upper(),
        blocksize=512,
        overview_resampling=args.resampling.upper(),
        bigtiff="IF_SAFER",
    )
    if is_float and args.compress != "zstd":
        opts["predictor"] = 3  # 浮點資料用 predictor 可明顯提高壓縮率
    rio_copy(args.src, args.dst, **opts)
    print(f"完成: {args.dst}")


if __name__ == "__main__":
    main()
