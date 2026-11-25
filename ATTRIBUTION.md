# ECOTHERM cache data attribution

This document records the source information and attribution requirements identified in the ECOTHERM cache manifests and project data-source notes. It applies to the curated `ecotherm-cache.tar.gz` bundle and is not a blanket license for the bundle. The archive combines datasets with different terms.

The cache contains processed and derived data. ECOTHERM may have reprojected, filtered, aggregated, or otherwise transformed source data; those changes do not imply endorsement by the source providers. Preserve the source identifiers and metadata supplied with each dataset.

## Landsat land-surface temperature

- **Collections:** Landsat 8 `LANDSAT/LC08/C02/T1_L2` and Landsat 9 `LANDSAT/LC09/C02/T1_L2`, accessed through Google Earth Engine.
- **Product used:** Collection 2 Level 2 surface-temperature band `ST_B10` from surface-temperature products (`L2SP`).
- **Providers:** U.S. Geological Survey (USGS); dataset catalog hosted by Google Earth Engine.
- **License:** The cache manifest identifies the collections but does not state a license for these products. This document does not assign one. Check the applicable USGS and Google Earth Engine terms before further redistribution.

References: [Landsat 8 Collection 2 Level 2](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2), [Landsat 9 Collection 2 Level 2](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2).

## Sentinel-2 optical indices

- **Collection:** `COPERNICUS/S2_SR_HARMONIZED` Level-2A surface reflectance, accessed through Google Earth Engine.
- **Provider:** European Union / ESA / Copernicus.
- **Bands recorded in the cache manifest:** NDVI B8/B4, NDBI B11/B8, and NDWI B3/B8.
- **License:** The cache manifest identifies the collection but does not state a license for these products. This document does not assign one. Check the applicable Copernicus and Google Earth Engine terms before further redistribution.

Reference: [Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED).

## WorldPop population estimates

The cache contains distinct WorldPop products and years:

- **2025 total-population estimate:** `WorldPop/GP/100m/R2025A/v1/pop`. This is a modelled gridded estimate, not a live count or census observation.
- **2020 age-structure estimate:** `WorldPop/GP/100m/pop_age_sex_cons_unadj`. The cached children and elderly indicators derive from this older product. They must not be described as 2025 or 2026 age estimates.

WorldPop data are identified in the cache metadata as licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Credit WorldPop, identify the relevant product and year, link to [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and indicate that ECOTHERM processed or derived values where applicable.

References: [WorldPop 2025 population collection](https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_R2025A_v1_pop), [WorldPop age/sex collection](https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_pop_age_sex_cons_unadj), [WorldPop data portal](https://www.worldpop.org/).

## Administrative boundaries

The cache manifests identify multiple boundary sources; their licenses remain separate:

- **Constituency boundaries:** DataMeet India community, from the `datameet/maps` source; manifest license **CC BY 4.0**. Credit DataMeet India and link to [datameet/maps](https://github.com/datameet/maps) and [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Tamil Nadu state boundary:** The manifest names DataMeet India community / Election Commission of India, states **CC BY 2.5 India**, and separately records [this geoBoundaries ADM1 source file](https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1.geojson). Preserve all recorded source references. Because the manifest does not clearly map the license statement to every source entry, confirm license coverage before redistribution. References: [datameet/maps](https://github.com/datameet/maps), [CC BY 2.5 India](https://creativecommons.org/licenses/by/2.5/in/).
- **District boundaries:** Pathways Data Pvt. Ltd. / Local Government Directory (`lgdirectory.gov.in`); manifest license **Open Data Commons Open Database License 1.0 (ODbL 1.0)**. Credit the recorded source and link to [LGDirectory](https://lgdirectory.gov.in/) and the [ODbL 1.0 text](https://opendatacommons.org/licenses/odbl/1-0/).

## OpenStreetMap

Where the cache uses OpenStreetMap boundary, place-reference, or processed feature-summary data, credit **© OpenStreetMap contributors** and link to [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright). OpenStreetMap data are made available under **ODbL 1.0**.

Follow ODbL attribution requirements and assess its share-alike obligations for any publicly used or redistributed derivative database. Include the required credit and license link with the relevant display or data distribution. The raw Geofabrik Southern Zone PBF extract is not included in this curated cache archive.

## Open-Meteo weather

The weather cache records Open-Meteo historical API data and the ERA5-Land model. Open-Meteo API data are offered under **CC BY 4.0**, subject to the provider's current [license](https://open-meteo.com/en/licence) and [terms of use](https://open-meteo.com/en/terms).

Provide a visible attribution link wherever the weather data are displayed:

> [Weather data by Open-Meteo.com](https://open-meteo.com/)

The Open-Meteo Free API is restricted to non-commercial use and is subject to its published request limits and other terms. The project owner confirmed on 2026-11-25 that ECOTHERM is an academic/educational submission without commercial use. Reassess eligibility if that use changes; this confirmation does not replace checking the provider's current terms.

## Attribution and redistribution notes

- Do not apply a single license to the complete archive. Keep the individual source credits and licenses above.
- Do not claim a license for Landsat or Sentinel-2 products based solely on this document; the cache manifests did not specify one.
- Preserve the archive's dataset manifests and provenance when extracting or redistributing data.
- Attribution in this file or in release notes does not replace provider-required attribution at the point of display, nor does it determine whether a particular derived database is subject to share-alike terms.
- Review the applicable source terms before each public redistribution. This document summarizes recorded metadata and is not legal advice.
