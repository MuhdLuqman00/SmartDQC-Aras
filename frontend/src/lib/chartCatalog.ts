/* Single source of truth for every chart block emitted by
   backend/eda/charts.py::build_chart_blocks. Add a new entry here when
   the backend grows a new block; nothing else needs to change. */

export type ChartShape =
  | 'histogram'      // { label, data: [{range, count}] }
  | 'scatter'        // { title, x_label, y_label, points: [{x, y}] }
  | 'pie_array'      // [{label, count}]
  | 'donut_object'   // { label, data: [{label, count}] }
  | 'bar_labeled'    // [{<labelKey>, count}]
  | 'trend_records'; // [{tahun_ukur, <indicator>: number}]

export type ChartHome = 'geo' | 'quality' | 'dashboard';

export interface ChartCatalogEntry {
  /** key in /charts/blocks response */
  key: string;
  titleEn: string;
  titleBm: string;
  shape: ChartShape;
  home: ChartHome;
  /** Shown by default; uncheck via "Show all" or page-specific toggle */
  recommended: boolean;
  /** For pie_array / bar_labeled — the field that holds the slice/bar label. */
  labelKey?: string;
}

export const CHART_CATALOG: ChartCatalogEntry[] = [
  // ── GeoPage "Distributions & relationships" ────────────────────────────────
  { key: 'bmi_distribution',                     titleEn: 'BMI distribution',                   titleBm: 'Taburan BMI',                       shape: 'histogram', home: 'geo', recommended: true },
  { key: 'berat_kg_distribution',                titleEn: 'Weight (kg) distribution',           titleBm: 'Taburan Berat (kg)',                shape: 'histogram', home: 'geo', recommended: true },
  { key: 'tinggi_cm_distribution',               titleEn: 'Height (cm) distribution',           titleBm: 'Taburan Tinggi (cm)',               shape: 'histogram', home: 'geo', recommended: true },
  { key: 'age_months_computed_distribution',     titleEn: 'Age (months) distribution',          titleBm: 'Taburan Umur (bulan)',              shape: 'histogram', home: 'geo', recommended: true },
  { key: 'waz_distribution',                     titleEn: 'WAZ z-score distribution',           titleBm: 'Taburan z-skor WAZ',                shape: 'histogram', home: 'geo', recommended: true },
  { key: 'haz_distribution',                     titleEn: 'HAZ z-score distribution',           titleBm: 'Taburan z-skor HAZ',                shape: 'histogram', home: 'geo', recommended: true },
  { key: 'baz_distribution',                     titleEn: 'BAZ z-score distribution',           titleBm: 'Taburan z-skor BAZ',                shape: 'histogram', home: 'geo', recommended: true },
  { key: 'scatter_berat_kg_vs_tinggi_cm',        titleEn: 'Weight vs Height',                   titleBm: 'Berat lwn Tinggi',                  shape: 'scatter',   home: 'geo', recommended: true },
  { key: 'scatter_bmi_vs_age_months_computed',   titleEn: 'BMI vs Age',                         titleBm: 'BMI lwn Umur',                      shape: 'scatter',   home: 'geo', recommended: true },
  { key: 'scatter_waz_vs_age_months_computed',   titleEn: 'WAZ vs Age',                         titleBm: 'WAZ lwn Umur',                      shape: 'scatter',   home: 'geo', recommended: true },
  { key: 'scatter_haz_vs_age_months_computed',   titleEn: 'HAZ vs Age',                         titleBm: 'HAZ lwn Umur',                      shape: 'scatter',   home: 'geo', recommended: true },
  { key: 'scatter_baz_vs_age_months_computed',   titleEn: 'BAZ vs Age',                         titleBm: 'BAZ lwn Umur',                      shape: 'scatter',   home: 'geo', recommended: true },

  // ── QualityPage "Classification breakdown" ────────────────────────────────
  { key: 'status_bmi_pie',  titleEn: 'BMI status',                     titleBm: 'Status BMI',                     shape: 'pie_array',    home: 'quality', recommended: true },
  { key: 'waz_class_pie',   titleEn: 'WAZ (Weight-for-Age) classes',   titleBm: 'Kelas WAZ (Berat-untuk-Umur)',   shape: 'donut_object', home: 'quality', recommended: true },
  { key: 'haz_class_pie',   titleEn: 'HAZ (Height-for-Age) classes',   titleBm: 'Kelas HAZ (Tinggi-untuk-Umur)',  shape: 'donut_object', home: 'quality', recommended: true },
  { key: 'baz_class_pie',   titleEn: 'BAZ (BMI-for-Age) classes',      titleBm: 'Kelas BAZ (BMI-untuk-Umur)',     shape: 'donut_object', home: 'quality', recommended: true },

  // ── DashboardPage "Population breakdown" + trend ─────────────────────────
  { key: 'trend_by_year',          titleEn: 'Indicator trend by year',  titleBm: 'Trend penunjuk mengikut tahun', shape: 'trend_records', home: 'dashboard', recommended: true },
  { key: 'gender_split',           titleEn: 'Gender split',             titleBm: 'Pecahan jantina',               shape: 'pie_array',     home: 'dashboard', recommended: true },
  { key: 'records_by_negeri',      titleEn: 'Records by state',         titleBm: 'Rekod mengikut negeri',         shape: 'bar_labeled',   home: 'dashboard', recommended: true,  labelKey: 'negeri' },
  { key: 'income_split',           titleEn: 'Income distribution',      titleBm: 'Taburan pendapatan',            shape: 'pie_array',     home: 'dashboard', recommended: true },
  { key: 'vaccine_distribution',   titleEn: 'Vaccine distribution',     titleBm: 'Taburan vaksin',                shape: 'bar_labeled',   home: 'dashboard', recommended: true,  labelKey: 'vaccine' },
];

export const catalogByHome = (home: ChartHome): ChartCatalogEntry[] =>
  CHART_CATALOG.filter(e => e.home === home);

export const catalogByKey = (key: string): ChartCatalogEntry | undefined =>
  CHART_CATALOG.find(e => e.key === key);

/* Shape-guard helpers — used by renderers and by the GeoPage "Show all"
   path so unknown payloads get skipped cleanly. */

export function isHistogramBlock(b: unknown): b is { label: string; data: { range: string; count: number }[] } {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  const obj = b as Record<string, unknown>;
  if (typeof obj.label !== 'string' || !Array.isArray(obj.data)) return false;
  const first = obj.data[0];
  return !first || (typeof first === 'object' && first !== null && 'range' in first);
}

export function isScatterBlock(b: unknown): b is { title: string; x_label: string; y_label: string; points: { x: number; y: number }[] } {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  return Array.isArray((b as Record<string, unknown>).points);
}

export function isPieArrayBlock(b: unknown): b is { label: string; count: number }[] {
  return Array.isArray(b) && b.every(item => item && typeof item === 'object' && 'label' in item && 'count' in item);
}

export function isDonutObjectBlock(b: unknown): b is { label: string; data: { label: string; count: number }[] } {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  const obj = b as Record<string, unknown>;
  if (typeof obj.label !== 'string' || !Array.isArray(obj.data)) return false;
  const first = obj.data[0] as Record<string, unknown> | undefined;
  return !first || ('label' in first && 'count' in first);
}

export function isBarLabeledBlock(b: unknown, labelKey: string): b is Record<string, unknown>[] {
  return Array.isArray(b) && b.every(item => item && typeof item === 'object' && labelKey in item && 'count' in item);
}

export function isTrendRecordsBlock(b: unknown): b is Record<string, unknown>[] {
  return Array.isArray(b) && b.every(item => item && typeof item === 'object' && 'tahun_ukur' in item);
}
