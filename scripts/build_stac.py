#!/usr/bin/env python3
"""掃描 data/ 產生馬太鞍溪的 STAC 目錄 (catalog/)。

檔名慣例:
    data/cog/YYYYMMDD_<產品>.tif      產品例: ortho, dsm, dem, dod, depth, velocity
    data/cog/YYYYMMDD.meta.json       (選用) 該日期的觀測說明，欄位見 README
    data/vector/<名稱>.parquet|.fgb   向量圖資，登錄為 collection 層級資產
    data/pointcloud/YYYYMMDD*.copc.laz|.laz   點雲，登錄為該日期 Item 的資產

同一日期的所有產品合併成一個 Item，各產品是該 Item 的 assets。

用法:
    python scripts/build_stac.py
    python scripts/build_stac.py --base-url https://example.org/mataian   # 資料上雲後
"""
import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pystac
import rasterio
from pystac.extensions.projection import ProjectionExtension
from rasterio.warp import transform_bounds

ROOT = Path(__file__).resolve().parents[1]
RASTER_RE = re.compile(r"^(\d{8})_([A-Za-z0-9\-]+)\.tif$")
POINTCLOUD_RE = re.compile(r"^(\d{8})[_\-.]?.*\.(copc\.laz|laz|las)$", re.IGNORECASE)

PRODUCT_LABELS = {
    "ortho": "正射影像",
    "dsm": "數值地表模型 (DSM)",
    "dem": "數值高程模型 (DEM)",
    "dod": "DEM of Difference 沖淤差分",
    "depth": "模擬水深",
    "velocity": "模擬流速",
}
VECTOR_TYPES = {
    ".parquet": "application/vnd.apache.parquet",
    ".fgb": "application/vnd.flatgeobuf",
}


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone.utc)


def href_for(path: Path, data_dir: Path, base_url: str | None, item_dir: Path) -> str:
    rel = path.relative_to(data_dir).as_posix()
    if base_url:
        return f"{base_url.rstrip('/')}/{rel}"
    return Path(os.path.relpath(path, item_dir)).as_posix()


def raster_info(path: Path):
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise SystemExit(f"{path} 沒有座標系統")
        bbox = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
        return {
            "bbox": list(bbox),
            "epsg": ds.crs.to_epsg(),
            "shape": [ds.height, ds.width],
            "transform": list(ds.transform)[:6],
            "gsd": abs(ds.transform.a),
            "nodata": ds.nodata,
            "dtype": ds.dtypes[0],
            "bands": ds.count,
        }


def union_bbox(boxes):
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def bbox_to_geom(b):
    w, s, e, n = b
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", help="資料公開網址前綴；省略則使用相對路徑 (本機用)")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "catalog")
    ap.add_argument("--no-validate", action="store_true", help="略過 STAC schema 驗證 (驗證需連網取得 extension schema)")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config" / "collection.json").read_text(encoding="utf-8"))
    cog_dir, vec_dir, pc_dir = args.data / "cog", args.data / "vector", args.data / "pointcloud"

    # --- 依日期分組 -------------------------------------------------------
    rasters: dict[str, dict[str, Path]] = defaultdict(dict)
    for p in sorted(cog_dir.glob("*.tif")):
        m = RASTER_RE.match(p.name)
        if not m:
            print(f"略過 (檔名不符 YYYYMMDD_產品.tif): {p.name}")
            continue
        rasters[m.group(1)][m.group(2).lower()] = p

    pointclouds: dict[str, list[Path]] = defaultdict(list)
    if pc_dir.exists():
        for p in sorted(pc_dir.iterdir()):
            m = POINTCLOUD_RE.match(p.name)
            if m:
                pointclouds[m.group(1)].append(p)

    dates = sorted(set(rasters) | set(pointclouds))
    if not dates:
        raise SystemExit("data/cog 與 data/pointcloud 內沒有符合檔名慣例的資料")

    # --- 建立 Items -------------------------------------------------------
    items: list[pystac.Item] = []
    for d in dates:
        meta_path = cog_dir / f"{d}.meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

        infos = {prod: raster_info(p) for prod, p in rasters.get(d, {}).items()}
        if not infos:
            print(f"略過 {d}: 只有點雲、無法取得範圍 (請至少提供一個 COG)")
            continue
        bbox = union_bbox([i["bbox"] for i in infos.values()])

        props = {"title": meta.get("title", f"馬太鞍溪 {d[:4]}-{d[4:6]}-{d[6:]}")}
        for k in ("platform", "instruments", "gsd", "description"):
            if k in meta:
                props[k] = meta[k]
        # 自訂欄位加上命名空間前綴，避免和 STAC 標準欄位衝突
        for k in ("event", "accuracy_h_m", "accuracy_v_m", "gcp_count", "processing_software"):
            if k in meta:
                props[f"mataian:{k}"] = meta[k]

        item = pystac.Item(
            id=f"mataian-{d}",
            geometry=bbox_to_geom(bbox),
            bbox=bbox,
            datetime=parse_date(d),  # 僅精確到日，時間固定為 00:00Z
            properties=props,
        )

        # 以第一個產品的投影資訊作為 Item 層級；各 asset 另記自己的形狀與轉換
        first = next(iter(infos.values()))
        proj = ProjectionExtension.ext(item, add_if_missing=True)
        proj.epsg = first["epsg"]

        for prod, info in infos.items():
            asset = pystac.Asset(
                href="PLACEHOLDER",
                title=PRODUCT_LABELS.get(prod, prod),
                media_type=pystac.MediaType.COG,
                roles=["data"] if prod != "ortho" else ["data", "visual"],
                extra_fields={
                    "gsd": round(info["gsd"], 4),
                    "raster:bands": [{"data_type": info["dtype"], **({"nodata": info["nodata"]} if info["nodata"] is not None else {})}],
                },
            )
            item.add_asset(prod, asset)
            pa = ProjectionExtension.ext(asset, add_if_missing=True)
            pa.epsg = info["epsg"]
            pa.shape = info["shape"]
            pa.transform = info["transform"]

        for i, p in enumerate(pointclouds.get(d, [])):
            media = "application/vnd.laszip+copc" if p.name.lower().endswith(".copc.laz") else "application/vnd.las"
            if p.suffix.lower() == ".laz" and not p.name.lower().endswith(".copc.laz"):
                media = "application/vnd.laszip"
            item.add_asset(
                "pointcloud" if i == 0 else f"pointcloud-{i + 1}",
                pystac.Asset(href="PLACEHOLDER", title="點雲", media_type=media, roles=["data"]),
            )
        item.stac_extensions.append("https://stac-extensions.github.io/raster/v1.1.0/schema.json")
        item.extra_fields["_files"] = {
            **{prod: str(p) for prod, p in rasters.get(d, {}).items()},
            **{(f"pointcloud" if i == 0 else f"pointcloud-{i + 1}"): str(p) for i, p in enumerate(pointclouds.get(d, []))},
        }
        items.append(item)

    # --- Collection / Catalog --------------------------------------------
    t0, t1 = items[0].datetime, items[-1].datetime
    collection = pystac.Collection(
        id=cfg["id"],
        title=cfg["title"],
        description=cfg["description"],
        license=cfg.get("license", "proprietary"),
        keywords=cfg.get("keywords"),
        providers=[pystac.Provider(**p) for p in cfg.get("providers", [])],
        extent=pystac.Extent(
            pystac.SpatialExtent([union_bbox([it.bbox for it in items])]),
            pystac.TemporalExtent([[t0, t1]]),
        ),
    )
    catalog = pystac.Catalog(id="mataian-catalog", description="馬太鞍溪數位身份目錄")
    catalog.add_child(collection)
    for it in items:
        collection.add_item(it)

    if vec_dir.exists():
        for p in sorted(vec_dir.iterdir()):
            if p.suffix.lower() in VECTOR_TYPES:
                collection.add_asset(
                    p.stem,
                    pystac.Asset(href="PLACEHOLDER", title=p.stem, media_type=VECTOR_TYPES[p.suffix.lower()], roles=["data"]),
                )
                collection.assets[p.stem].extra_fields["_file"] = str(p)

    # --- 寫出，並填入 asset href ----------------------------------------
    catalog.normalize_hrefs(str(args.out.resolve()))
    for it in items:
        item_dir = Path(it.get_self_href()).parent
        for key, f in it.extra_fields.pop("_files").items():
            it.assets[key].href = href_for(Path(f), args.data, args.base_url, item_dir)
    for key, a in collection.assets.items():
        f = a.extra_fields.pop("_file")
        a.href = href_for(Path(f), args.data, args.base_url, Path(collection.get_self_href()).parent)

    catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
    print(f"已輸出 {len(items)} 個 Item、{len(collection.assets)} 個向量資產 → {args.out}")
    if not args.no_validate:
        print("驗證中...")
        catalog.validate_all()
        print("STAC 驗證通過")


if __name__ == "__main__":
    main()
