# SPDX-License-Identifier: MIT
"""
Ground-mounted PV potential per country (``renewable_limits.ground_pv_file``).

    python scripts/update_ground_pv_potential.py <country_shapes.geojson> \
        --wdpa <WDPA polygons> --hnv <HNV farmland 2012 raster> \
        (--gebco <GEBCO_2014_2D.nc> | --slope <raster [deg]>) \
        [--out data/ground_pv_potential.csv]

Run in the pixi env of the fork (rasterio, geopandas). Cap per country [GW] =

- **farmland**: CORINE 12–20 (arable land, permanent crops, pastures, annual crops with
  permanent crops, complex cultivation patterns) outside protected areas (Natura 2000,
  WDPA) and outside High Nature Value farmland (EEA 2012); CORINE 21 (agriculture with
  significant natural vegetation) and 22 (agro-forestry) left out. The national rule's
  share of farmland applies to that eligible area at ``FARM_DENSITY`` (1 ha/MW). DE:
  the EEG ceiling (177.5 GW) as a share of all CORINE farmland (12–22), applied the same
  way (``FARMLAND_RULES``);
- **other land**: brownfield and transport corridors only (CORINE 3, 4, 7–9) outside
  protected areas, slope <= 10°, 10 % of that land at 80 MW/km² (Tröndle et al. 2019's
  share and density). No natural land (CORINE 26–29, 31, 32) and no settlements.

PyPSA-Eur's default rule for the land outside farmland (CORINE 1–11, 26, 31, 32 outside
Natura 2000 at 5.1 MW/km²) is kept as a reference column (``other_land_pypsa_gw``). Rules
and sources: ``FARMLAND_RULES`` and ``docs/energy.md`` ("Ground-mounted PV potential").
CORINE 2018 (v18_5, 250 m), Natura 2000 (2025-08-15) and GEBCO 2014 (30″, ~1 km; the
slope is computed from it, which underestimates steep terrain) are the rasters PyPSA-Eur
already uses; WDPA and HNV farmland are downloaded by hand (see docs).
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
import rasterio.io
import rasterio.mask
import rasterio.warp

CORINE = "data/corine/archive/v18_5/corine.tif"
NATURA = "data/natura/archive/2025-08-15/natura.tiff"
FARMLAND_ALL = list(range(12, 23))  # CORINE agricultural areas
FARMLAND = list(range(12, 21))  # without 21 (natural vegetation) and 22 (agro-forestry)
PYPSA_OTHER = list(range(1, 12)) + [26, 31, 32]  # reference only
PYPSA_DENSITY = 5.1  # MW/km², PyPSA-Eur default for utility PV
FARM_DENSITY = 100.0  # MW/km² of fenced site (1 ha/MW, UBA, new German plants)

#: country → (share of farmland, ceiling GW or None, rule, source). Share used when no
#: ceiling. Rules checked 2026-11-12 in the official texts ("verified") where reachable.
#: No text except the EEG sets a quantity: the shares are modelling choices, read
#: against the national targets (docs/energy.md).
FARMLAND_RULES = {
    "DE": (None, 177.5, "EEG §37(4): no tenders for ground PV on agricultural land "
           "above 80 GW operating, 177.5 GW after 31 Dec 2030; arable / grassland only "
           "in less-favoured areas (§37(1) Nr. 2 h, i) or as Agri-PV (Nr. 3)",
           "gesetze-im-internet.de/eeg_2014/__37.html (verified, version 15.5.2024)"),
    "FR": (0.005, None, "Code de l'urbanisme L.111-29 (loi APER 2023-175 art. 54): "
           "non-agrivoltaic solar on agricultural, natural or forest land only on surfaces "
           "of the departmental document-cadre (prefectoral order): land not farmable "
           "(R.111-56) or not farmed for >= 10 years before March 2023 (R.111-57), plus "
           "listed categories (R.111-58: brownfields, quarries, landfills...); "
           "agrivoltaics: yield > 90 % of a control plot (code de l'énergie R.314-114), "
           "coverage <= 40 % above 10 MWc for non-proven technologies (R.314-118); no "
           "area or capacity limit", "legifrance: L.111-29, décret 2024-318 (verified)"),
    "GB": (0.01, None, "Solar Roadmap 2025: 45-47 GW solar by 2030 on up to 0.4 % of "
           "UK land; best and most versatile land must be justified, lower-quality land "
           "preferred", "gov.uk Solar Roadmap, accessible webpage (verified)"),
    "NL": (0.005, None, "Aangescherpte voorkeursvolgorde zon (Kamerstuk 32813 nr. 1310, "
           "26 Oct 2023): solar on farmland and nature land 'in principe ongewenst'; "
           "exceptions only for agri-PV with a substantial farming function, land in "
           "transition under binding agreements, or projects that reduce grid congestion; "
           "binding through the provincial omgevingsverordeningen since early 2025 "
           "(Kamerstuk 32813 nr. 1464)", "officielebekendmakingen.nl (verified)"),
    "BE": (0.005, None, "Wallonia: circulaire photovoltaïque of 14 Mar 2024 (replaces "
           "12 Jan 2022): farmland must keep its food function; ground PV on farmed "
           "parcels only as research pilot projects compatible with farming. Flanders: "
           "policy note 'Zonneparken en agrivoltaïcs in agrarisch gebied' (farming stays "
           "primary; 6 projects advised negatively in 2025)", "Wallonia: circular, UVCW "
           "(verified); Flanders: minister's answers via Solar Magazine (secondary)"),
    "IE": (0.01, None, "No limit on farmland in law or guidance (no national solar "
           "planning guidelines, 2025); solar farms need full planning permission "
           "(farm exemption S.I. 493/2022 Class 18: <= 75 m2 free-standing); 8 GW solar "
           "by 2030 (CAP25)", "irishstatutebook.ie (verified); CAP25 target via IEA "
           "(secondary, gov.ie unreachable)"),
    "DK": (0.02, None, "No national limit on farmland; municipal planning plus "
           "state-designated energy parks (lov nr 614 of 11 Jun 2024); ambition of a "
           "market-driven quadrupling of land-based solar and wind by 2030 (aftale of "
           "10 Oct 2025)", "kefm.dk agreement (verified), retsinformation.dk"),
    "LU": (0.01, None, "Agrivoltaic tenders on grassland and arable land (pilot 2022: "
           "50 MW; 2025: 75 MWc, 100 kWc-5 MWc, an active farmer in each project)",
           "gouvernement.lu, guichet.public.lu (verified)"),
    "NO": (0.005, None, "Jordlova §9: cultivated land not to be used for non-farming "
           "purposes except by dispensation; not applicable to plants with a concession "
           "(energiloven §3-1) or zoned in a reguleringsplan (§2); national goal <= 2,000 "
           "daa (200 ha) of cultivated land converted per year by 2030, all uses (~0.5 % "
           "of farmland to 2050); farmland ~3 % of the land", "lovdata.no (verified), "
           "regjeringen.no"),
}
DEFAULT_SHARE = 0.01


#: Other land: brownfield and transport corridors (CORINE 3 industrial or commercial
#: units, 4 road and rail networks and associated land, 7 mineral extraction, 8 dump
#: sites, 9 construction sites), outside protected areas, slope <= 10°, 10 % of the land
#: at 80 MW/km² (share and density of Tröndle et al. 2019's technical-social potential).
#: Natural land (CORINE 26-29, 31, 32: grassland, heath, moors, sclerophyllous
#: vegetation, transitional woodland-shrub, bare rock, sparse vegetation) is excluded.
BROWNFIELD_CORRIDORS = [3, 4, 7, 8, 9]
OTHER_SHARE = 0.10
OTHER_DENSITY = 80.0  # MW/km²
MAX_SLOPE = 10.0  # degrees


def on_grid(src, data, transform, resampling, nodata=None, dtype="uint8"):
    """``src`` band 1 reprojected onto the CORINE window ``data``/``transform``."""
    out = np.zeros(data[0].shape, dtype=dtype)
    rasterio.warp.reproject(
        rasterio.band(src, 1), out, src_nodata=nodata, dst_transform=transform,
        dst_crs="EPSG:3035", resampling=resampling,
    )
    return out


def slope_from_gebco(path):
    """Slope [degrees] of GEBCO's land elevation (sea clipped at 0 m), as an
    in-memory raster: central differences, x spacing scaled by cos(latitude)."""
    with rasterio.open(path) as dem:  # PyPSA-Eur's copy is already cut to Europe
        z = np.clip(dem.read(1).astype("float64"), 0, None)
        transform = dem.transform
    lat = transform.f + transform.e * (np.arange(z.shape[0]) + 0.5)
    dy = 111320.0 * abs(transform.e)
    dx = 111320.0 * transform.a * np.cos(np.radians(lat))[:, None]
    gy, gx = np.gradient(z)
    deg = np.degrees(np.arctan(np.hypot(gx / dx, gy / dy))).astype("float32")
    mem = rasterio.io.MemoryFile()
    with mem.open(driver="GTiff", height=deg.shape[0], width=deg.shape[1], count=1,
                  dtype="float32", crs="EPSG:4326", transform=transform) as out:
        out.write(deg, 1)
    return mem.open()


def read_wdpa(path, shapes, landscape=True):
    """Designated terrestrial and coastal WDPA polygons in the region (EPSG:3035).
    ``landscape=False`` drops landscape designations (IUCN V: landscape protection
    areas, regional nature parks, UK national parks and AONBs; biosphere-reserve
    transition areas): lived-in farmland protected for scenery, not biodiversity."""
    box = tuple(shapes.to_crs(4326).total_bounds)
    wdpa = gpd.read_file(path, bbox=box)
    wdpa = wdpa[wdpa.geom_type.isin(["Polygon", "MultiPolygon"])]
    if "STATUS" in wdpa:
        wdpa = wdpa[wdpa["STATUS"].isin(["Designated", "Inscribed", "Established"])]
    if "REALM" in wdpa:  # WDPA since 2025
        wdpa = wdpa[wdpa["REALM"] != "Marine"]
    elif "MARINE" in wdpa:  # older releases: 0 terrestrial, 1 coastal, 2 marine
        wdpa = wdpa[wdpa["MARINE"].astype(str) != "2"]
    if not landscape:
        desig = wdpa.get("DESIG_ENG", pd.Series("", index=wdpa.index)).astype(str)
        wdpa = wdpa[(wdpa.get("IUCN_CAT") != "V")
                    & ~desig.str.contains("transition", case=False)]
    return wdpa.to_crs(3035)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    p.add_argument("country_shapes", type=Path)
    p.add_argument("--out", type=Path, default=Path("data/ground_pv_potential.csv"))
    p.add_argument("--wdpa", type=Path, required=True,
                   help="WDPA polygons (any OGR format)")
    p.add_argument("--hnv", type=Path, required=True,
                   help="EEA High Nature Value farmland 2012 (100 m, 1 = HNV)")
    p.add_argument("--keep-landscape", action="store_true",
                   help="landscape designations (IUCN V, biosphere transition areas) "
                   "stay eligible")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--gebco", type=Path, help="GEBCO_2014_2D.nc (PyPSA-Eur's "
                   "retrieve_gebco); the slope is computed from it")
    g.add_argument("--slope", type=Path, help="slope raster [degrees]")
    a = p.parse_args()

    shapes = gpd.read_file(a.country_shapes).set_index("name").to_crs(3035)
    wdpa = read_wdpa(a.wdpa, shapes, landscape=not a.keep_landscape)
    rows = []
    mode, bilinear = rasterio.warp.Resampling.mode, rasterio.warp.Resampling.bilinear
    with (rasterio.open(CORINE) as corine, rasterio.open(NATURA) as natura,
          rasterio.open(a.hnv) as hnv,
          (rasterio.open(a.slope) if a.slope else slope_from_gebco(a.gebco)) as slope):
        cell = abs(corine.res[0] * corine.res[1]) / 1e6
        for ct, geom in shapes.geometry.items():
            data, transform = rasterio.mask.mask(corine, [geom], crop=True, nodata=0)
            lc = data[0]
            # 100 m layers and polygons on the CORINE grid (250 m) by majority / cell
            # centre: "any touching" would also remove the farmland around small sites
            # (DK §3 habitats: 43 % of the farmland instead of the sites' ~25 %)
            natura2000 = on_grid(natura, data, transform, mode) > 0
            protected = natura2000.copy()
            sites = wdpa[wdpa.intersects(geom)]
            if len(sites):
                protected |= rasterio.features.rasterize(
                    ((g, 1) for g in sites.geometry), out_shape=lc.shape,
                    transform=transform, all_touched=False, dtype="uint8") > 0
            high_nature = on_grid(hnv, data, transform, mode, nodata=255) == 1
            flat = on_grid(slope, data, transform, bilinear, dtype="float32") <= MAX_SLOPE

            farm_all = np.isin(lc, FARMLAND_ALL).sum() * cell
            farm_hnv = (np.isin(lc, FARMLAND_ALL) & high_nature).sum() * cell
            farm = (np.isin(lc, FARMLAND) & ~protected & ~high_nature).sum() * cell
            brown = (np.isin(lc, BROWNFIELD_CORRIDORS) & ~protected & flat).sum() * cell
            pypsa_km2 = (np.isin(lc, PYPSA_OTHER) & ~natura2000).sum() * cell

            share, ceiling, rule, source = FARMLAND_RULES.get(
                ct, (DEFAULT_SHARE, None, "default share", ""))
            if ceiling is not None:  # legal ceiling as a share of all farmland
                share = ceiling * 1e3 / FARM_DENSITY / farm_all
            farm_gw = share * farm * FARM_DENSITY / 1e3
            other_gw = brown * OTHER_SHARE * OTHER_DENSITY / 1e3
            rows.append({
                "country": ct, "farmland_all_km2": round(farm_all),
                "farmland_hnv_km2": round(farm_hnv), "farmland_km2": round(farm),
                "farmland_share": round(share, 5), "farmland_gw": round(farm_gw, 2),
                "brownfield_corridors_km2": round(brown),
                "other_land_gw": round(other_gw, 2), "cap_gw": round(farm_gw + other_gw, 2),
                "other_land_pypsa_gw": round(pypsa_km2 * PYPSA_DENSITY / 1e3, 2),
                "rule": rule, "source": source,
            })
    out = pd.DataFrame(rows).sort_values("country")
    out.to_csv(a.out, index=False)
    print(out.drop(columns=["rule", "source"]).to_string(index=False))


if __name__ == "__main__":
    main()
