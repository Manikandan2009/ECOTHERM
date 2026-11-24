# ECOTHERM district heat-risk method

ECOTHERM uses a rule-based, transparent district risk layer. It is not a
validated epidemiological model or a measured heat-risk observation.

## Exposure

Each valid district 1 km LST cell receives a percentile rank within that
district, from 0 to 100. This makes high land-surface temperatures relative
to the observed district distribution.

## Vulnerability

The current vulnerability score combines:

- 40% low vegetation: Sentinel-derived NDVI deficit from a 0.4 reference
- 35% built-up context: Sentinel-derived NDBI rescaled from -1 to 1
- 25% population density: WorldPop 2025 modelled population per 1 km cell,
  capped at that district's 95th percentile

All component scores are clipped to 0–100.

## Heat Risk Index

`risk = Exposure × Vulnerability / 100`

Cells at 75 or above are labelled high-risk. "People exposed" is the sum of
modelled WorldPop population in those high-risk cells. It is not a live headcount
and not a census or health-outcome estimate.

## Urban heat island intensity

District UHI intensity is:

`district mean LST - Tamil Nadu statewide cached grid mean LST`

It is a descriptive surface-temperature contrast, not an air-temperature UHI
measurement or a measured urban/rural difference.

## Missing data

Cells require LST, NDVI, NDBI, and population. Missing components are excluded
from the cell calculation. Coverage gaps are shown as null or unavailable rather
than filled with zero. WorldPop is modelled 2025 data; NDVI/NDBI and LST are
April–June 2026 cached composites.

## Spatial LST estimate model

The AI Predictions page fits a standardized linear regression to cached
1 km district grid cells. Its target is the same summer's Landsat LST, not a
future season. Inputs are Sentinel-2 seasonal NDVI and NDBI. NDBI is a
built-up-index proxy; it is not a measured built-up-area share.

Evaluation uses a deterministic `GroupShuffleSplit` with 25% of districts held
out (`random_state=42`); no cell from a test district is used for training.
The page reports held-out R-squared, mean absolute error in °C, the 90th
percentile absolute residual, sample counts, train/test district IDs, and
normalized absolute standardized coefficients as relative feature importance.

The what-if control adds 0–0.20 NDVI index points while holding NDBI fixed.
It reports a model estimate, not a forecast or causal cooling effect. The
displayed change range is the estimated change plus/minus twice the held-out
90th-percentile absolute error. This is a conservative empirical error
envelope, not a calibrated confidence interval. Only the 2026 summer season is
cached, so temporal forecast validation is unavailable.
