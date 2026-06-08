/* Bilingual catalog for backend-generated data-quality issue / cleaning-rule
 * strings.
 *
 * Each entry carries two voices:
 *   issue — problem noun phrase for "Issues Detected" / "Top Issues Addressed"
 *           ("Records missing z-scores")
 *   rule  — action phrase for "Rules Applied" / "Cleaning Rules Applied"
 *           ("Remove records missing z-scores")
 *
 * translateIssue() → issue voice (with EN/BM toggle)
 * translateRule()  → rule voice  (with EN/BM toggle)
 *
 * Both fall back to the English `description` string for any unmapped code,
 * so genuine rules without a catalog entry (e.g. "Dropped age over5") still
 * render rather than going blank. */

export interface IssueLike {
  code?: string | null;
  description?: string | null;
  count?: number;
  field?: string | null;
  pct?: number | null;
}

interface VoicePair { en: string; bm: string }
interface CatalogEntry { issue: VoicePair; rule: VoicePair }

const CATALOG: Record<string, CatalogEntry> = {
  // Per-column completeness (parametrised — {field}/{pct} interpolated)
  col_empty: {
    issue: { en: "Column '{field}' is {pct}% empty",        bm: "Lajur '{field}' {pct}% kosong" },
    rule:  { en: "Fill or flag empty column '{field}'",     bm: "Isi atau tandakan lajur kosong '{field}'" },
  },

  // Gender
  dropped_invalid_gender: {
    issue: { en: 'Invalid gender values',             bm: 'Nilai jantina tidak sah' },
    rule:  { en: 'Remove invalid gender values',      bm: 'Buang nilai jantina tidak sah' },
  },
  dropped_ragu_gender: {
    issue: { en: 'Ambiguous gender values',           bm: 'Nilai jantina meragukan' },
    rule:  { en: 'Remove ambiguous gender values',    bm: 'Buang nilai jantina meragukan' },
  },
  ragu_gender: {
    issue: { en: 'Ambiguous gender values flagged',   bm: 'Nilai jantina meragukan ditanda' },
    rule:  { en: 'Flag ambiguous gender values',      bm: 'Tandakan nilai jantina meragukan' },
  },
  unknown_gender: {
    issue: { en: 'Unknown gender values',             bm: 'Nilai jantina tidak diketahui' },
    rule:  { en: 'Check unknown gender values',       bm: 'Semak nilai jantina tidak diketahui' },
  },

  // Dates / age
  dropped_date_before_dob: {
    issue: { en: 'Measurements dated before birth',         bm: 'Pengukuran bertarikh sebelum lahir' },
    rule:  { en: 'Remove measurements dated before birth',  bm: 'Buang pengukuran bertarikh sebelum lahir' },
  },
  dropped_null_dob: {
    issue: { en: 'Records missing date of birth',           bm: 'Rekod tanpa tarikh lahir' },
    rule:  { en: 'Remove records missing date of birth',    bm: 'Buang rekod tanpa tarikh lahir' },
  },
  null_tarikh_lahir: {
    issue: { en: 'Records missing date of birth',           bm: 'Rekod tanpa tarikh lahir' },
    rule:  { en: 'Check records missing date of birth',     bm: 'Semak rekod tanpa tarikh lahir' },
  },
  bad_dates: {
    issue: { en: 'Invalid dates',                           bm: 'Tarikh tidak sah' },
    rule:  { en: 'Check invalid dates',                     bm: 'Semak tarikh tidak sah' },
  },
  dropped_invalid_date: {
    issue: { en: 'Invalid dates',                           bm: 'Tarikh tidak sah' },
    rule:  { en: 'Remove invalid dates',                    bm: 'Buang tarikh tidak sah' },
  },
  invalid_age: {
    issue: { en: 'Invalid age records',                     bm: 'Rekod umur tidak sah' },
    rule:  { en: 'Check invalid age records',               bm: 'Semak rekod umur tidak sah' },
  },
  dropped_age_invalid: {
    issue: { en: 'Invalid age records',                     bm: 'Rekod umur tidak sah' },
    rule:  { en: 'Remove invalid age records',              bm: 'Buang rekod umur tidak sah' },
  },
  dropped_age_over5: {
    issue: { en: 'Records with age over 5 years',           bm: 'Rekod berumur lebih 5 tahun' },
    rule:  { en: 'Remove records with age over 5 years',    bm: 'Buang rekod berumur lebih 5 tahun' },
  },

  // Measurements
  dropped_measurement_outlier: {
    issue: { en: 'Measurement outliers',              bm: 'Pencilan pengukuran' },
    rule:  { en: 'Remove measurement outliers',       bm: 'Buang pencilan pengukuran' },
  },
  dropped_bmi_outlier: {
    issue: { en: 'BMI outliers',                      bm: 'Pencilan BMI' },
    rule:  { en: 'Remove BMI outliers',               bm: 'Buang pencilan BMI' },
  },
  dropped_no_measurement: {
    issue: { en: 'Records with no measurement',       bm: 'Rekod tanpa pengukuran' },
    rule:  { en: 'Remove records with no measurement',bm: 'Buang rekod tanpa pengukuran' },
  },
  dropped_no_bmi: {
    issue: { en: 'Records with no BMI',               bm: 'Rekod tanpa BMI' },
    rule:  { en: 'Remove records with no BMI',        bm: 'Buang rekod tanpa BMI' },
  },
  dropped_null_zscore: {
    issue: { en: 'Records missing z-scores',          bm: 'Rekod tanpa z-skor' },
    rule:  { en: 'Remove records missing z-scores',   bm: 'Buang rekod tanpa z-skor' },
  },
  null_berat_original: {
    issue: { en: 'Missing weight values',             bm: 'Nilai berat hilang' },
    rule:  { en: 'Check missing weight values',       bm: 'Semak nilai berat hilang' },
  },
  null_tinggi_original: {
    issue: { en: 'Missing height values',             bm: 'Nilai tinggi hilang' },
    rule:  { en: 'Check missing height values',       bm: 'Semak nilai tinggi hilang' },
  },
  berat_out_of_range: {
    issue: { en: 'Weight out of valid range',         bm: 'Berat di luar julat sah' },
    rule:  { en: 'Check weight out of valid range',   bm: 'Semak berat di luar julat sah' },
  },
  tinggi_out_of_range: {
    issue: { en: 'Height out of valid range',         bm: 'Tinggi di luar julat sah' },
    rule:  { en: 'Check height out of valid range',   bm: 'Semak tinggi di luar julat sah' },
  },

  // Duplicates / identity
  dropped_duplicate_ic: {
    issue: { en: 'Duplicate IC records',              bm: 'Rekod IC berganda' },
    rule:  { en: 'Remove duplicate IC records',       bm: 'Buang rekod IC berganda' },
  },
  duplicate_ic: {
    issue: { en: 'Duplicate IC records',              bm: 'Rekod IC berganda' },
    rule:  { en: 'Check duplicate IC records',        bm: 'Semak rekod IC berganda' },
  },
  dropped_duplicate_id: {
    issue: { en: 'Duplicate student ID records',      bm: 'Rekod ID murid berganda' },
    rule:  { en: 'Remove duplicate student ID records', bm: 'Buang rekod ID murid berganda' },
  },
  dropped_duplicate_mykid: {
    issue: { en: 'Duplicate MyKid records',           bm: 'Rekod MyKid berganda' },
    rule:  { en: 'Remove duplicate MyKid records',    bm: 'Buang rekod MyKid berganda' },
  },

  // Cohort / income
  dropped_non_tahun_satu: {
    issue: { en: 'Non Year-One records',              bm: 'Rekod bukan Tahun Satu' },
    rule:  { en: 'Remove non Year-One records',       bm: 'Buang rekod bukan Tahun Satu' },
  },
  dropped_pendapatan_x: {
    issue: { en: 'Records with invalid income',       bm: 'Rekod pendapatan tidak sah' },
    rule:  { en: 'Remove records with invalid income',bm: 'Buang rekod pendapatan tidak sah' },
  },

  // Review
  flagged_records: {
    issue: { en: 'Records flagged for review',        bm: 'Rekod ditanda untuk semakan' },
    rule:  { en: 'Flag records for review',           bm: 'Tandakan rekod untuk semakan' },
  },
};

function interpolate(template: string, issue: IssueLike): string {
  return template
    .replace('{field}', String(issue.field ?? ''))
    .replace('{pct}', String(issue.pct ?? ''));
}

/** Localise by `code` in issue voice ("Records missing z-scores").
 *  Falls back to the English `description` for unmapped codes. */
export function translateIssue(issue: IssueLike, lang: 'en' | 'bm'): string {
  const entry = issue.code ? CATALOG[issue.code] : undefined;
  if (entry) return interpolate(lang === 'en' ? entry.issue.en : entry.issue.bm, issue);
  return issue.description ?? '';
}

/** Localise by `code` in rule/action voice ("Remove records missing z-scores").
 *  Falls back to the English `description` for unmapped codes. */
export function translateRule(issue: IssueLike, lang: 'en' | 'bm'): string {
  const entry = issue.code ? CATALOG[issue.code] : undefined;
  if (entry) return interpolate(lang === 'en' ? entry.rule.en : entry.rule.bm, issue);
  return issue.description ?? '';
}
