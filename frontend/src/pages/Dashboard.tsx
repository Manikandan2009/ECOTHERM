import L from 'leaflet'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { GeoJSON, MapContainer, Pane, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import type { FeatureCollection, Geometry, Position } from 'geojson'
import Brand from '../components/Brand'

const sections = [
  { id: 'overview', label: 'Overview', icon: 'grid' },
  { id: 'heat-map', label: 'Heat Map Explorer', icon: 'map' },
  { id: 'satellite', label: 'Satellite Analysis', icon: 'satellite' },
  { id: 'predictions', label: 'AI Predictions', icon: 'spark' },
  { id: 'analytics', label: 'Environmental Analytics', icon: 'chart' },
  { id: 'priorities', label: 'Priorities & Budget', icon: 'target' },
  { id: 'reports', label: 'Reports & Methods', icon: 'document' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
]
const baseRegions = [
  { id: 'tamil_nadu', name: 'Tamil Nadu' },
]

type DistrictRegion = { district_id: string; district_name: string }
type DistrictCollection = {
  district_count: number
  boundary_year: string
  source: string
  license: string
  selection_rule: string
  districts: DistrictRegion[]
  geojson: FeatureCollection
}

type ConstituencyCollection = {
  constituency_count: number
  state_constituency_count: number
  district_id: string | null
  source: string
  source_reference: string
  license: string
  delimitation_year: string
  district_assignment: string
  district_overlap_below_80_percent: Array<{
    ac_number: number
    constituency_name: string
    district_name: string
    overlap_percent: number
  }>
  districts: Array<{
    district_id: string
    district_name: string
    constituency_count: number
  }>
  constituencies: Array<{
    constituency_id: string
    constituency_name: string
    ac_number: number
    district_id: string
    district_name: string
  }>
  geojson: FeatureCollection
}

type LiveWeather = {
  district_id?: string | null
  district_name?: string | null
  constituency_id?: string | null
  constituency_name?: string | null
  temperature_2m_c: number | null
  relative_humidity_2m_percent: number | null
  wind_speed_10m_kmh: number | null
  status: 'live' | 'stale' | 'unavailable'
  updated_at_utc: string | null
  provider?: string
  error: string | null
}

type InspectMetric = {
  value: number | null
  status: 'available' | 'unavailable'
  reason: string | null
}

type MapInspection = {
  latitude: number
  longitude: number
  study_area_status: 'inside' | 'outside'
  district_id: string | null
  district_name: string | null
  constituency_id: string | null
  constituency_name: string | null
  cell_id: string | null
  cell_resolution_m: number | null
  cell_outline: Geometry | null
  lst_c: InspectMetric
  lst_source: string
  lst_composite_start: string | null
  lst_composite_end: string | null
  lst_valid_observations: InspectMetric
  lst_observation_count_note: string | null
  constituency_mean_lst_c: InspectMetric
  constituency_mean_resolution_m: number | null
  difference_from_constituency_mean_c: InspectMetric
  population_estimated_2025: InspectMetric
  air_temperature: {
    temperature_2m_c: number | null
    status: 'live' | 'stale' | 'unavailable'
    updated_at_utc: string | null
    spatial_support: string
    reason: string | null
  }
}

type MapPoint = { latitude: number; longitude: number }


type DashboardSummary = {
  region_id: string
  season_year: number
  data_status: string
  grid_resolution_m: number | null
  grid_cell_count: number | null
  lst_valid_cell_count: number | null
  lst_coverage_percent: number | null
  lst_mean_c: number | null
  lst_max_c: number | null
  estimated_population_2025: number | null
  population_valid_cell_count: number | null
  population_coverage_percent: number | null
  weather_mean_air_temperature_c: number | null
  weather_max_air_temperature_c: number | null
  weather_model: string | null
  weather_data_status: string | null
  weather_start_date: string | null
  weather_end_date: string | null
  urban_heat_island_intensity_c: number | null
  people_exposed_high_heat: number | null
  high_risk_cell_count: number | null
  osm_feature_counts: Record<string, number> | null
  osm_feature_total: number | null
  osm_processed_at_utc: string | null
  unavailable_metrics: string[]
}

const API_BASE = 'http://127.0.0.1:8000'

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(value)) return 'Unavailable'
  return new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: digits,
  }).format(value)
}

function formatUpdatedTime(value: string | null | undefined) {
  if (!value) return null
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return null
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function formatUpdatedDateTime(value: string | null | undefined) {
  if (!value) return null
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return null
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

type SatelliteMetric = {
  mean: number | null
  valid_cell_count: number | null
  coverage_percent: number | null
}

type SatelliteAnalysisSummary = {
  region_id: string
  season_year: number
  data_status: 'available' | 'partial' | 'unavailable'
  grid_cell_count: number | null
  grid_resolution_m: number | null
  lst: SatelliteMetric
  ndvi: SatelliteMetric
  ndbi: SatelliteMetric
  ndwi: SatelliteMetric
  composite_start: string | null
  composite_end: string | null
  lst_source: string
  optical_source: string
}

type SatelliteScatterSummary = {
  constituency_id: string
  season_year: number
  data_status: 'available' | 'unavailable'
  resolution_m: number | null
  pair_count: number
  correlation_pearson: number | null
  composite_start: string | null
  composite_end: string | null
  ndvi_source: string
  lst_source: string
  reason: string | null
  points: Array<{ ndvi: number; lst_c: number }>
}

type AnalyticsRegion = {
  region_id: string
  region_name: string
  region_type: 'district' | 'constituency'
  district_id: string
  district_name: string
  data_status: 'available' | 'partial' | 'unavailable'
  cell_count: number | null
  lst_mean_c: number | null
  lst_coverage_percent: number | null
  population_estimated_2025: number | null
  ndvi_mean: number | null
  resolution_m: number | null
  composite_start: string | null
  composite_end: string | null
  lst_reason: string | null
  population_reason: string | null
  ndvi_reason: string | null
  air_temperature_mean_c: number | null
  air_temperature_model: string | null
  air_temperature_start_date: string | null
  air_temperature_end_date: string | null
  air_temperature_reason: string | null
}

type AnalyticsResponse = {
  season_year: number
  data_status: 'available' | 'partial' | 'unavailable'
  lst_source: string
  population_source: string
  ndvi_source: string
  air_temperature_source: string
  regions: AnalyticsRegion[]
}

type ConstituencyPriority = {
  constituency_id: string
  constituency_name: string
  district_id: string
  district_name: string
  data_status: 'available' | 'unavailable'
  lst_mean_c: number | null
  population_estimated_2025: number | null
  ndvi_mean: number | null
  heat_exposure_percentile: number | null
  population_weight: number | null
  low_green_score: number | null
  priority_score: number | null
  resolution_m: number | null
  composite_start: string | null
  composite_end: string | null
  lst_reason: string | null
  population_reason: string | null
  ndvi_reason: string | null
  priority_reason: string | null
}

type PrioritiesResponse = {
  season_year: number
  data_status: 'available' | 'partial' | 'unavailable'
  formula: string
  heat_exposure_method: string
  population_method: string
  low_green_method: string
  lst_source: string
  population_source: string
  ndvi_source: string
  priorities: ConstituencyPriority[]
}

type InterventionInput = {
  type: string
  cost: string
}

type DashboardSettings = {
  version: 1
  basemapPreference: 'street' | 'satellite'
  temperatureUnit: 'C' | 'F'
  defaultRegion: string
  resolutionPreferenceM: 100 | 1000
}

const dashboardSettingsKey = 'ecotherm.dashboard.settings.v1'
const defaultDashboardSettings: DashboardSettings = {
  version: 1,
  basemapPreference: 'street',
  temperatureUnit: 'C',
  defaultRegion: 'tamil_nadu',
  resolutionPreferenceM: 1000,
}

function isDashboardSettings(value: unknown): value is DashboardSettings {
  if (typeof value !== 'object' || value === null) return false
  const settings = value as Partial<DashboardSettings>
  return settings.version === 1
    && (settings.basemapPreference === 'street' || settings.basemapPreference === 'satellite')
    && (settings.temperatureUnit === 'C' || settings.temperatureUnit === 'F')
    && typeof settings.defaultRegion === 'string'
    && (settings.resolutionPreferenceM === 100 || settings.resolutionPreferenceM === 1000)
}

function loadDashboardSettings(): { settings: DashboardSettings; error: string | null } {
  let serialized: string | null
  try {
    serialized = window.localStorage.getItem(dashboardSettingsKey)
  } catch (error: unknown) {
    const reason = error instanceof Error ? error.message : 'Browser storage is unavailable.'
    return {
      settings: defaultDashboardSettings,
      error: `Could not read saved dashboard settings: ${reason}`,
    }
  }
  if (serialized === null) return { settings: defaultDashboardSettings, error: null }
  try {
    const parsed: unknown = JSON.parse(serialized)
    if (isDashboardSettings(parsed)) return { settings: parsed, error: null }
    return {
      settings: defaultDashboardSettings,
      error: 'Saved dashboard settings have an unsupported format; defaults are active.',
    }
  } catch (error: unknown) {
    const reason = error instanceof Error ? error.message : 'Invalid saved settings.'
    return {
      settings: defaultDashboardSettings,
      error: `Could not parse saved dashboard settings: ${reason}`,
    }
  }
}

function convertTemperature(value: number, unit: 'C' | 'F') {
  return unit === 'F' ? value * 9 / 5 + 32 : value
}

function formatTemperature(value: number | null | undefined, unit: 'C' | 'F', digits = 1) {
  if (value == null || !Number.isFinite(value)) return 'Unavailable'
  return `${formatNumber(convertTemperature(value, unit), digits)} °${unit}`
}

function formatTemperatureDelta(value: number | null | undefined, unit: 'C' | 'F', digits = 1) {
  if (value == null || !Number.isFinite(value)) return 'Unavailable'
  const converted = unit === 'F' ? value * 9 / 5 : value
  return `${formatNumber(converted, digits)} °${unit}`
}

type AnalyticsSortKey =
  | 'region_name'
  | 'region_type'
  | 'lst_mean_c'
  | 'population_estimated_2025'
  | 'ndvi_mean'
  | 'lst_coverage_percent'

type PredictionStatus = {
  region_id: string
  status: 'unavailable'
  model_status: 'no_qualified_model'
  prediction_available: boolean
  available_season_years: number[]
  region_season_years: number[]
  latest_region_cell_count: number | null
  latest_region_lst_valid_cell_count: number | null
  target_status: 'not_defined'
  baseline_status: 'not_evaluated'
  spatial_validation_status: 'not_run'
  temporal_validation_status: 'not_run'
  reason: string
}

type PredictionEstimate = {
  region_id: string
  season_year: number
  model_status: 'available' | 'unavailable'
  output_label: 'estimate'
  forecast_label: 'not_a_forecast'
  model_name: string
  target: string
  target_source: string
  validation_method: string
  training_districts: string[]
  test_districts: string[]
  training_cell_count: number
  test_cell_count: number
  training_district_count: number
  test_district_count: number
  r_squared: number | null
  mean_absolute_error_c: number | null
  p90_absolute_error_c: number | null
  evaluation_resolution_m: number | null
  evaluation_start_date: string | null
  evaluation_end_date: string | null
  inputs: Array<{
    feature: 'ndvi' | 'ndbi'
    label: string
    value: number | null
    source: string
    resolution_m: number | null
    composite_start: string | null
    composite_end: string | null
    reason: string | null
  }>
  feature_importance: Array<{
    feature: 'ndvi' | 'ndbi'
    label: string
    standardized_coefficient: number | null
    relative_importance_percent: number | null
    source: string
    resolution_m: number | null
  }>
  model_intercept_c: number | null
  ndvi_coefficient_c_per_index: number | null
  ndbi_coefficient_c_per_index: number | null
  scenario_ndvi_mean: number | null
  scenario_ndbi_mean: number | null
  scenario_baseline_lst_c: number | null
  scenario_error_bound_c: number | null
  scenario_reason: string | null
  reason: string | null
}

type SatelliteLayer = 'lst' | 'ndvi' | 'ndbi' | 'ndwi'
const satelliteLayers: Array<{ id: SatelliteLayer; label: string }> = [
  { id: 'lst', label: 'LST' },
  { id: 'ndvi', label: 'NDVI' },
  { id: 'ndbi', label: 'NDBI' },
  { id: 'ndwi', label: 'NDWI' },
]

function FitDistrictBounds({
  geojson,
  constituencyGeojson,
  region,
  constituencyId,
  active,
}: {
  geojson: FeatureCollection | null
  constituencyGeojson: FeatureCollection | null
  region: string
  constituencyId: string | null
  active: string
}) {
  const map = useMap()
  useEffect(() => {
    map.invalidateSize()
    if (!geojson) return
    if (region === 'tamil_nadu') {
      map.fitBounds([[8.0, 76.2], [13.7, 80.5]], { padding: [10, 10] })
      return
    }
    const districtId = region.startsWith('district_') ? region.slice(9) : null
    if (!districtId) return
    if (constituencyId && constituencyGeojson) {
      const selectedConstituency = constituencyGeojson.features.find(
        (feature) => feature.properties?.constituency_id === constituencyId,
      )
      if (selectedConstituency) {
        const bounds = geometryBounds(selectedConstituency.geometry)
        if (bounds) {
          map.fitBounds(bounds, { padding: [18, 18], maxZoom: 11 })
          return
        }
      }
    }
    const selected = geojson.features.find(
      (feature) => feature.properties?.district_id === districtId,
    )
    if (!selected) return
    const bounds = geometryBounds(selected.geometry)
    if (bounds) map.fitBounds(bounds, { padding: [18, 18], maxZoom: 10 })
  }, [active, constituencyGeojson, constituencyId, geojson, map, region])
  return null
}

function geometryBounds(geometry: unknown): [[number, number], [number, number]] | null {
  const coordinates: number[][] = []
  const collect = (value: unknown) => {
    if (!Array.isArray(value)) return
    if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
      coordinates.push([value[0], value[1]])
      return
    }
    value.forEach(collect)
  }
  if (geometry && typeof geometry === 'object' && 'coordinates' in geometry) {
    collect(geometry.coordinates)
  }
  if (!coordinates.length) return null
  const latitudes = coordinates.map((coordinate) => coordinate[1])
  const longitudes = coordinates.map((coordinate) => coordinate[0])
  return [
    [Math.min(...latitudes), Math.min(...longitudes)],
    [Math.max(...latitudes), Math.max(...longitudes)],
  ]
}

function inspectionMetricValue(
  metric: InspectMetric,
  unit: string,
  digits = 1,
  temperatureUnit?: 'C' | 'F',
) {
  return metric.status === 'available'
    && metric.value !== null
    && Number.isFinite(metric.value)
    ? `${formatNumber(temperatureUnit ? convertTemperature(metric.value, temperatureUnit) : metric.value, digits)}${unit || (temperatureUnit ? ` °${temperatureUnit}` : '')}`
    : null
}

function createInspectionPopupContent(
  inspection: MapInspection | null,
  loading: boolean,
  error: string | null,
  temperatureUnit: 'C' | 'F',
) {
  const container = document.createElement('div')
  container.className = 'inspect-popup-content'
  container.setAttribute('role', loading ? 'status' : 'region')

  const addLine = (
    parent: HTMLElement,
    label: string,
    value: string | null,
    reason: string | null = null,
  ) => {
    const line = document.createElement('p')
    if (value === null) line.className = 'is-missing'
    const name = document.createElement('span')
    name.className = 'inspect-row-label'
    name.textContent = `${label}:`
    const detail = document.createElement('span')
    detail.className = 'inspect-row-value'
    detail.textContent = value ?? 'Unavailable'
    line.append(name, detail)
    if (value === null) {
      const reasonDetail = document.createElement('small')
      reasonDetail.className = 'inspect-row-reason'
      reasonDetail.textContent = `Unavailable: ${reason ?? 'No cached value is available.'}`
      line.appendChild(reasonDetail)
    }
    parent.appendChild(line)
  }

  const heading = document.createElement('strong')
  if (loading) {
    heading.textContent = 'Inspecting…'
    container.appendChild(heading)
    return container
  }
  if (error) {
    heading.textContent = 'Inspection unavailable'
    container.append(heading, document.createTextNode(error))
    return container
  }
  if (!inspection) return container
  if (inspection.study_area_status === 'outside') {
    heading.textContent = 'Outside study area'
    container.appendChild(heading)
    return container
  }

  heading.textContent = inspection.constituency_name ?? 'Constituency'
  container.appendChild(heading)
  const district = document.createElement('p')
  district.className = 'inspect-popup-district'
  district.textContent = `District: ${inspection.district_name ?? ''}`
  container.appendChild(district)

  const resolution = inspection.cell_resolution_m === 1000
    ? '1 km'
    : inspection.cell_resolution_m
      ? `${inspection.cell_resolution_m} m`
      : null
  const lstValue = inspectionMetricValue(inspection.lst_c, '', 1, temperatureUnit)
  const populationValue = inspectionMetricValue(
    inspection.population_estimated_2025,
    '',
    0,
  )
  addLine(
    container,
    'Surface temp (LST)',
    lstValue && resolution ? `${lstValue} (${resolution})` : lstValue,
    inspection.lst_c.reason,
  )
  const difference = inspection.difference_from_constituency_mean_c
  const differenceValue = difference.status === 'available'
    && difference.value !== null
    && Number.isFinite(difference.value)
    ? `${difference.value > 0 ? '+' : ''}${formatTemperatureDelta(difference.value, temperatureUnit)}`
    : null
  addLine(
    container,
    'vs constituency avg',
    differenceValue,
    difference.reason,
  )
  addLine(
    container,
    'Population (cell)',
    populationValue && resolution
      ? `${populationValue} (${resolution} cell)`
      : populationValue,
    inspection.population_estimated_2025.reason,
  )

  const weather = inspection.air_temperature
  let weatherValue: string | null = null
  if (weather.temperature_2m_c !== null && Number.isFinite(weather.temperature_2m_c)) {
    const updatedAt = weather.updated_at_utc
      ? new Date(weather.updated_at_utc)
      : null
    const updated = updatedAt && Number.isFinite(updatedAt.getTime())
      ? new Intl.DateTimeFormat('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        }).format(updatedAt)
      : null
    weatherValue = `${formatTemperature(weather.temperature_2m_c, temperatureUnit)} · ${weather.status}${updated ? ` ${updated}` : ''}`
  }
  addLine(
    container,
    'Air temp (regional)',
    weatherValue,
    weather.reason,
  )

  const details = document.createElement('details')
  details.className = 'inspect-popup-details'
  const summary = document.createElement('summary')
  summary.textContent = 'Details'
  details.appendChild(summary)
  const detailRows = document.createElement('div')
  detailRows.className = 'inspect-popup-detail-rows'
  addLine(
    detailRows,
    'Valid Landsat observations',
    inspectionMetricValue(inspection.lst_valid_observations, '', 1),
    inspection.lst_valid_observations.reason,
  )
  if (inspection.lst_composite_start && inspection.lst_composite_end) {
    addLine(
      detailRows,
      'Composite dates',
      `${inspection.lst_composite_start} to ${inspection.lst_composite_end}`,
    )
  }
  addLine(detailRows, 'LST source', inspection.lst_source)
  if (inspection.lst_observation_count_note) {
    addLine(detailRows, 'Count note', inspection.lst_observation_count_note)
  }
  details.appendChild(detailRows)
  container.appendChild(details)
  return container
}

function MapClickInspector({
  onInspect,
  point,
  inspection,
  loading,
  error,
  temperatureUnit,
}: {
  onInspect: (latitude: number, longitude: number) => void
  point: MapPoint | null
  inspection: MapInspection | null
  loading: boolean
  error: string | null
  temperatureUnit: 'C' | 'F'
}) {
  const map = useMapEvents({
    click(event) {
      onInspect(event.latlng.lat, event.latlng.lng)
    },
  })
  const popup = useMemo(
    () => L.popup({ maxWidth: 260, className: 'inspect-popup' }),
    [],
  )

  useEffect(() => {
    if (!point) return
    popup
      .setLatLng([point.latitude, point.longitude])
      .setContent(createInspectionPopupContent(inspection, loading, error, temperatureUnit))
    map.closePopup()
    popup.openOn(map)
  }, [error, inspection, loading, map, point, popup, temperatureUnit])

  useEffect(() => () => {
    map.closePopup(popup)
  }, [map, popup])

  return null
}

function Icon({ name }: { name: string }) {
  if (name === 'map') return <span aria-hidden="true">⌖</span>
  if (name === 'satellite') return <span aria-hidden="true">◉</span>
  if (name === 'spark') return <span aria-hidden="true">✦</span>
  if (name === 'chart') return <span aria-hidden="true">⌁</span>
  if (name === 'target') return <span aria-hidden="true">◎</span>
  if (name === 'document') return <span aria-hidden="true">▤</span>
  if (name === 'settings') return <span aria-hidden="true">⚙</span>
  return <span aria-hidden="true">▦</span>
}

function AnalyticsValue({
  label,
  value,
  metadata,
  reason,
}: {
  label: string
  value: string | null
  metadata: string
  reason: string | null
}) {
  return (
    <div className="analytics-value">
      <dt>{label}</dt>
      <dd>{value ?? 'Unavailable'}</dd>
      <small>{value === null ? `Unavailable: ${reason ?? 'value is unavailable'} · ${metadata}` : metadata}</small>
    </div>
  )
}

function geometryRings(geometry: Geometry | null): Position[][] {
  if (!geometry) return []
  if (geometry.type === 'Polygon') return geometry.coordinates
  if (geometry.type === 'MultiPolygon') return geometry.coordinates.flat()
  if (geometry.type === 'GeometryCollection') {
    return geometry.geometries.flatMap(geometryRings)
  }
  return []
}

function ReportMapSnapshot({ features }: { features: FeatureCollection['features'] }) {
  const rings = features.flatMap((feature) => geometryRings(feature.geometry))
  const positions = rings.flat()
  if (positions.length === 0) {
    return (
      <div className="report-map-empty">
        Unavailable: cached boundary geometry for this selection has not loaded.
      </div>
    )
  }
  const geographicBounds = positions.reduce(
    (bounds, position) => ({
      minLatitude: Math.min(bounds.minLatitude, position[1]),
      maxLatitude: Math.max(bounds.maxLatitude, position[1]),
    }),
    { minLatitude: Infinity, maxLatitude: -Infinity },
  )
  const longitudeFactor = Math.cos(
    ((geographicBounds.minLatitude + geographicBounds.maxLatitude) / 2) * Math.PI / 180,
  )
  const projected = positions.map((position) => [position[0] * longitudeFactor, position[1]])
  const projectedBounds = projected.reduce(
    (bounds, [x, y]) => ({
      minX: Math.min(bounds.minX, x),
      maxX: Math.max(bounds.maxX, x),
      minY: Math.min(bounds.minY, y),
      maxY: Math.max(bounds.maxY, y),
    }),
    { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity },
  )
  const { minX, maxX, minY, maxY } = projectedBounds
  const scale = Math.min(600 / (maxX - minX || 1), 320 / (maxY - minY || 1))
  const offsetX = (640 - (maxX - minX) * scale) / 2
  const offsetY = (360 - (maxY - minY) * scale) / 2

  return (
    <svg
      className="report-map-snapshot"
      viewBox="0 0 640 360"
      role="img"
      aria-label="Cached boundary-only map snapshot"
    >
      <rect width="640" height="360" fill="#10291f" />
      {rings.map((ring, index) => (
        <polygon
          key={index}
          points={ring.map(([longitude, latitude]) => {
            const x = longitude * longitudeFactor
            return `${offsetX + (x - minX) * scale},${360 - offsetY - (latitude - minY) * scale}`
          }).join(' ')}
          fill="rgba(111, 207, 151, .16)"
          stroke="#8bd3a0"
          strokeWidth="1.2"
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  )
}

export default function Dashboard() {
  const [initialSettings] = useState(loadDashboardSettings)
  const [dashboardSettings, setDashboardSettings] = useState(initialSettings.settings)
  const [settingsError, setSettingsError] = useState<string | null>(initialSettings.error)
  const [active, setActive] = useState('overview')
  const [region, setRegion] = useState(dashboardSettings.defaultRegion)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [satelliteSummary, setSatelliteSummary] = useState<SatelliteAnalysisSummary | null>(null)
  const [satelliteSummaryLoading, setSatelliteSummaryLoading] = useState(true)
  const [satelliteSummaryError, setSatelliteSummaryError] = useState<string | null>(null)
  const [predictionStatus, setPredictionStatus] = useState<PredictionStatus | null>(null)
  const [predictionStatusLoading, setPredictionStatusLoading] = useState(true)
  const [predictionStatusError, setPredictionStatusError] = useState<string | null>(null)
  const [predictionEstimate, setPredictionEstimate] = useState<PredictionEstimate | null>(null)
  const [predictionEstimateLoading, setPredictionEstimateLoading] = useState(false)
  const [predictionEstimateError, setPredictionEstimateError] = useState<string | null>(null)
  const [ndviUpliftPercent, setNdviUpliftPercent] = useState(0)
  const [districtCollection, setDistrictCollection] = useState<DistrictCollection | null>(null)
  const [districtError, setDistrictError] = useState<string | null>(null)
  const [constituencyId, setConstituencyId] = useState<string | null>(null)
  const [constituencyCollection, setConstituencyCollection] = useState<ConstituencyCollection | null>(null)
  const [constituencyError, setConstituencyError] = useState<string | null>(null)
  const [liveWeather, setLiveWeather] = useState<LiveWeather | null>(null)
  const [weatherRefreshStatus, setWeatherRefreshStatus] = useState<string | null>(null)
  const [weatherRefreshToken, setWeatherRefreshToken] = useState(0)
  const [inspectionPoint, setInspectionPoint] = useState<MapPoint | null>(null)
  const [inspection, setInspection] = useState<MapInspection | null>(null)
  const [inspectionLoading, setInspectionLoading] = useState(false)
  const [inspectionError, setInspectionError] = useState<string | null>(null)
  const [baseLayer, setBaseLayer] = useState<'map' | 'satellite'>('map')
  const [labelsVisible, setLabelsVisible] = useState(false)
  const [lstOverlayVisible, setLstOverlayVisible] = useState(false)
  const [lstOpacity, setLstOpacity] = useState(0.65)
  const [satelliteLayer, setSatelliteLayer] = useState<SatelliteLayer>('ndvi')
  const [satelliteOverlayVisible, setSatelliteOverlayVisible] = useState(false)
  const [satelliteSwipeEnabled, setSatelliteSwipeEnabled] = useState(false)
  const [satelliteSwipePosition, setSatelliteSwipePosition] = useState(50)
  const [scatterSummary, setScatterSummary] = useState<SatelliteScatterSummary | null>(null)
  const [scatterLoading, setScatterLoading] = useState(false)
  const [scatterError, setScatterError] = useState<string | null>(null)
  const [analyticsData, setAnalyticsData] = useState<AnalyticsResponse | null>(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [analyticsError, setAnalyticsError] = useState<string | null>(null)
  const [prioritiesData, setPrioritiesData] = useState<PrioritiesResponse | null>(null)
  const [prioritiesLoading, setPrioritiesLoading] = useState(false)
  const [prioritiesError, setPrioritiesError] = useState<string | null>(null)
  const [budgetAmount, setBudgetAmount] = useState('')
  const [priorityTopCount, setPriorityTopCount] = useState('20')
  const [interventionInputs, setInterventionInputs] = useState<
    Record<string, InterventionInput>
  >({})
  const [analyticsSort, setAnalyticsSort] = useState<{
    key: AnalyticsSortKey
    direction: 'asc' | 'desc'
  }>({ key: 'region_name', direction: 'asc' })
  const [compareDistrictIds, setCompareDistrictIds] = useState<[string, string]>([
    'chennai',
    'coimbatore',
  ])
  const [trendDistrictId, setTrendDistrictId] = useState('chennai')
  const inspectionRequestId = useRef(0)

  const updateDashboardSettings = (updates: Partial<DashboardSettings>) => {
    const next = { ...dashboardSettings, ...updates }
    setDashboardSettings(next)
    try {
      window.localStorage.setItem(dashboardSettingsKey, JSON.stringify(next))
      setSettingsError(null)
    } catch (error: unknown) {
      const reason = error instanceof Error ? error.message : 'Browser storage is unavailable.'
      setSettingsError(`Could not save dashboard settings: ${reason}`)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${API_BASE}/api/v1/districts`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`District boundary request failed (${response.status})`)
        return (await response.json()) as DistrictCollection
      })
      .then((data) => setDistrictCollection(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setDistrictError(error instanceof Error ? error.message : 'District boundaries unavailable.')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
      if (!districtCollection) return
      const validDefault = dashboardSettings.defaultRegion === 'tamil_nadu'
        || districtCollection.districts.some(
          (district) => `district_${district.district_id}` === dashboardSettings.defaultRegion,
        )
      if (!validDefault) {
        setRegion('tamil_nadu')
        setSettingsError(
          `Saved default region "${dashboardSettings.defaultRegion}" is not present in the cached district list.`,
        )
        return
      }
      setRegion(dashboardSettings.defaultRegion)
  }, [districtCollection, dashboardSettings.defaultRegion])

  useEffect(() => {
    if (!region.startsWith('district_')) {
      setConstituencyCollection(null)
      setConstituencyError(null)
      return
    }
    const districtId = region.slice(9)
    const controller = new AbortController()
    setConstituencyCollection(null)
    setConstituencyError(null)
    fetch(
      `${API_BASE}/api/v1/constituencies?district_id=${encodeURIComponent(districtId)}`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`Constituency boundary request failed (${response.status})`)
        return (await response.json()) as ConstituencyCollection
      })
      .then((data) => setConstituencyCollection(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setConstituencyError(error instanceof Error ? error.message : 'Constituency data unavailable.')
      })
    return () => controller.abort()
  }, [region])

  useEffect(() => {
    if (!region.startsWith('district_') && !constituencyId) {
      setLiveWeather(null)
      setWeatherRefreshStatus(null)
      return
    }
    const districtId = region.startsWith('district_') ? region.slice(9) : null
    const controller = new AbortController()
    let disposed = false

    const refresh = async () => {
      try {
        const query = constituencyId
          ? `constituency_id=${encodeURIComponent(constituencyId)}`
          : `district_id=${encodeURIComponent(districtId ?? '')}`
        const response = await fetch(
          `${API_BASE}/api/v1/weather/live?${query}`,
          { signal: controller.signal },
        )
        if (disposed) return
        if (!response.ok) {
          const error = `Live weather request failed (${response.status}).`
          setLiveWeather({
            district_id: districtId,
            constituency_id: constituencyId,
            temperature_2m_c: null,
            relative_humidity_2m_percent: null,
            wind_speed_10m_kmh: null,
            status: 'unavailable',
            updated_at_utc: null,
            error,
          })
          setWeatherRefreshStatus(error)
          return
        }
        const data = await response.json() as LiveWeather
        if (disposed) return
        setLiveWeather(data)
        const updated = formatUpdatedTime(data.updated_at_utc)
        setWeatherRefreshStatus(
          data.status === 'unavailable'
            ? data.error ?? 'Live weather is unavailable.'
            : `${data.status === 'live' ? 'Live' : 'Stale'}${updated ? ` · Updated ${updated}` : ' · Update time unavailable'}`,
        )
      } catch (error: unknown) {
        if (disposed || (error instanceof DOMException && error.name === 'AbortError')) return
        const message = error instanceof Error ? error.message : 'Unknown request error.'
        const detail = `Live weather refresh failed: ${message}`
        setLiveWeather({
          district_id: districtId,
          constituency_id: constituencyId,
          temperature_2m_c: null,
          relative_humidity_2m_percent: null,
          wind_speed_10m_kmh: null,
          status: 'unavailable',
          updated_at_utc: null,
          error: detail,
        })
        setWeatherRefreshStatus(detail)
      }
    }

    void refresh()
    const interval = window.setInterval(() => void refresh(), 5 * 60 * 1000)
    return () => {
      disposed = true
      controller.abort()
      window.clearInterval(interval)
    }
  }, [constituencyId, region, weatherRefreshToken])

  const regions = [
    ...baseRegions,
    ...(districtCollection?.districts.map((district) => ({
      id: `district_${district.district_id}`,
      name: district.district_name,
    })) ?? []),
  ]
  const selectedRegion = regions.find((item) => item.id === region) ?? regions[0]
  const selectedConstituency = constituencyCollection?.constituencies.find(
    (item) => item.constituency_id === constituencyId,
  )
  const selectedLiveWeather = (
    region.startsWith('district_') || constituencyId !== null
  )
    ? liveWeather
    : null
  const liveWeatherTime = formatUpdatedTime(
    selectedLiveWeather?.updated_at_utc,
  )
  const weatherReadiness = selectedLiveWeather
    ? selectedLiveWeather.temperature_2m_c === null
      ? 'Unavailable'
      : `${selectedLiveWeather.status === 'live' ? 'Live' : selectedLiveWeather.status === 'stale' ? 'Stale' : 'Unavailable'}${liveWeatherTime ? ` · Updated ${liveWeatherTime}` : ''}`
    : summary?.weather_model
      ? `Cached · ${summary.weather_model === 'era5_land' ? 'ERA5-Land' : summary.weather_model}`
      : 'Missing'
  const weatherSourceAvailable = selectedLiveWeather
    ? selectedLiveWeather.temperature_2m_c !== null
    : summary?.weather_model != null
  const osmCategoryLabels: Record<string, string> = {
    buildings: 'Buildings',
    roads: 'Roads',
    hospitals: 'Health sites',
    parks: 'Parks',
    water_features: 'Water features',
    bus_stops: 'Bus stops',
    markets: 'Markets',
  }
  const osmFeatureDetails = summary?.osm_feature_counts
    ? Object.entries(osmCategoryLabels)
        .map(([key, label]) => `${label} ${formatNumber(summary.osm_feature_counts?.[key], 0)}`)
        .join(' · ')
    : ''
  const osmSourceAvailable = region === 'tamil_nadu' && summary?.osm_feature_total != null
  const summaryRegionId = constituencyId
    ? `constituency_${constituencyId}`
    : region
  const reportDistrictId = region.startsWith('district_') ? region.slice(9) : null
  const reportDistrict = districtCollection?.districts.find(
    (item) => item.district_id === reportDistrictId,
  )
  const reportConstituency = constituencyCollection?.constituencies.find(
    (item) => item.constituency_id === constituencyId,
  )
  const reportTitle = reportConstituency?.constituency_name
    ?? reportDistrict?.district_name
    ?? 'Tamil Nadu'
  const reportAnalyticsRegion = analyticsData?.regions.find(
    (item) => item.region_id === (constituencyId ?? reportDistrictId)
      && item.region_type === (constituencyId ? 'constituency' : 'district'),
  )
  const reportGridResolution = reportAnalyticsRegion?.resolution_m
    ?? satelliteSummary?.grid_resolution_m
  const reportCompositeStart = reportAnalyticsRegion?.composite_start
    ?? satelliteSummary?.composite_start
  const reportCompositeEnd = reportAnalyticsRegion?.composite_end
    ?? satelliteSummary?.composite_end
  const reportLstMean = reportAnalyticsRegion?.lst_mean_c
    ?? summary?.lst_mean_c
    ?? satelliteSummary?.lst.mean
    ?? null
  const reportPopulation = reportAnalyticsRegion?.population_estimated_2025
    ?? summary?.estimated_population_2025
    ?? null
  const reportNdvi = reportAnalyticsRegion?.ndvi_mean
    ?? satelliteSummary?.ndvi.mean
    ?? null
  const reportWeather = reportAnalyticsRegion?.air_temperature_mean_c
    ?? summary?.weather_mean_air_temperature_c
    ?? null
  const reportFeatures = constituencyId
    ? (constituencyCollection?.geojson.features ?? []).filter(
        (feature) => feature.properties?.constituency_id === constituencyId,
      )
    : reportDistrictId
      ? (districtCollection?.geojson.features ?? []).filter(
          (feature) => feature.properties?.district_id === reportDistrictId,
        )
      : districtCollection?.geojson.features ?? []
  const mapRasterVisible = active === 'satellite'
    ? satelliteOverlayVisible && !satelliteSwipeEnabled
    : lstOverlayVisible
  const inspectionCellGeojson: FeatureCollection | null = inspection?.cell_outline
    ? {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          properties: {},
          geometry: inspection.cell_outline,
        }],
      }
    : null
  const handleMapInspect = useCallback(async (latitude: number, longitude: number) => {
    const requestId = ++inspectionRequestId.current
    const point = { latitude, longitude }
    setInspectionPoint(point)
    setInspection(null)
    setInspectionError(null)
    setInspectionLoading(true)
    try {
      const response = await fetch(
        `${API_BASE}/api/inspect?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`,
      )
      if (!response.ok) {
        const detail = await response.text()
        throw new Error(`Map inspection failed (${response.status}): ${detail}`)
      }
      const data = await response.json() as MapInspection
      if (requestId !== inspectionRequestId.current) return
      setInspection(data)
      setRegion(data.district_id ? `district_${data.district_id}` : 'tamil_nadu')
      setConstituencyId(data.constituency_id)
    } catch (error: unknown) {
      if (requestId !== inspectionRequestId.current) return
      setInspectionError(error instanceof Error ? error.message : 'Map inspection is unavailable.')
    } finally {
      if (requestId === inspectionRequestId.current) setInspectionLoading(false)
    }
  }, [])

  const analyticsDistricts = analyticsData?.regions.filter(
    (item) => item.region_type === 'district',
  ) ?? []
  const compareDistrictA = analyticsDistricts.find(
    (item) => item.region_id === compareDistrictIds[0],
  ) ?? analyticsDistricts[0]
  const compareDistrictB = analyticsDistricts.find(
    (item) => item.region_id === compareDistrictIds[1],
  ) ?? analyticsDistricts.find((item) => item.region_id !== compareDistrictA?.region_id)
  const trendDistrict = analyticsDistricts.find(
    (item) => item.region_id === trendDistrictId,
  ) ?? analyticsDistricts[0]
  const scenarioEstimate = useMemo(() => {
    const report = predictionEstimate
    const baseline = report?.scenario_baseline_lst_c
    const ndvi = report?.scenario_ndvi_mean
    const ndviCoefficient = report?.ndvi_coefficient_c_per_index
    if (
      report?.model_status !== 'available'
      || baseline == null
      || ndvi == null
      || ndviCoefficient == null
    ) return null
    const scenarioNdvi = Math.min(1, ndvi + ndviUpliftPercent / 100)
    const rawPredictedChange = ndviCoefficient * (scenarioNdvi - ndvi)
    const predictedChange = Math.abs(rawPredictedChange) < 0.0005 ? 0 : rawPredictedChange
    const errorMargin = (report.scenario_error_bound_c ?? 0) * 2
    return {
      ndvi: scenarioNdvi,
      predictedChange,
      scenarioPrediction: baseline + predictedChange,
      changeLower: predictedChange - errorMargin,
      changeUpper: predictedChange + errorMargin,
      errorMargin,
    }
  }, [ndviUpliftPercent, predictionEstimate])
  const scatterChartPoints = useMemo(
    () => scatterSummary?.points.map((point) => ({
      ndvi: point.ndvi,
      lst_value: convertTemperature(point.lst_c, dashboardSettings.temperatureUnit),
    })) ?? [],
    [dashboardSettings.temperatureUnit, scatterSummary],
  )
  const sortedAnalyticsRows = useMemo(() => {
    const rows = [...(analyticsData?.regions ?? [])]
    rows.sort((left, right) => {
      const leftValue = left[analyticsSort.key]
      const rightValue = right[analyticsSort.key]
      if (leftValue == null) return rightValue == null ? 0 : 1
      if (rightValue == null) return -1
      const order = typeof leftValue === 'number' && typeof rightValue === 'number'
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), 'en')
      return analyticsSort.direction === 'asc' ? order : -order
    })
    return rows
  }, [analyticsData, analyticsSort])
  const sortAnalyticsBy = (key: AnalyticsSortKey) => {
    setAnalyticsSort((previous) => ({
      key,
      direction: previous.key === key && previous.direction === 'asc' ? 'desc' : 'asc',
    }))
  }
  const priorityAllocations = useMemo(() => {
    const amount = budgetAmount.trim() === '' ? null : Number(budgetAmount)
    const count = Math.floor(Number(priorityTopCount))
    if (amount === null || !Number.isFinite(amount) || amount < 0 || !Number.isFinite(count) || count < 1) {
      return new Map<string, number>()
    }
    const selected = (prioritiesData?.priorities ?? [])
      .filter((item) => item.priority_score != null && item.priority_score > 0)
      .slice(0, count)
    const scoreTotal = selected.reduce((total, item) => total + (item.priority_score ?? 0), 0)
    if (scoreTotal <= 0) return new Map<string, number>()
    return new Map(
      selected.map((item) => [
        item.constituency_id,
        amount * (item.priority_score ?? 0) / scoreTotal,
      ]),
    )
  }, [budgetAmount, priorityTopCount, prioritiesData])

  const exportPriorityCsv = () => {
    if (!prioritiesData) return
    const escapeCsv = (value: string | number | null | undefined) =>
      `"${String(value ?? '').replace(/"/g, '""')}"`
    const headings = [
      'District',
      'Constituency',
      'Priority score (derived, 0-100)',
      'Mean LST (C)',
      'LST source',
      'Population estimate (2025)',
      'Population source',
      'Mean NDVI (greenness proxy)',
      'NDVI source',
      'Resolution (m)',
      'Composite start',
      'Composite end',
      'Intervention (user-selected)',
      'Cost (user-entered)',
      'Budget allocation (user-entered total, proportional to score)',
      'No-data reason',
    ]
    const lines = [
      headings,
      ...prioritiesData.priorities.map((item) => [
        item.district_name,
        item.constituency_name,
        item.priority_score,
        item.lst_mean_c,
        prioritiesData.lst_source,
        item.population_estimated_2025,
        prioritiesData.population_source,
        item.ndvi_mean,
        prioritiesData.ndvi_source,
        item.resolution_m,
        item.composite_start,
        item.composite_end,
        interventionInputs[item.constituency_id]?.type,
        interventionInputs[item.constituency_id]?.cost,
        priorityAllocations.get(item.constituency_id),
        item.priority_reason,
      ]),
    ].map((line) => line.map(escapeCsv).join(',')).join('\r\n')
    const file = new Blob([`\uFEFF${lines}`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(file)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'ecotherm-constituency-priorities.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  useEffect(() => {
    const controller = new AbortController()
    setSummaryLoading(true)
    fetch(
      `${API_BASE}/api/v1/summary?region_id=${encodeURIComponent(summaryRegionId)}&season_year=2026`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Dashboard data request failed (${response.status}): ${detail}`)
        }
        return (await response.json()) as DashboardSummary
      })
      .then((data) => setSummary(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setSummary(null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setSummaryLoading(false)
      })
    return () => controller.abort()
  }, [summaryRegionId])

  useEffect(() => {
    if (active !== 'satellite' || !constituencyId) {
      setScatterSummary(null)
      setScatterLoading(false)
      setScatterError(null)
      return
    }
    const controller = new AbortController()
    setScatterSummary(null)
    setScatterLoading(true)
    setScatterError(null)
    fetch(
      `${API_BASE}/api/v1/satellite/scatter?constituency_id=${encodeURIComponent(constituencyId)}&season_year=2026`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Satellite cell data request failed (${response.status}): ${detail}`)
        }
        return (await response.json()) as SatelliteScatterSummary
      })
      .then((data) => setScatterSummary(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setScatterError(error instanceof Error ? error.message : 'Satellite cell data is unavailable.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setScatterLoading(false)
      })
    return () => controller.abort()
  }, [active, constituencyId])

  useEffect(() => {
    if (active !== 'analytics' && active !== 'reports') return
    const controller = new AbortController()
    setAnalyticsLoading(true)
    setAnalyticsError(null)
    fetch(`${API_BASE}/api/v1/analytics/regions?season_year=2026`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Environmental analytics request failed (${response.status}): ${detail}`)
        }
        return (await response.json()) as AnalyticsResponse
      })
      .then((data) => setAnalyticsData(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setAnalyticsError(error instanceof Error ? error.message : 'Environmental analytics are unavailable.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setAnalyticsLoading(false)
      })
    return () => controller.abort()
  }, [active])

  useEffect(() => {
      if (active !== 'priorities') return
      const controller = new AbortController()
      setPrioritiesLoading(true)
      setPrioritiesError(null)
      fetch(`${API_BASE}/api/v1/priorities/constituencies?season_year=2026`, {
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok) {
            const detail = await response.text()
            throw new Error(`Priority data request failed (${response.status}): ${detail}`)
          }
          return (await response.json()) as PrioritiesResponse
        })
        .then((data) => setPrioritiesData(data))
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === 'AbortError') return
          setPrioritiesError(error instanceof Error ? error.message : 'Priority data is unavailable.')
        })
        .finally(() => {
          if (!controller.signal.aborted) setPrioritiesLoading(false)
        })
      return () => controller.abort()
  }, [active])

  useEffect(() => {
    const controller = new AbortController()
    setPredictionStatusLoading(true)
    setPredictionStatusError(null)
    fetch(
      `${API_BASE}/api/v1/predictions/status?region_id=${encodeURIComponent(summaryRegionId)}`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Prediction readiness request failed (${response.status}): ${detail}`)
        }
        return (await response.json()) as PredictionStatus
      })
      .then((data) => setPredictionStatus(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setPredictionStatus(null)
        setPredictionStatusError(
          error instanceof Error ? error.message : 'Prediction readiness is unavailable.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setPredictionStatusLoading(false)
      })
    return () => controller.abort()
  }, [summaryRegionId])

  useEffect(() => {
    if (active !== 'predictions') return
    const controller = new AbortController()
    setPredictionEstimate(null)
    setPredictionEstimateLoading(true)
    setPredictionEstimateError(null)
    setNdviUpliftPercent(0)
    fetch(
      `${API_BASE}/api/v1/predictions/estimate?region_id=${encodeURIComponent(summaryRegionId)}&season_year=2026`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Spatial estimate request failed (${response.status}): ${detail}`)
        }
        return (await response.json()) as PredictionEstimate
      })
      .then((data) => setPredictionEstimate(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setPredictionEstimateError(error instanceof Error ? error.message : 'Spatial estimate model is unavailable.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setPredictionEstimateLoading(false)
      })
    return () => controller.abort()
  }, [active, summaryRegionId])

  useEffect(() => {
    const controller = new AbortController()
    setSatelliteSummaryLoading(true)
    setSatelliteSummaryError(null)
    fetch(
      `${API_BASE}/api/v1/satellite/summary?region_id=${encodeURIComponent(summaryRegionId)}&season_year=2026`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.text()
          throw new Error(`Satellite analysis request failed (${response.status}): ${detail}`)
        }
        return (await response.json()) as SatelliteAnalysisSummary
      })
      .then((data) => setSatelliteSummary(data))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setSatelliteSummary(null)
        setSatelliteSummaryError(
          error instanceof Error ? error.message : 'Satellite analysis is unavailable.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setSatelliteSummaryLoading(false)
      })
    return () => controller.abort()
  }, [summaryRegionId])

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <Brand compact />
        <nav className="side-nav" aria-label="ECOTHERM dashboard sections">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={active === section.id ? 'side-nav__item active' : 'side-nav__item'}
              onClick={() => {
                setActive(section.id)
                if (section.id === 'heat-map') {
                  setBaseLayer(dashboardSettings.basemapPreference === 'street' ? 'map' : 'satellite')
                  setLstOverlayVisible(true)
                }
                if (section.id === 'satellite') {
                  setBaseLayer('satellite')
                  setSatelliteOverlayVisible(false)
                  setSatelliteSwipeEnabled(false)
                }
              }}
              aria-current={active === section.id ? 'page' : undefined}
            >
              <Icon name={section.icon} />
              <span>{section.label}</span>
            </button>
          ))}
        </nav>
        <Link className="sidebar-home" to="/">Back to welcome ↗</Link>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <span className="dashboard-eyebrow">
              {summary?.data_status === 'available' || summary?.data_status === 'partial'
                ? 'DEMO DATA · CACHED REAL SOURCES'
                : 'DEMO DATA · REAL SOURCES ONLY'}
            </span>
            <h1>{active === 'overview' ? 'Urban heat overview' : sections.find((item) => item.id === active)?.label}</h1>
          </div>
          <div className="region-controls">
            <label className="region-control">
              <span>Region</span>
              <select
                value={region}
                onChange={(event) => {
                  setRegion(event.target.value)
                  setConstituencyId(null)
                }}
              >
                {regions.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="region-control">
              <span>Constituency</span>
              <select
                value={constituencyId ?? ''}
                disabled={!region.startsWith('district_') || !constituencyCollection}
                onChange={(event) => setConstituencyId(event.target.value || null)}
                aria-describedby={constituencyError ? 'constituency-error' : undefined}
              >
                <option value="">
                  {region.startsWith('district_') ? 'All of district' : 'Choose a district first'}
                </option>
                {constituencyCollection?.constituencies.map((item) => (
                  <option key={item.constituency_id} value={item.constituency_id}>
                    {item.constituency_name}
                  </option>
                ))}
              </select>
              {constituencyError && (
                <span className="region-error" id="constituency-error">
                  Constituency boundary list unavailable: {constituencyError}
                </span>
              )}
            </label>
          </div>
        </header>

        {active !== 'overview' && active !== 'heat-map' && active !== 'satellite' && active !== 'predictions' && active !== 'analytics' && active !== 'priorities' && active !== 'reports' && active !== 'settings' ? (
          <div className="section-empty">
            <span className="section-empty__icon"><Icon name={sections.find((item) => item.id === active)?.icon || 'grid'} /></span>
            <h2>{sections.find((item) => item.id === active)?.label}</h2>
            <p>No cached real-data result is available for this section yet. Acquisition and processing must complete before values or map layers appear.</p>
            <button type="button" onClick={() => setActive('overview')}>Return to overview</button>
          </div>
        ) : (
          <>
            {active === 'overview' && (
            <div className="metric-grid" aria-label="Urban heat summary">
              <article className="metric-card">
                <span>Mean LST</span>
                <strong>{summaryLoading ? '…' : formatTemperature(summary?.lst_mean_c, dashboardSettings.temperatureUnit)}</strong>
                <small>
                  {summary?.lst_mean_c == null
                    ? 'Cached Landsat LST is not present for this selection.'
                    : `${satelliteSummary?.lst_source ?? 'Landsat 8/9 Collection 2 Level 2'} · ${satelliteSummary?.grid_resolution_m ?? summary.grid_resolution_m ?? 'Unavailable'} m grid · ${
                        satelliteSummary?.composite_start && satelliteSummary.composite_end
                          ? `${satelliteSummary.composite_start} to ${satelliteSummary.composite_end}`
                          : `summer ${summary.season_year}; exact composite dates unavailable`
                      } · ${
                        summary.lst_coverage_percent == null
                          ? 'Unavailable: valid and total grid-cell counts are unavailable'
                          : `${formatNumber(summary.lst_coverage_percent, 0)}% grid coverage`
                      }`}
                </small>
              </article>
              <article className="metric-card">
                <span>Estimated population</span>
                <strong>{summaryLoading ? '…' : formatNumber(summary?.estimated_population_2025, 0)}</strong>
                <small>
                  {summary?.estimated_population_2025 == null
                    ? 'WorldPop model year 2025 estimate is not present for this selection.'
                    : `WorldPop modelled estimate · source year 2025 · ${summary.grid_resolution_m ?? 'Unavailable'} m grid${
                        summary.population_coverage_percent == null
                          ? ' · Unavailable: population coverage counts are unavailable'
                          : ` · ${formatNumber(summary.population_coverage_percent, 0)}% coverage`
                      }`}
                </small>
              </article>
              <article className="metric-card">
                <span>People exposed to high heat</span>
                <strong>{formatNumber(summary?.people_exposed_high_heat, 0)}</strong>
                <small>
                  {summary?.people_exposed_high_heat == null
                    ? 'Unavailable: required cached heat-risk and population inputs are unavailable'
                    : `WorldPop 2025 estimate with Landsat/Sentinel-derived risk score ≥75 · ${summary.grid_resolution_m ?? 'Unavailable'} m grid · summer ${summary.season_year}`}
                </small>
              </article>
              <article className="metric-card">
                <span>Air-temperature context</span>
                <strong>
                  {selectedLiveWeather
                    ? selectedLiveWeather.temperature_2m_c == null
                      ? 'Unavailable'
                      : formatTemperature(selectedLiveWeather.temperature_2m_c, dashboardSettings.temperatureUnit)
                    : summary?.weather_mean_air_temperature_c == null
                      ? 'Unavailable'
                      : formatTemperature(summary.weather_mean_air_temperature_c, dashboardSettings.temperatureUnit)}
                </strong>
                <small>
                  {selectedLiveWeather
                    ? selectedLiveWeather.temperature_2m_c === null
                      ? 'Unavailable: Open-Meteo did not return a live temperature value'
                      : `${selectedLiveWeather.provider ?? 'Open-Meteo Forecast API'} · ${weatherReadiness} · spatial resolution not exposed by the live endpoint`
                    : summary?.weather_model
                      ? `${summary.weather_model === 'era5_land' ? 'Open-Meteo ERA5-Land 0.1° (~11 km)' : summary.weather_model} at the ${region === 'tamil_nadu' ? 'statewide' : 'district'} reference point · Apr 1 to Jun 30, ${summary.season_year} · reanalysis, not a station observation`
                      : 'Regional air-temperature context is not cached for this selection.'}
                </small>
              </article>
              <article className="metric-card">
                <span>High-risk cells</span>
                <strong>{formatNumber(summary?.high_risk_cell_count, 0)}</strong>
                <small>
                  {summary?.high_risk_cell_count == null
                    ? 'Unavailable: cached heat-risk inputs are unavailable'
                    : `Landsat LST / Sentinel-2 NDVI and NDBI rule-based estimate · risk score ≥75 · ${summary.grid_resolution_m ?? 'Unavailable'} m grid · summer ${summary.season_year}`}
                </small>
              </article>
              <article className="metric-card">
                <span>{region === 'tamil_nadu' ? 'Statewide reference difference' : 'Urban heat island intensity'}</span>
                <strong>
                  {summary?.urban_heat_island_intensity_c == null
                    ? 'Unavailable'
                    : `${summary.urban_heat_island_intensity_c > 0 ? '+' : ''}${formatTemperatureDelta(summary.urban_heat_island_intensity_c, dashboardSettings.temperatureUnit)}`}
                </strong>
                <small>
                  {summary?.urban_heat_island_intensity_c == null
                    ? 'Unavailable: local or statewide cached LST reference is unavailable'
                    : region === 'tamil_nadu'
                      ? `Cached Landsat LST state mean compared with itself · ${summary.grid_resolution_m ?? 'Unavailable'} m · summer ${summary.season_year}`
                      : `Cached Landsat LST area mean minus statewide mean · ${summary.grid_resolution_m ?? 'Unavailable'} m cells · summer ${summary.season_year}`}
                </small>
              </article>
            </div>
            )}

            {active === 'satellite' && (
              <div className="metric-grid satellite-metric-grid" aria-label="Satellite analysis summary">
                {satelliteLayers.map((layer) => {
                  const metric = satelliteSummary?.[layer.id]
                  const noDataReason = metric?.mean != null
                    ? null
                    : satelliteSummary?.data_status === 'unavailable'
                      ? constituencyId
                        ? 'No aggregate grid summary is cached for this constituency.'
                        : 'No cached grid observations are available for this region and season.'
                      : `No valid ${layer.label} cells are available in this composite.`
                  const value = layer.id === 'lst'
                    ? formatTemperature(metric?.mean, dashboardSettings.temperatureUnit)
                    : formatNumber(metric?.mean, 3)
                  return (
                    <article className="metric-card" key={layer.id}>
                      <span>{layer.id === 'lst' ? 'Mean land-surface temperature' : `Mean ${layer.label}`}</span>
                      <strong>{satelliteSummaryLoading ? '…' : value}</strong>
                      <small>
                        {layer.id === 'lst'
                          ? 'Landsat 8/9 · surface temperature'
                          : layer.id === 'ndvi'
                            ? 'Sentinel-2 · vegetation greenness'
                            : layer.id === 'ndbi'
                              ? 'Sentinel-2 · built-up index'
                              : 'Sentinel-2 · water index'}
                        {' · '}
                        {satelliteSummaryLoading
                          ? 'Loading cached summary'
                          : noDataReason
                            ? `Unavailable: ${noDataReason}; resolution ${satelliteSummary?.grid_resolution_m ?? 'unavailable'} m; composite dates ${satelliteSummary?.composite_start ?? 'unavailable'} to ${satelliteSummary?.composite_end ?? 'unavailable'}`
                            : `${formatNumber(metric?.coverage_percent, 1)}% grid coverage · ${satelliteSummary?.grid_resolution_m ?? 'Unavailable'} m cells · ${satelliteSummary?.composite_start ?? 'Unavailable'} to ${satelliteSummary?.composite_end ?? 'Unavailable'}`}
                      </small>
                    </article>
                  )
                })}
              </div>
            )}

            {active === 'predictions' && (
              <section className="predictions-page" aria-label="AI spatial LST estimate model">
                <article className="prediction-status-banner" role={predictionEstimateError ? 'alert' : 'status'}>
                  <span className="prediction-status-banner__icon" aria-hidden="true">✦</span>
                  <div>
                    <span className="panel-kicker">SPATIAL HOLDOUT · {predictionEstimate?.model_status.toUpperCase() ?? (predictionEstimateLoading ? 'CHECKING' : 'UNAVAILABLE')}</span>
                    <h2>Explainable LST model</h2>
                    <p>
                      Fits cached 2026 cell-level Landsat LST from NDVI and NDBI, then tests on districts excluded from training.
                    </p>
                    <strong>Every model output is an estimate, not a forecast.</strong>
                  </div>
                </article>

                {predictionEstimateLoading ? (
                  <p className="prediction-detail-note" role="status">Loading cached grid inputs and fitting the spatially held-out model…</p>
                ) : predictionEstimateError ? (
                  <p className="prediction-detail-note prediction-estimate-error" role="alert">{predictionEstimateError}</p>
                ) : predictionEstimate?.model_status !== 'available' ? (
                  <p className="prediction-detail-note">Unavailable: {predictionEstimate?.reason ?? 'No qualified spatial model inputs are available.'}</p>
                ) : (
                  <>
                    <div className="prediction-readiness-grid" aria-label="Spatial model evaluation metrics">
                      <article className="prediction-gate-card">
                        <span>Held-out R² · estimate model</span>
                        <strong>{predictionEstimate.r_squared == null ? 'Unavailable' : formatNumber(predictionEstimate.r_squared, 3)}</strong>
                        <small>
                          {predictionEstimate.r_squared == null
                            ? 'Unavailable: held-out LST values have no measurable variance.'
                            : `${predictionEstimate.test_district_count} districts excluded from training`}
                          {' · '}{predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m ?? 'Unavailable'} m grid ·{' '}
                          {predictionEstimate.evaluation_start_date ?? 'Unavailable'} to {predictionEstimate.evaluation_end_date ?? 'Unavailable'}
                        </small>
                      </article>
                      <article className="prediction-gate-card">
                        <span>Mean absolute error · estimate</span>
                        <strong>{predictionEstimate.mean_absolute_error_c == null ? 'Unavailable' : formatTemperatureDelta(predictionEstimate.mean_absolute_error_c, dashboardSettings.temperatureUnit)}</strong>
                        <small>{predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m ?? 'Unavailable'} m cells · {predictionEstimate.evaluation_start_date ?? 'Unavailable'} to {predictionEstimate.evaluation_end_date ?? 'Unavailable'}</small>
                      </article>
                      <article className="prediction-gate-card">
                        <span>90th-percentile absolute error</span>
                        <strong>{predictionEstimate.p90_absolute_error_c == null ? 'Unavailable' : formatTemperatureDelta(predictionEstimate.p90_absolute_error_c, dashboardSettings.temperatureUnit)}</strong>
                        <small>Empirical held-out residuals from {predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m ?? 'Unavailable'} m · {predictionEstimate.evaluation_start_date ?? 'Unavailable'} to {predictionEstimate.evaluation_end_date ?? 'Unavailable'} · not a confidence interval</small>
                      </article>
                      <article className="prediction-gate-card">
                        <span>Spatial split · districts</span>
                        <strong>{predictionEstimate.training_district_count} train / {predictionEstimate.test_district_count} test</strong>
                        <small>{formatNumber(predictionEstimate.training_cell_count, 0)} training / {formatNumber(predictionEstimate.test_cell_count, 0)} test cells · {predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m ?? 'Unavailable'} m · {predictionEstimate.evaluation_start_date ?? 'Unavailable'} to {predictionEstimate.evaluation_end_date ?? 'Unavailable'}</small>
                      </article>
                    </div>

                    <div className="prediction-detail-grid">
                      <article className="panel prediction-detail-panel">
                        <header>
                          <div>
                            <span className="panel-kicker">EXPLAINABLE MODEL · ESTIMATE</span>
                            <h2>Feature importance</h2>
                          </div>
                        </header>
                        <div className="prediction-observation-grid prediction-feature-list">
                          {predictionEstimate.feature_importance.map((feature) => (
                            <div key={feature.feature}>
                              <span>{feature.label}</span>
                              <strong>{feature.relative_importance_percent == null ? 'Unavailable' : `${formatNumber(feature.relative_importance_percent)}%`}</strong>
                              <small>
                                {feature.source} · {feature.resolution_m ?? 'Unavailable'} m · {predictionEstimate.evaluation_start_date} to {predictionEstimate.evaluation_end_date}
                              </small>
                            </div>
                          ))}
                        </div>
                        <p className="prediction-detail-note">
                          Relative importance is the normalized absolute standardized linear coefficient; it describes this fitted model, not causal impact.
                        </p>
                      </article>

                      <article className="panel prediction-detail-panel">
                        <header>
                          <div>
                            <span className="panel-kicker">TRAIN / TEST DESIGN</span>
                            <h2>District holdout</h2>
                          </div>
                          <span className="status-pill">{predictionEstimate.validation_method}</span>
                        </header>
                        <div className="prediction-district-split">
                          <div>
                            <strong>Training districts ({predictionEstimate.training_districts.length})</strong>
                            <span>{predictionEstimate.training_districts.map((item) => item.replaceAll('_', ' ')).join(', ')}</span>
                          </div>
                          <div>
                            <strong>Held-out test districts ({predictionEstimate.test_districts.length})</strong>
                            <span>{predictionEstimate.test_districts.map((item) => item.replaceAll('_', ' ')).join(', ')}</span>
                          </div>
                        </div>
                        <p className="prediction-detail-note">
                          Target: {predictionEstimate.target}. Model fitting and evaluation use the cached {predictionEstimate.evaluation_start_date} to {predictionEstimate.evaluation_end_date} 1 km composite; only held-out districts contribute to the reported metrics.
                        </p>
                      </article>
                    </div>

                    <article className="panel prediction-input-panel">
                      <header>
                        <div>
                          <span className="panel-kicker">REGIONAL MODEL INPUTS</span>
                          <h2>Cached features for {selectedConstituency?.constituency_name ?? selectedRegion.name}</h2>
                        </div>
                      </header>
                      <div className="prediction-input-list">
                        {predictionEstimate.inputs.map((input) => (
                          <div key={input.feature}>
                            <span>{input.label}</span>
                            <strong>{input.value == null ? 'Unavailable' : formatNumber(input.value, 3)}</strong>
                            <small>
                              {input.value == null
                                ? `Unavailable: ${input.reason}`
                                : `${input.source} · ${input.resolution_m ?? 'Unavailable'} m grid · ${input.composite_start ?? 'Unavailable'} to ${input.composite_end ?? 'Unavailable'}`}
                            </small>
                          </div>
                        ))}
                      </div>
                      <p className="prediction-detail-note">
                        NDBI is a built-up index proxy, not a literal built-up share. The what-if scenario changes NDVI only; it is not causal and does not change NDBI.
                      </p>
                    </article>

                    <article className="panel prediction-what-if-panel">
                      <header>
                        <div>
                          <span className="panel-kicker">WHAT IF · MODEL ESTIMATE</span>
                          <h2>NDVI uplift scenario</h2>
                        </div>
                        <span className="status-pill">Estimate, not a forecast</span>
                      </header>
                      <div className="prediction-what-if-body">
                        {scenarioEstimate ? (
                          <>
                            <label className="prediction-uplift-control">
                              <span>NDVI uplift: +{ndviUpliftPercent} percentage points (+{formatNumber(ndviUpliftPercent / 100, 2)} index points)</span>
                              <input
                                type="range"
                                min="0"
                                max="20"
                                step="1"
                                value={ndviUpliftPercent}
                                onChange={(event) => setNdviUpliftPercent(Number(event.target.value))}
                                aria-label="NDVI increase from zero to twenty percentage points"
                              />
                            </label>
                            <div className="prediction-scenario-values">
                              <div><span>Baseline LST estimate</span><strong>{formatTemperature(predictionEstimate.scenario_baseline_lst_c, dashboardSettings.temperatureUnit)}</strong><small>{predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m} m · {predictionEstimate.evaluation_start_date} to {predictionEstimate.evaluation_end_date}</small></div>
                              <div><span>Scenario LST estimate</span><strong>{formatTemperature(scenarioEstimate.scenarioPrediction, dashboardSettings.temperatureUnit)}</strong><small>{predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m} m · {predictionEstimate.evaluation_start_date} to {predictionEstimate.evaluation_end_date}</small></div>
                              <div><span>Estimated change</span><strong>{scenarioEstimate.predictedChange > 0 ? '+' : ''}{formatTemperatureDelta(scenarioEstimate.predictedChange, dashboardSettings.temperatureUnit)}</strong><small>{predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m} m · {predictionEstimate.evaluation_start_date} to {predictionEstimate.evaluation_end_date}</small></div>
                              <div><span>Estimated change range</span><strong>{formatTemperatureDelta(scenarioEstimate.changeLower, dashboardSettings.temperatureUnit)} to {formatTemperatureDelta(scenarioEstimate.changeUpper, dashboardSettings.temperatureUnit)}</strong><small>Held-out residual envelope · {predictionEstimate.target_source} · {predictionEstimate.evaluation_resolution_m} m · {predictionEstimate.evaluation_start_date} to {predictionEstimate.evaluation_end_date}</small></div>
                            </div>
                            <p className="prediction-detail-note">
                              Range is the estimated change ± 2 × held-out 90th-percentile absolute error ({formatTemperatureDelta(predictionEstimate.scenario_error_bound_c, dashboardSettings.temperatureUnit)}). It is a conservative empirical error envelope, not a confidence interval or forecast. Scenario NDVI: {formatNumber(predictionEstimate.scenario_ndvi_mean, 3)} → {formatNumber(scenarioEstimate.ndvi, 3)}; NDBI remains {formatNumber(predictionEstimate.scenario_ndbi_mean, 3)}.
                            </p>
                          </>
                        ) : (
                          <p className="prediction-detail-note">
                            Unavailable: {predictionEstimate.scenario_reason ?? 'paired regional NDVI and NDBI inputs are unavailable for this selection.'}
                          </p>
                        )}
                      </div>
                    </article>
                    <p className="prediction-detail-note">
                      {predictionStatusLoading
                        ? 'Checking forecast readiness…'
                        : predictionStatusError
                          ? `Future forecast unavailable: ${predictionStatusError}`
                          : `This is a spatial estimate of the cached ${predictionEstimate.season_year} LST surface. A future-season forecast remains unavailable; cached seasons: ${predictionStatus?.available_season_years.join(', ') ?? 'Unavailable'}.`}
                    </p>
                  </>
                )}
              </section>
            )}

            {active !== 'predictions' && active !== 'analytics' && (
            <>
            <div className={active === 'heat-map' || active === 'satellite' ? 'dashboard-grid dashboard-grid--heat-map' : 'dashboard-grid'}>
              <article className="panel map-panel">
                <header>
                  <div>
                    <span className="panel-kicker">
                      {active === 'heat-map' ? 'HEAT MAP EXPLORER' : active === 'satellite' ? 'SATELLITE ANALYSIS' : 'REGION'}
                    </span>
                    <h2>{selectedConstituency?.constituency_name ?? selectedRegion.name}</h2>
                  </div>
                  <span className="status-pill">
                    {active === 'satellite'
                      ? satelliteSummaryLoading
                        ? 'Loading cached data'
                        : satelliteSummary?.data_status ?? 'Unavailable'
                      : summaryLoading
                        ? 'Loading cached data'
                        : summary?.data_status ?? 'Unavailable'}
                  </span>
                </header>
                <div className="map-layer-controls" aria-label="Map layers">
                  <div className="map-layer-controls__row">
                    <div className="map-basemap-switch" role="group" aria-label="Basemap">
                      <button
                        type="button"
                        aria-pressed={baseLayer === 'map'}
                        className={baseLayer === 'map' ? 'is-active' : ''}
                        onClick={() => {
                          setBaseLayer('map')
                          setSatelliteSwipeEnabled(false)
                        }}
                      >
                        Map
                      </button>
                      <button
                        type="button"
                        aria-pressed={baseLayer === 'satellite'}
                        className={baseLayer === 'satellite' ? 'is-active' : ''}
                        onClick={() => setBaseLayer('satellite')}
                      >
                        Satellite
                      </button>
                    </div>
                    <label className="map-layer-check">
                      <input
                        type="checkbox"
                        checked={labelsVisible}
                        onChange={(event) => setLabelsVisible(event.target.checked)}
                      />
                      Labels
                      <span>Satellite only</span>
                    </label>
                    {active === 'satellite' ? (
                      <div className="satellite-layer-switch" role="group" aria-label="Satellite analysis layer">
                        {satelliteLayers.map((layer) => (
                          <button
                            key={layer.id}
                            type="button"
                            aria-pressed={satelliteLayer === layer.id}
                            className={satelliteLayer === layer.id ? 'is-active' : ''}
                            onClick={() => {
                              setSatelliteLayer(layer.id)
                              setSatelliteOverlayVisible(true)
                              setSatelliteSwipeEnabled(false)
                            }}
                          >
                            {layer.id === 'ndbi' ? 'Built-up' : layer.label}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <label className="map-layer-check">
                        <input
                          type="checkbox"
                          checked={lstOverlayVisible}
                          onChange={(event) => setLstOverlayVisible(event.target.checked)}
                        />
                        LST heat
                      </label>
                    )}
                    {active === 'satellite' && (
                      <>
                        <label className="map-layer-check">
                          <input
                            type="checkbox"
                            checked={satelliteOverlayVisible}
                            disabled={satelliteSwipeEnabled}
                            onChange={(event) => setSatelliteOverlayVisible(event.target.checked)}
                          />
                          Overlay
                        </label>
                        <label className="map-layer-check">
                          <input
                            type="checkbox"
                            checked={satelliteSwipeEnabled}
                            onChange={(event) => {
                              setSatelliteSwipeEnabled(event.target.checked)
                              if (event.target.checked) {
                                setBaseLayer('satellite')
                                setSatelliteLayer('lst')
                              }
                            }}
                          />
                          Satellite/LST swipe
                        </label>
                      </>
                    )}
                    {(active === 'satellite' && satelliteSwipeEnabled) && (
                      <label className="map-layer-opacity">
                        Swipe
                        <input
                          type="range"
                          min="10"
                          max="90"
                          step="1"
                          value={satelliteSwipePosition}
                          onChange={(event) => setSatelliteSwipePosition(Number(event.target.value))}
                          aria-label="Satellite and LST swipe position"
                        />
                      </label>
                    )}
                    {((active === 'satellite' && satelliteOverlayVisible && !satelliteSwipeEnabled)
                      || (active !== 'satellite' && lstOverlayVisible)) && (
                      <label className="map-layer-opacity">
                        Opacity
                        <input
                          type="range"
                          min="0.15"
                          max="1"
                          step="0.05"
                          value={lstOpacity}
                          onChange={(event) => setLstOpacity(Number(event.target.value))}
                          aria-label="Satellite layer opacity"
                        />
                      </label>
                    )}
                  </div>
                  {((active === 'satellite' && (satelliteOverlayVisible || satelliteSwipeEnabled))
                    || (active !== 'satellite' && lstOverlayVisible)) && (
                    <div className="lst-legend" aria-label={`${active === 'satellite' ? satelliteLayer.toUpperCase() : 'Landsat LST'} colour legend`}>
                      <span>
                        {active === 'satellite' && satelliteLayer !== 'lst'
                          ? `${satelliteLayer === 'ndbi' ? 'NDBI · built-up index' : satelliteLayer.toUpperCase()} · 1 km cells`
                          : `Landsat LST · °${dashboardSettings.temperatureUnit} · 1 km cells`}
                      </span>
                      <div
                        className={`lst-legend__scale ${active === 'satellite' ? `lst-legend__scale--${satelliteLayer}` : ''}`}
                        aria-hidden="true"
                      />
                      <div className="lst-legend__labels">
                        {active === 'satellite' && satelliteLayer !== 'lst'
                          ? <><span>−1</span><span>0</span><span>+1</span></>
                          : <><span>{formatNumber(convertTemperature(25, dashboardSettings.temperatureUnit), 0)}</span><span>{formatNumber(convertTemperature(40, dashboardSettings.temperatureUnit), 0)}</span><span>{formatNumber(convertTemperature(55, dashboardSettings.temperatureUnit), 0)}+</span></>}
                      </div>
                    </div>
                  )}
                </div>
                {active === 'heat-map' && (
                  <div className="heat-map-context">
                    <strong>Landsat land-surface temperature</strong>
                    <span>April–June 2026 · cloud-masked seasonal composite · 1 km cells</span>
                    <span>Select a district or click the map to inspect cached cell values.</span>
                  </div>
                )}
                {active === 'satellite' && (
                  <div className="heat-map-context">
                    <strong>Cached seasonal satellite composite</strong>
                    <span>
                      {satelliteSummary?.composite_start && satelliteSummary.composite_end
                        ? `${satelliteSummary.composite_start} to ${satelliteSummary.composite_end}`
                        : 'April–June 2026'}
                      {' · '}
                      {satelliteSummary?.grid_resolution_m ?? 1000} m cells
                    </span>
                    <span>Select NDVI, built-up index, NDWI, or LST; the swipe compares cached satellite imagery with LST.</span>
                  </div>
                )}
                {districtCollection ? (
                  <div
                    className={active === 'heat-map' || active === 'satellite' ? 'district-map district-map--explorer' : 'district-map'}
                    role="region"
                    aria-label={active === 'heat-map'
                      ? 'Tamil Nadu heat map and district boundaries'
                      : active === 'satellite'
                        ? 'Tamil Nadu satellite analysis map and district boundaries'
                        : 'Tamil Nadu district boundaries'}
                  >
                    <MapContainer
                      center={[10.8, 78.7]}
                      zoom={7}
                      minZoom={5}
                      scrollWheelZoom
                      style={{
                        height: active === 'heat-map' || active === 'satellite' ? 'min(68vh, 720px)' : '360px',
                        width: '100%',
                      }}
                      attributionControl
                    >
                      {baseLayer === 'map' ? (
                        <TileLayer
                          attribution="&copy; OpenStreetMap contributors"
                          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                          maxZoom={19}
                        />
                      ) : !satelliteSwipeEnabled ? (
                        <TileLayer
                          attribution="Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
                          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                          maxZoom={19}
                        />
                      ) : null}
                      {satelliteSwipeEnabled && active === 'satellite' && (
                        <>
                          <Pane
                            name="satellite-swipe-imagery"
                            style={{
                              zIndex: 250,
                              clipPath: `inset(0 ${100 - satelliteSwipePosition}% 0 0)`,
                            }}
                          >
                            <TileLayer
                              attribution="Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
                              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                              maxZoom={19}
                            />
                          </Pane>
                          <Pane
                            name="satellite-swipe-lst"
                            style={{
                              zIndex: 251,
                              clipPath: `inset(0 0 0 ${satelliteSwipePosition}%)`,
                            }}
                          >
                            <TileLayer
                              attribution="Landsat 8/9 Level-2 LST · USGS · ECOTHERM cached raster"
                              url={`${API_BASE}/api/v1/map/lst/{z}/{x}/{y}.png`}
                              opacity={lstOpacity}
                              maxNativeZoom={13}
                              maxZoom={19}
                            />
                          </Pane>
                        </>
                      )}
                      {baseLayer === 'satellite' && labelsVisible && (
                        satelliteSwipeEnabled ? (
                          <Pane name="satellite-swipe-labels" style={{ zIndex: 300, pointerEvents: 'none' }}>
                            <TileLayer
                              attribution="Labels &copy; Esri, HERE, Garmin, and OpenStreetMap contributors"
                              url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
                              maxZoom={19}
                            />
                            <TileLayer
                              attribution="Labels &copy; Esri, HERE, Garmin, and OpenStreetMap contributors"
                              url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
                              maxZoom={19}
                            />
                          </Pane>
                        ) : (
                        <>
                          <TileLayer
                            attribution="Labels &copy; Esri, HERE, Garmin, and OpenStreetMap contributors"
                            url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
                            maxZoom={19}
                          />
                          <TileLayer
                            attribution="Labels &copy; Esri, HERE, Garmin, and OpenStreetMap contributors"
                            url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
                            maxZoom={19}
                          />
                        </>
                        )
                      )}
                      {mapRasterVisible && !satelliteSwipeEnabled && (
                        <TileLayer
                          attribution={active === 'satellite' && satelliteLayer !== 'lst'
                            ? 'Sentinel-2 SR Harmonized · Copernicus/ESA · ECOTHERM cached index raster'
                            : 'Landsat 8/9 Level-2 LST · USGS · ECOTHERM cached raster'}
                          url={`${API_BASE}/api/v1/map/${active === 'satellite' ? satelliteLayer : 'lst'}/{z}/{x}/{y}.png`}
                          opacity={lstOpacity}
                          maxNativeZoom={13}
                          maxZoom={19}
                        />
                      )}
                      <GeoJSON
                        key={`${region}-${districtCollection.district_count}`}
                        data={districtCollection.geojson as FeatureCollection}
                        bubblingMouseEvents={false}
                        style={(feature) => {
                          const selectedId = region.startsWith('district_') ? region.slice(9) : null
                          const isSelected = feature?.properties?.district_id === selectedId
                          const isDimmed = selectedId !== null && !isSelected
                          return {
                            color: baseLayer === 'satellite'
                              ? isSelected ? '#a8fff0' : '#d8fff1'
                              : isSelected ? '#b7efc7' : '#83d3a0',
                            weight: isSelected ? (baseLayer === 'satellite' ? 3.5 : 3) : (baseLayer === 'satellite' ? 1.6 : 1),
                            fillColor: baseLayer === 'satellite'
                              ? isSelected ? '#00c6a7' : '#22a6a1'
                              : isSelected ? '#83d3a0' : '#2f7553',
                            fillOpacity: isDimmed
                              ? baseLayer === 'satellite' ? 0.025 : 0.06
                              : isSelected ? baseLayer === 'satellite' ? 0.17 : 0.42
                              : baseLayer === 'satellite' ? 0.055 : 0.16,
                          }
                        }}
                        onEachFeature={(feature, layer) => {
                          const name = feature.properties?.district_name ?? 'District'
                          const source = feature.properties?.source ?? districtCollection.source
                          layer.bindPopup(
                            `<strong>${name}</strong><br/>Source: ${source}<br/>Boundary year: ${districtCollection.boundary_year}<br/>Licence: ${districtCollection.license}`,
                          )
                          layer.on('click', (event) => {
                            const districtId = feature.properties?.district_id
                            if (districtId) {
                              setRegion(`district_${districtId}`)
                              setConstituencyId(null)
                            }
                            handleMapInspect(event.latlng.lat, event.latlng.lng)
                          })
                        }}
                      />
                      {constituencyCollection && (
                        <GeoJSON
                          key={`constituencies-${region}`}
                          data={constituencyCollection.geojson}
                          bubblingMouseEvents={false}
                          style={(feature) => {
                            const id = feature?.properties?.constituency_id
                            const selected = id === constituencyId
                            const dimmed = constituencyId !== null && !selected
                            return {
                              color: baseLayer === 'satellite'
                                ? selected ? '#ffe27a' : '#d2fff0'
                                : selected ? '#f5cb70' : '#a9e3bb',
                              weight: selected ? (baseLayer === 'satellite' ? 3.5 : 3) : (baseLayer === 'satellite' ? 1.6 : 1),
                              fillColor: baseLayer === 'satellite'
                                ? selected ? '#f1bb3f' : '#55bca0'
                                : selected ? '#f5cb70' : '#55a879',
                              fillOpacity: dimmed
                                ? baseLayer === 'satellite' ? 0.035 : 0.08
                                : selected ? baseLayer === 'satellite' ? 0.2 : 0.58
                                : baseLayer === 'satellite' ? 0.07 : 0.26,
                            }
                          }}
                          onEachFeature={(feature, layer) => {
                            const properties = feature.properties ?? {}
                            const popup = document.createElement('div')
                            const heading = document.createElement('strong')
                            heading.textContent = `${properties.constituency_name ?? 'Constituency'} · AC ${properties.ac_number ?? 'unavailable'}`
                            popup.appendChild(heading)
                            const details = [
                              `District: ${properties.district_name ?? 'unavailable'}`,
                              `Largest overlap: ${properties.parent_district_overlap_percent ?? 'unavailable'}%`,
                              `Delimitation: ${properties.delimitation_year ?? 'unavailable'}`,
                              `Source: ${properties.source ?? constituencyCollection.source}`,
                              `Licence: ${properties.license ?? constituencyCollection.license}`,
                            ]
                            details.forEach((detail) => {
                              popup.appendChild(document.createElement('br'))
                              popup.appendChild(document.createTextNode(detail))
                            })
                            layer.bindPopup(popup)
                            layer.on('click', (event) => {
                              const districtId = properties.district_id
                              const id = properties.constituency_id
                              if (districtId && id) {
                                setRegion(`district_${districtId}`)
                                setConstituencyId(id)
                              }
                              handleMapInspect(event.latlng.lat, event.latlng.lng)
                            })
                          }}
                        />
                      )}
                      {inspectionCellGeojson && (
                        <GeoJSON
                          key={`inspection-cell-${inspection?.cell_id ?? 'unavailable'}`}
                          data={inspectionCellGeojson}
                          interactive={false}
                          style={{
                            color: '#f5cb70',
                            weight: 2,
                            fillColor: '#f5cb70',
                            fillOpacity: 0.1,
                          }}
                        />
                      )}
                      <MapClickInspector
                        onInspect={handleMapInspect}
                        point={inspectionPoint}
                        inspection={inspection}
                        loading={inspectionLoading}
                        error={inspectionError}
                        temperatureUnit={dashboardSettings.temperatureUnit}
                      />
                      <FitDistrictBounds
                        geojson={districtCollection.geojson}
                        constituencyGeojson={constituencyCollection?.geojson ?? null}
                        region={region}
                        constituencyId={constituencyId}
                        active={active}
                      />
                    </MapContainer>
                    {satelliteSwipeEnabled && active === 'satellite' && (
                      <div
                        className="satellite-swipe-divider"
                        style={{ left: `${satelliteSwipePosition}%` }}
                        aria-hidden="true"
                      />
                    )}
                  </div>
                ) : (
                  <div className="map-empty" role="img" aria-label="District boundary map loading or unavailable">
                    <div className="map-grid" aria-hidden="true" />
                    <div className="map-empty__message">
                      <span aria-hidden="true">⌖</span>
                      <strong>{districtError ? 'District boundaries unavailable' : 'Loading district boundaries'}</strong>
                      <p>{districtError ?? 'Reading sourced Tamil Nadu ADM2 polygons.'}</p>
                    </div>
                  </div>
                )}
              </article>

              {active === 'overview' && <article className="panel evidence-panel">
                <header>
                  <div>
                    <span className="panel-kicker">DATA STATUS</span>
                    <h2>Source readiness</h2>
                  </div>
                </header>
                <ul className="source-list">
                  <li><span>Landsat LST</span><strong className={summary?.lst_mean_c != null ? 'source-state cached' : 'source-state missing'}>{summary?.lst_mean_c != null ? 'Cached · 2026' : 'Missing'}</strong></li>
                  <li><span>Sentinel NDVI / NDBI / NDWI</span><strong className={summary?.grid_cell_count ? 'source-state cached' : 'source-state missing'}>{summary?.grid_cell_count ? 'Cached · 2026' : 'Missing'}</strong></li>
                  <li><span>Open-Meteo weather</span><strong className={weatherSourceAvailable ? 'source-state cached' : 'source-state missing'}>{weatherReadiness}</strong></li>
                  <li><span>WorldPop population / age</span><strong className={summary?.estimated_population_2025 != null ? 'source-state cached' : 'source-state missing'}>{summary?.estimated_population_2025 != null ? 'Cached · 2025 / age 2020' : 'Not acquired'}</strong></li>
                  <li className={osmSourceAvailable ? 'source-list__osm' : undefined}>
                    <span>OpenStreetMap features</span>
                    <strong className={osmSourceAvailable ? 'source-state cached' : 'source-state missing'}>
                      {summaryLoading
                        ? 'Checking…'
                        : osmSourceAvailable
                          ? `Cached · ${formatNumber(summary?.osm_feature_total, 0)} mapped`
                          : region === 'tamil_nadu'
                            ? 'Not acquired'
                            : 'Tamil Nadu-wide only'}
                    </strong>
                    {osmSourceAvailable && (
                      <small className="source-list__detail">
                        {osmFeatureDetails}
                      </small>
                    )}
                  </li>
                </ul>
              </article>}
              {active === 'satellite' && (
                <article className="panel satellite-scatter-panel">
                  <header>
                    <div>
                      <span className="panel-kicker">CELL-LEVEL ASSOCIATION</span>
                      <h2>NDVI vs LST per cell</h2>
                    </div>
                    <span className="status-pill">
                      {scatterLoading
                        ? 'Loading cached cells'
                        : scatterSummary?.correlation_pearson == null
                          ? 'Correlation unavailable'
                          : `r = ${formatNumber(scatterSummary.correlation_pearson, 3)}`}
                    </span>
                  </header>
                  <div className="satellite-scatter-panel__body">
                    {!constituencyId ? (
                      <p className="satellite-scatter-panel__empty">
                        Select a district, then a constituency to load paired cached cells.
                      </p>
                    ) : scatterError ? (
                      <p className="satellite-source-panel__error" role="alert">{scatterError}</p>
                    ) : scatterLoading ? (
                      <p className="satellite-scatter-panel__empty" role="status">Loading paired NDVI and LST cells…</p>
                    ) : scatterSummary?.data_status !== 'available' ? (
                      <p className="satellite-scatter-panel__empty">
                        Unavailable: {scatterSummary?.reason ?? 'No cached paired cells are available for this constituency and season.'}
                      </p>
                    ) : (
                      <>
                        <div
                          className="satellite-scatter-chart"
                          role="img"
                          aria-label={`Scatter plot of ${scatterSummary.pair_count} paired NDVI and land-surface temperature cells`}
                        >
                          <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart margin={{ top: 12, right: 20, bottom: 12, left: 8 }}>
                              <CartesianGrid stroke="rgba(169, 227, 187, .12)" />
                              <XAxis
                                type="number"
                                dataKey="ndvi"
                                name="NDVI"
                                domain={[-1, 1]}
                                tick={{ fill: 'rgba(224, 237, 228, .6)', fontSize: 10 }}
                                label={{ value: 'NDVI', position: 'insideBottom', offset: -4, fill: '#a9e3bb', fontSize: 10 }}
                              />
                              <YAxis
                                type="number"
                                dataKey="lst_value"
                                name="LST"
                                unit={` °${dashboardSettings.temperatureUnit}`}
                                tick={{ fill: 'rgba(224, 237, 228, .6)', fontSize: 10 }}
                                label={{ value: `LST (°${dashboardSettings.temperatureUnit})`, angle: -90, position: 'insideLeft', fill: '#a9e3bb', fontSize: 10 }}
                              />
                              <Tooltip
                                cursor={{ strokeDasharray: '3 3' }}
                                contentStyle={{ background: '#10291f', border: '1px solid rgba(143, 202, 163, .25)', color: '#edf7ef' }}
                                formatter={(value, name) => [
                                  `${formatNumber(Number(value), 3)}${name === 'LST' ? ` °${dashboardSettings.temperatureUnit}` : ''}`,
                                  name,
                                ]}
                              />
                              <Scatter name="LST" data={scatterChartPoints} fill="#6fcf97" fillOpacity={0.65} />
                            </ScatterChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="satellite-scatter-panel__metadata">
                          <span>{scatterSummary.pair_count.toLocaleString()} paired cells · {scatterSummary.resolution_m ?? 'Unavailable'} m resolution</span>
                          <span>
                            Composite: {scatterSummary.composite_start ?? 'Unavailable'} to {scatterSummary.composite_end ?? 'Unavailable'}
                          </span>
                          <span>NDVI source: {scatterSummary.ndvi_source}</span>
                          <span>LST source: {scatterSummary.lst_source}</span>
                          {scatterSummary.reason && <span>Unavailable: {scatterSummary.reason}</span>}
                        </div>
                      </>
                    )}
                  </div>
                </article>
              )}
              {active === 'satellite' && (
                <article className="panel satellite-source-panel">
                  <header>
                    <div>
                      <span className="panel-kicker">SOURCE & METHOD</span>
                      <h2>How to read these layers</h2>
                    </div>
                  </header>
                  <div className="satellite-source-panel__body">
                    <p>
                      Landsat 8/9 Collection 2 Level 2 provides land-surface temperature (LST). Sentinel-2 SR Harmonized provides NDVI, NDBI, and NDWI from optical reflectance; it does not measure temperature.
                    </p>
                    <p>
                      Values are cached April–June {satelliteSummary?.season_year ?? 2026} seasonal composites on a 1 km analysis grid. Cloud and quality masks can leave gaps; coverage is shown per layer and region.
                    </p>
                    {satelliteSummaryError && <p className="satellite-source-panel__error" role="alert">{satelliteSummaryError}</p>}
                    <span>Sources: USGS Landsat · Copernicus Sentinel-2 · seasonal medians · nearest-neighbour map display</span>
                  </div>
                </article>
              )}
            </div>

            {active === 'overview' && <div className="honesty-banner" role="note">
              <strong>About these values</strong>
              <span>
                LST is land surface temperature, not air temperature. Population is estimated (modelled), year 2025; age structure is a separate 2020 product. OSM counts represent mapped features, not a complete inventory. Missing values are not fabricated.
              </span>
            </div>}
            </>
            )}
            {active === 'analytics' && (
              <section className="environmental-analytics" aria-label="Environmental analytics">
                <header className="panel analytics-page-header">
                  <div>
                    <span className="panel-kicker">CACHED ENVIRONMENTAL EVIDENCE</span>
                    <h2>District and constituency analytics</h2>
                  </div>
                  <span className="status-pill">
                    {analyticsLoading ? 'Loading cached data' : analyticsData?.data_status ?? 'Unavailable'}
                  </span>
                </header>
                {analyticsError && <p className="analytics-error" role="alert">{analyticsError}</p>}
                {analyticsLoading ? (
                  <p className="analytics-empty" role="status">Loading cached district and constituency summaries…</p>
                ) : !analyticsData ? (
                  <p className="analytics-empty">Unavailable: {analyticsError ?? 'the cached analytics endpoint did not return results.'}</p>
                ) : (
                  <>
                    <p className="analytics-provenance">
                      Summer {analyticsData.season_year} cached values · 1 km analysis grid. Green cover is represented by mean NDVI as a greenness proxy, not a measured percent of land cover. Air temperature appears as regional context only.
                    </p>
                    <article className="panel analytics-table-panel">
                      <header>
                        <div>
                          <span className="panel-kicker">SORTABLE TABLE</span>
                          <h3>Districts and constituencies</h3>
                        </div>
                        <span className="status-pill">{sortedAnalyticsRows.length} cached regions</span>
                      </header>
                      <div className="analytics-table-scroll">
                        <table className="analytics-table" aria-label="Cached environmental metrics by district and constituency">
                          <thead>
                            <tr>
                              <th aria-sort={analyticsSort.key === 'region_name' ? analyticsSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
                                <button type="button" onClick={() => sortAnalyticsBy('region_name')}>Area</button>
                              </th>
                              <th aria-sort={analyticsSort.key === 'region_type' ? analyticsSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
                                <button type="button" onClick={() => sortAnalyticsBy('region_type')}>Type</button>
                              </th>
                              <th aria-sort={analyticsSort.key === 'lst_mean_c' ? analyticsSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
                                <button type="button" onClick={() => sortAnalyticsBy('lst_mean_c')}>Mean LST</button>
                              </th>
                              <th aria-sort={analyticsSort.key === 'population_estimated_2025' ? analyticsSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
                                <button type="button" onClick={() => sortAnalyticsBy('population_estimated_2025')}>Population</button>
                              </th>
                              <th aria-sort={analyticsSort.key === 'ndvi_mean' ? analyticsSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
                                <button type="button" onClick={() => sortAnalyticsBy('ndvi_mean')}>Green cover (NDVI proxy)</button>
                              </th>
                              <th aria-sort={analyticsSort.key === 'lst_coverage_percent' ? analyticsSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
                                <button type="button" onClick={() => sortAnalyticsBy('lst_coverage_percent')}>LST coverage</button>
                              </th>
                              <th>Air temperature (context only)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sortedAnalyticsRows.map((item) => {
                              const resolution = item.resolution_m == null
                                ? 'resolution unavailable'
                                : `${item.resolution_m} m analysis grid`
                              const dates = item.composite_start && item.composite_end
                                ? `${item.composite_start} to ${item.composite_end}`
                                : 'composite dates unavailable'
                              const weatherDates = item.air_temperature_start_date && item.air_temperature_end_date
                                ? `${item.air_temperature_start_date} to ${item.air_temperature_end_date}`
                                : 'weather dates unavailable'
                              const weatherReference = item.region_type === 'district'
                                ? `${item.region_name} district reference point`
                                : `${item.district_name} district reference point; shared context, not constituency-specific`
                              return (
                                <tr key={item.region_id} data-status={item.data_status}>
                                  <td>
                                    <strong>{item.region_name}</strong>
                                    <small>{item.region_type === 'district' ? 'Tamil Nadu ADM2 district' : `Constituency · ${item.district_name}`}</small>
                                  </td>
                                  <td>{item.region_type}</td>
                                  <td>
                                    <strong>{item.lst_mean_c == null ? 'Unavailable' : formatTemperature(item.lst_mean_c, dashboardSettings.temperatureUnit)}</strong>
                                    <small>{item.lst_mean_c == null ? `Unavailable: ${item.lst_reason}` : `${analyticsData.lst_source} · ${resolution} · ${dates}`}</small>
                                  </td>
                                  <td>
                                    <strong>{item.population_estimated_2025 == null ? 'Unavailable' : formatNumber(item.population_estimated_2025, 0)}</strong>
                                    <small>{item.population_estimated_2025 == null ? `Unavailable: ${item.population_reason}` : `${analyticsData.population_source} · ${resolution} · model year 2025`}</small>
                                  </td>
                                  <td>
                                    <strong>{item.ndvi_mean == null ? 'Unavailable' : formatNumber(item.ndvi_mean, 3)}</strong>
                                    <small>{item.ndvi_mean == null ? `Unavailable: ${item.ndvi_reason}` : `${analyticsData.ndvi_source} · ${resolution} · ${dates}`}</small>
                                  </td>
                                  <td>
                                    <strong>{item.lst_coverage_percent == null ? 'Unavailable' : `${formatNumber(item.lst_coverage_percent)}%`}</strong>
                                    <small>{item.lst_coverage_percent == null ? `Unavailable: ${item.lst_reason ?? 'cell counts are unavailable'}` : `Valid LST cells / cached cells · ${analyticsData.lst_source} · ${resolution} · ${dates}`}</small>
                                  </td>
                                  <td>
                                    <strong>{item.air_temperature_mean_c == null ? 'Unavailable' : formatTemperature(item.air_temperature_mean_c, dashboardSettings.temperatureUnit)}</strong>
                                    <small>
                                      {item.air_temperature_mean_c == null
                                        ? `Unavailable: ${item.air_temperature_reason ?? 'district-reference temperature is not available'}`
                                        : `${analyticsData.air_temperature_source} · ${weatherReference} · ${weatherDates}`}
                                    </small>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </article>

                    <article className="panel analytics-comparison-panel">
                      <header>
                        <div>
                          <span className="panel-kicker">SIDE-BY-SIDE</span>
                          <h3>Compare districts</h3>
                        </div>
                      </header>
                      <div className="analytics-comparison-selectors">
                        {[0, 1].map((slot) => (
                          <label key={slot}>
                            District {slot === 0 ? 'A' : 'B'}
                            <select
                              value={(slot === 0 ? compareDistrictA : compareDistrictB)?.region_id ?? ''}
                              onChange={(event) => {
                                const id = event.target.value
                                setCompareDistrictIds((current): [string, string] => (
                                  slot === 0 ? [id, current[1]] : [current[0], id]
                                ))
                              }}
                            >
                              {analyticsDistricts.map((district) => (
                                <option key={district.region_id} value={district.region_id}>{district.region_name}</option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>
                      <div className="analytics-comparison-grid">
                        {[compareDistrictA, compareDistrictB].map((district, index) => {
                          if (!district) return null
                          const resolution = district.resolution_m == null
                            ? 'resolution unavailable'
                            : `${district.resolution_m} m analysis grid`
                          const dates = district.composite_start && district.composite_end
                            ? `${district.composite_start} to ${district.composite_end}`
                            : 'composite dates unavailable'
                          return (
                            <section className="analytics-district-card" key={`${index}-${district.region_id}`}>
                              <h4>{district.region_name}</h4>
                              <dl>
                                <AnalyticsValue
                                  label="Mean LST"
                                  value={district.lst_mean_c == null ? null : formatTemperature(district.lst_mean_c, dashboardSettings.temperatureUnit)}
                                  metadata={`${analyticsData.lst_source} · ${resolution} · ${dates}`}
                                  reason={district.lst_reason}
                                />
                                <AnalyticsValue
                                  label="Population"
                                  value={district.population_estimated_2025 == null ? null : formatNumber(district.population_estimated_2025, 0)}
                                  metadata={`${analyticsData.population_source} · ${resolution} · model year 2025`}
                                  reason={district.population_reason}
                                />
                                <AnalyticsValue
                                  label="Green cover (NDVI proxy)"
                                  value={district.ndvi_mean == null ? null : formatNumber(district.ndvi_mean, 3)}
                                  metadata={`${analyticsData.ndvi_source} · ${resolution} · ${dates}`}
                                  reason={district.ndvi_reason}
                                />
                                <AnalyticsValue
                                  label="Air temperature context only"
                                  value={district.air_temperature_mean_c == null ? null : formatTemperature(district.air_temperature_mean_c, dashboardSettings.temperatureUnit)}
                                  metadata={`${analyticsData.air_temperature_source} · district reference point, not an area average · ${district.air_temperature_start_date ?? 'date unavailable'} to ${district.air_temperature_end_date ?? 'date unavailable'}`}
                                  reason={district.air_temperature_reason}
                                />
                              </dl>
                            </section>
                          )
                        })}
                      </div>
                    </article>

                    <article className="panel analytics-trend-panel">
                      <header>
                        <div>
                          <span className="panel-kicker">CACHED COMPOSITE HISTORY</span>
                          <h3>Temperature trend</h3>
                        </div>
                        <label className="analytics-trend-select">
                          District
                          <select
                            value={trendDistrict?.region_id ?? ''}
                            onChange={(event) => setTrendDistrictId(event.target.value)}
                          >
                            {analyticsDistricts.map((district) => (
                              <option key={district.region_id} value={district.region_id}>{district.region_name}</option>
                            ))}
                          </select>
                        </label>
                      </header>
                      {trendDistrict?.lst_mean_c == null ? (
                        <p className="analytics-empty">
                          Unavailable: {trendDistrict?.lst_reason ?? 'no cached composite is available for this district.'}
                        </p>
                      ) : (
                        <>
                          <div className="analytics-trend-chart" role="img" aria-label={`Cached seasonal LST composite for ${trendDistrict.region_name}`}>
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={[{
                                period: `${trendDistrict.composite_start ?? 'Date unavailable'} to ${trendDistrict.composite_end ?? 'Date unavailable'}`,
                                lst: convertTemperature(trendDistrict.lst_mean_c, dashboardSettings.temperatureUnit),
                              }]} margin={{ top: 14, right: 22, bottom: 14, left: 8 }}>
                                <CartesianGrid stroke="rgba(169, 227, 187, .12)" />
                                <XAxis dataKey="period" tick={{ fill: 'rgba(224, 237, 228, .6)', fontSize: 10 }} />
                                <YAxis unit={` °${dashboardSettings.temperatureUnit}`} tick={{ fill: 'rgba(224, 237, 228, .6)', fontSize: 10 }} />
                                <Tooltip
                                  contentStyle={{ background: '#10291f', border: '1px solid rgba(143, 202, 163, .25)', color: '#edf7ef' }}
                                  formatter={(value) => [`${formatNumber(Number(value))} °${dashboardSettings.temperatureUnit}`, 'Mean LST']}
                                />
                                <Line type="monotone" dataKey="lst" name="Mean LST" stroke="#f5cb70" strokeWidth={2} dot={{ r: 5, fill: '#f5cb70' }} />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                          <p className="analytics-trend-note">
                            One cached April–June seasonal composite is available for {trendDistrict.region_name}: {analyticsData.lst_source} · {trendDistrict.resolution_m ?? 'Resolution unavailable'} m grid · {trendDistrict.composite_start} to {trendDistrict.composite_end}. It is a dated summary, not a monthly trend.
                          </p>
                          <div className="analytics-monthly-gaps" aria-label="Monthly composite availability">
                            {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map((month) => (
                              <div key={month}>
                                <strong>{month} {analyticsData.season_year}</strong>
                                <small>
                                  {['Apr', 'May', 'Jun'].includes(month)
                                    ? 'No monthly data: only an Apr–Jun seasonal composite is cached.'
                                    : 'Unavailable: no month-specific composite is cached.'}
                                </small>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </article>
                  </>
                )}
              </section>
            )}
            {active === 'priorities' && (
              <section className="priorities-page" aria-label="Priorities and budget allocator">
                <header className="panel analytics-page-header">
                  <div>
                    <span className="panel-kicker">TRANSPARENT, CACHED-DATA RANKING</span>
                    <h2>Constituency priorities & budget</h2>
                  </div>
                  <span className="status-pill">
                    {prioritiesLoading ? 'Loading cached data' : prioritiesData?.data_status ?? 'Unavailable'}
                  </span>
                </header>
                {prioritiesError && <p className="analytics-error" role="alert">{prioritiesError}</p>}
                {prioritiesLoading ? (
                  <p className="analytics-empty" role="status">Loading cached LST, population and NDVI summaries…</p>
                ) : !prioritiesData ? (
                  <p className="analytics-empty">Unavailable: {prioritiesError ?? 'the cached priorities endpoint did not return results.'}</p>
                ) : (
                  <>
                    <div className="priorities-method panel">
                      <span className="panel-kicker">FORMULA · DERIVED SCORE, NOT A MEASURED VALUE</span>
                      <strong>{prioritiesData.formula}</strong>
                      <p>
                        Heat: {prioritiesData.heat_exposure_method} Population: {prioritiesData.population_method}
                        {' '}Green cover uses a bounded NDVI greenness proxy, not measured percent land cover.
                        {' '}{prioritiesData.low_green_method}
                      </p>
                      <small>
                        Inputs: LST — {prioritiesData.lst_source}; population — {prioritiesData.population_source};
                        {' '}NDVI — {prioritiesData.ndvi_source}. Values are from the cached {prioritiesData.season_year}
                        {' '}seasonal composite / population model year 2025. Grid resolution and composite dates are shown per constituency.
                      </small>
                    </div>
                    <div className="priorities-budget-controls panel">
                      <label>
                        Total budget (user-entered)
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={budgetAmount}
                          onChange={(event) => setBudgetAmount(event.target.value)}
                          placeholder="Enter total budget"
                          aria-label="Total budget"
                        />
                      </label>
                      <label>
                        Number of top priorities
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={priorityTopCount}
                          onChange={(event) => setPriorityTopCount(event.target.value)}
                          aria-label="Number of top priorities"
                        />
                      </label>
                      <button
                        type="button"
                        onClick={exportPriorityCsv}
                        disabled={prioritiesData.priorities.length === 0}
                      >
                        Export CSV
                      </button>
                    </div>
                    <p className="priorities-allocation-method">
                      Allocation method: split the entered total among the top score-available constituencies in proportion to their priority scores
                      {' '}({`allocation = total budget × constituency score ÷ sum of selected scores`}). User-entered intervention costs are recorded but are not used to calculate this split.
                    </p>
                    <article className="panel priorities-table-panel">
                      <header>
                        <div>
                          <span className="panel-kicker">RANKED CONSTITUENCY TABLE</span>
                          <h3>Priority inputs, optional costs and allocations</h3>
                        </div>
                        <span className="status-pill">{prioritiesData.priorities.length} constituencies</span>
                      </header>
                      <div className="priorities-table-scroll">
                        <table className="priorities-table" aria-label="Constituency priority scores and budget allocation">
                          <thead>
                            <tr>
                              <th>Priority</th>
                              <th>Heat exposure · LST</th>
                              <th>Population</th>
                              <th>Low-green proxy · NDVI</th>
                              <th>Intervention</th>
                              <th>User-entered cost</th>
                              <th>Budget allocation</th>
                            </tr>
                          </thead>
                          <tbody>
                            {prioritiesData.priorities.map((item, index) => {
                              const resolution = item.resolution_m == null
                                ? 'resolution unavailable'
                                : `${item.resolution_m} m analysis grid`
                              const dates = item.composite_start && item.composite_end
                                ? `${item.composite_start} to ${item.composite_end}`
                                : 'composite dates unavailable'
                              const input = interventionInputs[item.constituency_id] ?? { type: '', cost: '' }
                              const changeInput = (field: keyof InterventionInput, value: string) => {
                                setInterventionInputs((current) => ({
                                  ...current,
                                  [item.constituency_id]: { ...input, [field]: value },
                                }))
                              }
                              const allocation = priorityAllocations.get(item.constituency_id)
                              return (
                                <tr key={item.constituency_id} data-status={item.data_status}>
                                  <td>
                                    <strong>{index + 1}. {item.constituency_name}</strong>
                                    <small>{item.district_name}</small>
                                    <b>{item.priority_score == null ? 'Unavailable' : formatNumber(item.priority_score, 3)}</b>
                                    <small>
                                      {item.priority_score == null
                                        ? `Unavailable: ${item.priority_reason ?? 'one or more required inputs are missing.'}`
                                        : `Derived score · ${prioritiesData.lst_source} + ${prioritiesData.population_source} + ${prioritiesData.ndvi_source} · ${resolution} · ${dates}`}
                                    </small>
                                  </td>
                                  <td>
                                    {item.lst_mean_c == null ? 'Unavailable' : formatTemperature(item.lst_mean_c, dashboardSettings.temperatureUnit)}
                                    <small>
                                      {item.lst_mean_c == null
                                        ? `Unavailable: ${item.lst_reason ?? 'cached LST unavailable.'}`
                                        : `${prioritiesData.lst_source} · ${resolution} · ${dates}; heat percentile ${formatNumber((item.heat_exposure_percentile ?? 0) * 100, 1)}%`}
                                    </small>
                                  </td>
                                  <td>
                                    {item.population_estimated_2025 == null ? 'Unavailable' : formatNumber(item.population_estimated_2025, 0)}
                                    <small>
                                      {item.population_estimated_2025 == null
                                        ? `Unavailable: ${item.population_reason ?? 'cached population unavailable.'}`
                                        : `${prioritiesData.population_source} · ${resolution} · model year 2025; relative weight ${formatNumber(item.population_weight, 3)}`}
                                    </small>
                                  </td>
                                  <td>
                                    {item.ndvi_mean == null ? 'Unavailable' : formatNumber(item.ndvi_mean, 3)}
                                    <small>
                                      {item.ndvi_mean == null
                                        ? `Unavailable: ${item.ndvi_reason ?? 'cached NDVI unavailable.'}`
                                        : `${prioritiesData.ndvi_source} · ${resolution} · ${dates}; low-green proxy ${formatNumber(item.low_green_score, 3)}`}
                                    </small>
                                  </td>
                                  <td>
                                    <select
                                      value={input.type}
                                      onChange={(event) => changeInput('type', event.target.value)}
                                      aria-label={`Intervention for ${item.constituency_name}`}
                                    >
                                      <option value="">Choose intervention</option>
                                      <option value="Tree planting">Tree planting</option>
                                      <option value="Cool roofs">Cool roofs</option>
                                      <option value="Shade">Shade</option>
                                      <option value="Water bodies">Water bodies</option>
                                    </select>
                                    <small>User-selected; no external source, resolution or date.</small>
                                  </td>
                                  <td>
                                    <input
                                      type="number"
                                      min="0"
                                      step="any"
                                      value={input.cost}
                                      onChange={(event) => changeInput('cost', event.target.value)}
                                      aria-label={`User-entered cost for ${item.constituency_name}`}
                                      placeholder="Leave blank"
                                    />
                                    <small>User-entered cost; no cost is assumed or generated.</small>
                                  </td>
                                  <td>
                                    {allocation == null ? 'No allocation' : formatNumber(allocation, 2)}
                                    <small>
                                      {allocation == null
                                        ? 'Enter a total budget and select a positive top-priority count.'
                                        : `User-entered total · score-proportional split · ${resolution} · ${dates}`}
                                    </small>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </article>
                  </>
                )}
              </section>
            )}
            {active === 'reports' && (
              <section className="reports-page" aria-label="Cached reports and data methods">
                <header className="panel analytics-page-header">
                  <div>
                    <span className="panel-kicker">CACHED-DATA REPORTING</span>
                    <h2>Reports & methods</h2>
                  </div>
                  <span className="status-pill">
                    {summaryLoading || satelliteSummaryLoading || analyticsLoading
                      ? 'Loading cached data'
                      : summary?.data_status ?? 'Partial / unavailable'}
                  </span>
                </header>
                <p className="analytics-provenance">
                  Choose a district or constituency with the Region and Constituency selectors above.
                  Reports use only cached dashboard summaries and cached boundary geometry; live weather and remote basemap tiles are not included.
                </p>
                {summaryLoading || satelliteSummaryLoading || analyticsLoading ? (
                  <p className="analytics-empty" role="status">Loading cached report inputs…</p>
                ) : (
                  <article className="panel report-print" aria-label={`${reportTitle} cached report`}>
                    <header className="report-print-header">
                      <div>
                        <span className="panel-kicker">ECOTHERM · CACHED EVIDENCE</span>
                        <h2>{reportTitle} — Environmental report</h2>
                        <p>
                          {reportCompositeStart && reportCompositeEnd
                            ? `Cached composite: ${reportCompositeStart} to ${reportCompositeEnd}`
                            : 'Unavailable: composite dates were not returned for this selection.'}
                          {' '}· Population model year 2025
                        </p>
                      </div>
                      <button
                        className="report-print-button"
                        type="button"
                        onClick={() => window.print()}
                      >
                        Print / Save as PDF
                      </button>
                    </header>
                    <div className="report-layout">
                      <section className="report-map-panel">
                        <h3>Map snapshot</h3>
                        <ReportMapSnapshot features={reportFeatures} />
                        <p>
                          Boundary-only snapshot from cached geometry; no live imagery or street tiles.
                          {' '}Source: {constituencyId
                            ? constituencyCollection?.source ?? 'Unavailable: constituency boundary source is not loaded.'
                            : reportDistrictId
                              ? districtCollection?.source ?? 'Unavailable: district boundary source is not loaded.'
                              : districtCollection?.source ?? 'Unavailable: district boundary source is not loaded.'}
                          {' '}· Licence: {constituencyId
                            ? constituencyCollection?.license ?? 'not recorded in the loaded cache'
                            : reportDistrictId
                              ? districtCollection?.license ?? 'not recorded in the loaded cache'
                              : districtCollection?.license ?? 'not recorded in the loaded cache'}
                        </p>
                      </section>
                      <section className="report-metrics-panel">
                        <h3>Key numbers</h3>
                        <dl>
                          <AnalyticsValue
                            label="Mean land-surface temperature"
                            value={reportLstMean == null ? null : formatTemperature(reportLstMean, dashboardSettings.temperatureUnit)}
                            metadata={`${analyticsData?.lst_source ?? satelliteSummary?.lst_source ?? 'Landsat source unavailable'} · ${reportGridResolution ?? 'resolution not recorded'} m analysis grid · ${reportCompositeStart ?? 'date unavailable'} to ${reportCompositeEnd ?? 'date unavailable'}`}
                            reason={
                              reportAnalyticsRegion?.lst_reason
                              ?? (summary
                                ? `No cached LST mean returned${summary.unavailable_metrics.length ? ` (${summary.unavailable_metrics.join(', ')} marked unavailable)` : ''}.`
                                : 'No cached dashboard summary was returned for this selection.')
                            }
                          />
                          <AnalyticsValue
                            label="LST valid-cell coverage"
                            value={(reportAnalyticsRegion?.lst_coverage_percent ?? summary?.lst_coverage_percent) == null ? null : `${formatNumber(reportAnalyticsRegion?.lst_coverage_percent ?? summary?.lst_coverage_percent)}%`}
                            metadata={`${analyticsData?.lst_source ?? satelliteSummary?.lst_source ?? 'Landsat source unavailable'} · ${reportGridResolution ?? 'resolution not recorded'} m analysis grid · ${reportCompositeStart ?? 'date unavailable'} to ${reportCompositeEnd ?? 'date unavailable'}`}
                            reason={reportAnalyticsRegion?.lst_reason ?? (summary ? 'Cached LST coverage is not available for this selection.' : 'No cached dashboard summary was returned.')}
                          />
                          <AnalyticsValue
                            label="Population"
                            value={reportPopulation == null ? null : formatNumber(reportPopulation, 0)}
                            metadata={`${analyticsData?.population_source ?? 'WorldPop 2025 modelled estimate'} · approximately 100 m native support, aggregated to ${reportGridResolution ?? 'unrecorded'} m grid · model year 2025`}
                            reason={reportAnalyticsRegion?.population_reason ?? (summary ? 'No cached WorldPop estimate is available for this selection.' : 'No cached dashboard summary was returned.')}
                          />
                          <AnalyticsValue
                            label="Population coverage"
                            value={summary?.population_coverage_percent == null
                              ? null
                              : `${formatNumber(summary.population_coverage_percent)}%`}
                            metadata={`${analyticsData?.population_source ?? 'WorldPop 2025'} · ${reportGridResolution ?? 'unrecorded'} m analysis grid · model year 2025`}
                            reason={reportAnalyticsRegion?.population_reason ?? (summary ? 'Cached population coverage is not available for this selection.' : 'No cached dashboard summary was returned.')}
                          />
                          <AnalyticsValue
                            label="Mean NDVI (greenness proxy)"
                            value={reportNdvi == null ? null : formatNumber(reportNdvi, 3)}
                            metadata={`${analyticsData?.ndvi_source ?? satelliteSummary?.optical_source ?? 'Sentinel-2 source unavailable'} · ${reportGridResolution ?? 'resolution not recorded'} m analysis grid · ${reportCompositeStart ?? 'date unavailable'} to ${reportCompositeEnd ?? 'date unavailable'}`}
                            reason={
                              reportAnalyticsRegion?.ndvi_reason
                              ?? (satelliteSummary
                                ? 'No valid cached NDVI cells were returned for this selection.'
                                : satelliteSummaryError ?? 'No cached satellite summary was returned.')
                            }
                          />
                          <AnalyticsValue
                            label="Air temperature (regional context only)"
                            value={reportWeather == null ? null : formatTemperature(reportWeather, dashboardSettings.temperatureUnit)}
                            metadata={`${analyticsData?.air_temperature_source ?? 'Open-Meteo'} ${reportAnalyticsRegion?.air_temperature_model ?? summary?.weather_model ?? 'ERA5-Land'} · approximately 0.1° / 11 km · ${reportAnalyticsRegion?.air_temperature_start_date ?? summary?.weather_start_date ?? 'date unavailable'} to ${reportAnalyticsRegion?.air_temperature_end_date ?? summary?.weather_end_date ?? 'date unavailable'}`}
                            reason={reportAnalyticsRegion?.air_temperature_reason ?? (summary ? 'No cached regional weather value is available for this selection.' : 'No cached dashboard summary was returned.')}
                          />
                        </dl>
                      </section>
                    </div>
                    <section className="report-limitations">
                      <h3>Limits and interpretation</h3>
                      <ul>
                        <li>LST is a Landsat surface-temperature estimate, not air temperature; cloud masks, retrieval errors and missing thermal observations remain.</li>
                        <li>All raster metrics use the cached 1 km analysis grid; Landsat thermal support is approximately 100 m and NDVI optical bands have finer native sampling, neither is made more detailed by aggregation.</li>
                        <li>WorldPop is a modelled 2025 population estimate, not a census or live count. NDVI is a vegetation-greenness index, not percent green cover.</li>
                        <li>Open-Meteo ERA5-Land is regional reanalysis context, not a station measurement or a constituency-scale observation.</li>
                        <li>Only the cached April–June 2026 seasonal composite is available; it is not a monthly trend or a future forecast. Cache refresh timestamps are not present in the report API.</li>
                      </ul>
                    </section>
                    <section className="report-source-notes">
                      <h3>Report provenance</h3>
                      <p>
                        Landsat: {satelliteSummary?.lst_source ?? 'Unavailable: source metadata unavailable'} ·
                        {' '}Sentinel-2: {satelliteSummary?.optical_source ?? 'Unavailable: source metadata unavailable'} ·
                        {' '}WorldPop: 2025 gridded model · Open-Meteo: cached {summary?.weather_model ?? 'Unavailable: regional model unavailable'}.
                      </p>
                      <p>
                        Grid resolution: {reportGridResolution ?? 'Unavailable'} m ·
                        {' '}Composite date: {reportCompositeStart ?? 'Unavailable'} to {reportCompositeEnd ?? 'Unavailable'} ·
                        {' '}population model year: 2025.
                      </p>
                    </section>
                  </article>
                )}
                <article className="panel methods-panel">
                  <header>
                    <div>
                      <span className="panel-kicker">ATTRIBUTION · LICENCE · VERSION</span>
                      <h3>Methods and data-source register</h3>
                    </div>
                  </header>
                  <div className="methods-table-scroll">
                    <table className="methods-table" aria-label="Data sources, licences, versions and limitations">
                      <thead>
                        <tr>
                          <th>Dataset / source</th>
                          <th>Version / date</th>
                          <th>Licence / attribution</th>
                          <th>Resolution / support</th>
                          <th>Method and limits</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Assembly constituency boundaries · DataMeet India community</td>
                          <td>{constituencyCollection?.delimitation_year ?? '2008 (cached boundary manifest)'} delimitation</td>
                          <td>{constituencyCollection?.license ?? 'CC BY 4.0'}</td>
                          <td>Vector boundaries; not a raster measurement</td>
                          <td>{constituencyCollection?.source_reference ?? 'DataMeet India community, github.com/datameet/maps'}; district assignment by largest overlap.</td>
                        </tr>
                        <tr>
                          <td>District boundaries · Pathways Data Pvt. Ltd. / LGDirectory</td>
                          <td>{districtCollection?.boundary_year ?? 'Unavailable: boundary year not loaded'}</td>
                          <td>{districtCollection?.license ?? 'Unavailable: licence metadata not loaded'}</td>
                          <td>Vector boundaries; not a raster measurement</td>
                          <td>{districtCollection?.source ?? 'Cached source metadata unavailable'}; use boundary outlines for geography only.</td>
                        </tr>
                        <tr>
                          <td>Landsat 8/9 land-surface temperature</td>
                          <td>Collection 2 Level 2 L2SP; cached composite dates shown per report</td>
                          <td>USGS attribution; exact licence text is not stored in the local cache manifest</td>
                          <td>Thermal sensor support approximately 100 m; ECOTHERM analysis grid 1 km</td>
                          <td>ST_B10; QA-masked seasonal median. Resampling and aggregation do not add native detail; surface temperature is not air temperature.</td>
                        </tr>
                        <tr>
                          <td>Sentinel-2 optical indices</td>
                          <td>COPERNICUS/S2_SR_HARMONIZED Level-2A; cached composite dates shown per report</td>
                          <td>Copernicus / ESA attribution; exact licence text is not stored in the local cache manifest</td>
                          <td>B8/B4 NDVI native 10 m; ECOTHERM analysis grid 1 km</td>
                          <td>Cloud/quality masked seasonal optical indices. NDVI is greenness proxy; Sentinel-2 is not a thermal source.</td>
                        </tr>
                        <tr>
                          <td>WorldPop 2025 population</td>
                          <td>WorldPop/GP/100m/R2025A/v1/pop; model year 2025</td>
                          <td>CC BY 4.0; attribute WorldPop</td>
                          <td>Approximately 100 m at equator; aggregated to ECOTHERM 1 km grid</td>
                          <td>Modelled population estimate, not census or live count; coverage gaps remain visible.</td>
                        </tr>
                        <tr>
                          <td>Open-Meteo Historical Weather API · ERA5-Land</td>
                          <td>Archive API; cached dates shown per report; model ERA5-Land</td>
                          <td>CC BY 4.0 attribution; free-service use is subject to provider terms</td>
                          <td>Approximately 0.1° / 11 km; regional reanalysis context</td>
                          <td>Not a station observation or local 1 km weather measurement; missing values are not converted to zero.</td>
                        </tr>
                        <tr>
                          <td>Esri World Imagery basemap</td>
                          <td>ArcGIS World_Imagery MapServer; service version/date not pinned in cache</td>
                          <td>Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community; follow Esri service terms</td>
                          <td>Remote tiled imagery; scale varies by location and zoom</td>
                          <td>Not embedded in cached reports; the report map snapshot uses only cached vector boundaries.</td>
                        </tr>
                        <tr>
                          <td>OpenStreetMap streets / Geofabrik Southern Zone extract</td>
                          <td>Latest extract; processing metadata and extract fingerprint are recorded in the local cache</td>
                          <td>© OpenStreetMap contributors; ODbL 1.0</td>
                          <td>Vector data; mapped-feature completeness varies</td>
                          <td>Mapped features are not a complete real-world inventory. Report map snapshot does not request external tiles.</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p className="methods-source-note">
                    Local cached output timestamps are not available through the report endpoint; source periods, model years and recorded source versions above are shown instead. Review current provider terms before redistribution or commercial use.
                  </p>
                </article>
              </section>
            )}
            {active === 'settings' && (
              <section className="settings-page" aria-label="Dashboard settings and about">
                <header className="panel analytics-page-header">
                  <div>
                    <span className="panel-kicker">LOCAL DASHBOARD PREFERENCES</span>
                    <h2>Settings</h2>
                  </div>
                  <span className="status-pill">Saved in this browser</span>
                </header>
                {settingsError && <p className="analytics-error" role="alert">{settingsError}</p>}
                <article className="panel settings-controls">
                  <label>
                    Heat Map Explorer basemap
                    <select
                      value={dashboardSettings.basemapPreference}
                      onChange={(event) => {
                        const value = event.target.value
                        if (value !== 'street' && value !== 'satellite') return
                        updateDashboardSettings({ basemapPreference: value })
                      }}
                    >
                      <option value="street">OpenStreetMap streets</option>
                      <option value="satellite">Esri World Imagery</option>
                    </select>
                    <small>Satellite Analysis always opens on imagery as designed.</small>
                  </label>
                  <label>
                    Temperature display units
                    <select
                      value={dashboardSettings.temperatureUnit}
                      onChange={(event) => {
                        const value = event.target.value
                        if (value === 'C' || value === 'F') {
                          updateDashboardSettings({ temperatureUnit: value })
                        }
                      }}
                    >
                      <option value="C">Celsius (°C)</option>
                      <option value="F">Fahrenheit (°F)</option>
                    </select>
                    <small>Applied to displayed temperature values; stored source data remains in Celsius.</small>
                  </label>
                  <label>
                    Default region
                    <select
                      value={dashboardSettings.defaultRegion}
                      onChange={(event) => {
                        updateDashboardSettings({ defaultRegion: event.target.value })
                        setConstituencyId(null)
                      }}
                    >
                      {regions.map((item) => (
                        <option key={item.id} value={item.id}>{item.name}</option>
                      ))}
                    </select>
                    <small>Applied immediately and restored when this dashboard opens.</small>
                  </label>
                  <label>
                    Preferred analysis resolution
                    <select
                      value={dashboardSettings.resolutionPreferenceM}
                      onChange={(event) => {
                        const value = Number(event.target.value)
                        if (value === 100 || value === 1000) {
                          updateDashboardSettings({ resolutionPreferenceM: value })
                        }
                      }}
                    >
                      <option value={1000}>1 km</option>
                      <option value={100}>100 m</option>
                    </select>
                    <small>
                      Preference only. Cached Tamil Nadu, district and constituency summaries use a 1 km grid; choosing 100 m does not create finer cached data.
                    </small>
                  </label>
                </article>
                <article className="panel settings-datasets">
                  <header>
                    <div>
                      <span className="panel-kicker">CACHE FRESHNESS</span>
                      <h3>Dataset update information</h3>
                    </div>
                  </header>
                  <div className="settings-update-list">
                    <div>
                      <strong>Landsat LST</strong>
                      <span>Cache update timestamp not recorded in the local source manifest.</span>
                      <small>
                        {reportCompositeStart && reportCompositeEnd
                          ? `Composite period: ${reportCompositeStart} to ${reportCompositeEnd}`
                          : 'Source composite date range is not present in the cached response.'}
                      </small>
                    </div>
                    <div>
                      <strong>Sentinel-2 NDVI / NDBI / NDWI</strong>
                      <span>Cache update timestamp not recorded in the local source manifest.</span>
                      <small>
                        {reportCompositeStart && reportCompositeEnd
                          ? `Composite period: ${reportCompositeStart} to ${reportCompositeEnd}`
                          : 'Source composite date range is not present in the cached response.'}
                      </small>
                    </div>
                    <div>
                      <strong>WorldPop population</strong>
                      <span>Cache update timestamp not recorded in the local source manifest.</span>
                      <small>Model year: 2025 · 2025 is the source year, not a cache-update date.</small>
                    </div>
                    <div>
                      <strong>District / constituency boundaries</strong>
                      <span>Manifest update timestamp is not recorded for these boundaries.</span>
                      <small>
                        District boundary year: {districtCollection?.boundary_year ?? 'Boundary year not present in the loaded source manifest'}
                        {' · '}constituency delimitation: {constituencyCollection?.delimitation_year ?? '2008 cached source manifest'}.
                      </small>
                    </div>
                    <div>
                      <strong>OpenStreetMap mapped features</strong>
                      <span>
                        Last processed: {formatUpdatedDateTime(summary?.osm_processed_at_utc) ?? 'Processing timestamp not included in this response.'}
                      </span>
                      <small>Feature counts are mapped objects, not a complete infrastructure inventory.</small>
                    </div>
                    <div>
                      <strong>Open-Meteo historical ERA5-Land</strong>
                      <span>Cache update timestamp not recorded for this reanalysis output.</span>
                      <small>
                        {summary?.weather_start_date && summary.weather_end_date
                          ? `Weather period: ${summary.weather_start_date} to ${summary.weather_end_date} · ERA5-Land 0.1° (~11 km) model grid`
                          : 'Cached reanalysis period is not returned for this selection.'}
                      </small>
                    </div>
                    <div>
                      <strong>Open-Meteo live weather</strong>
                      <span>
                        {formatUpdatedDateTime(selectedLiveWeather?.updated_at_utc)
                          ? `Last response update: ${formatUpdatedDateTime(selectedLiveWeather?.updated_at_utc)}`
                          : 'Select a district or constituency to request live weather.'}
                      </span>
                      <small>{selectedLiveWeather?.provider ?? 'Open-Meteo Forecast API'} · live/stale status and the source timestamp are shown after refresh.</small>
                    </div>
                    <div>
                      <strong>Esri World Imagery</strong>
                      <span>Remote tile service; no cached last-updated date is available.</span>
                      <small>Attribution is shown in the map. Imagery is not embedded in cached reports.</small>
                    </div>
                  </div>
                  <div className="settings-weather-refresh">
                    <button
                      type="button"
                      disabled={!region.startsWith('district_') && constituencyId === null}
                      onClick={() => {
                        setWeatherRefreshStatus('Refreshing live weather…')
                        setWeatherRefreshToken((current) => current + 1)
                      }}
                    >
                      Refresh live weather
                    </button>
                    <span role="status">
                      {weatherRefreshStatus
                        ?? (selectedLiveWeather
                          ? `${selectedLiveWeather.status}${selectedLiveWeather.error ? ` · ${selectedLiveWeather.error}` : ''}`
                          : 'Live weather refresh requires a selected district or constituency.')}
                    </span>
                    <small>Only the live weather endpoint is refreshed here; cached satellite, population and boundary datasets are not refreshed.</small>
                  </div>
                </article>
                <article className="panel about-panel">
                  <header>
                    <div>
                      <span className="panel-kicker">ABOUT ECOTHERM</span>
                      <h3>Licences and attributions</h3>
                    </div>
                  </header>
                  <ul>
                    <li>Constituency boundaries: DataMeet India community, 2008 delimitation · CC BY 4.0.</li>
                    <li>District boundaries: Pathways Data Pvt. Ltd. / LGDirectory, 2021 boundary year · Open Data Commons Open Database License 1.0.</li>
                    <li>Landsat 8/9 Collection 2 Level 2: USGS attribution; license text is not present in the local cache manifest.</li>
                    <li>Sentinel-2 SR Harmonized: Copernicus / ESA attribution; license text is not present in the local cache manifest.</li>
                    <li>WorldPop 2025 population: CC BY 4.0; modelled estimate, not a live count.</li>
                    <li>Open-Meteo Historical Weather API / ERA5-Land: CC BY 4.0 attribution and provider terms.</li>
                    <li>Esri World Imagery: Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community; follow Esri service terms.</li>
                    <li>OpenStreetMap / Geofabrik Southern Zone: © OpenStreetMap contributors; ODbL 1.0.</li>
                  </ul>
                  <p>
                    Cached model periods, native support, aggregation methods and limitations are documented on Reports & Methods. Settings are local browser preferences and do not alter or reprocess source data.
                  </p>
                </article>
              </section>
            )}
          </>
        )}
      </section>
    </main>
  )
}
