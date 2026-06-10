import React, { useEffect, useState } from 'react';
import { Save, RotateCcw, Info } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';

/* Threshold keys MUST match backend _DEFAULT_THRESHOLDS in main.py.
   Prior shape (missing_warn / duplicate_warn / outlier_zscore) didn't
   round-trip: GET returned the backend keys, save POSTed the truncated
   keys, and the next reload showed defaults again. */
interface Thresholds {
  missing_rate_warn: number;
  missing_rate_fail: number;
  duplicate_rate_warn: number;
  duplicate_rate_fail: number;
  outlier_zscore_threshold: number;
  rag_amber_tolerance: number;
  trajectory_atrisk_tolerance: number;
}

const DEFAULT_THRESHOLDS: Thresholds = {
  missing_rate_warn: 0.05,
  missing_rate_fail: 0.15,
  duplicate_rate_warn: 0.02,
  duplicate_rate_fail: 0.10,
  outlier_zscore_threshold: 3.0,
  rag_amber_tolerance: 0.20,
  trajectory_atrisk_tolerance: 0.30,
};

/* B3: registry-driven cleaning rule — the SAME rule the pipeline runs.
   source_types = the schemas that actually apply this rule (for the schema filter).
   kind: "drop" removes rows from analysis; "review" flags rows for human review. */
interface Rule {
  code: string;
  en: string; bm: string;
  desc_en: string; desc_bm: string;
  locked: boolean;
  enabled: boolean;
  source_types: string[];
  kind: 'drop' | 'review';
}

type RuleSchema = 'myvass' | 'ncdc' | 'kpm' | 'general';

/* KPI benchmark targets. Both NPAN (national policy) and WHO (clinical
   standard) targets are editable, admin-only. Labels live here; the backend
   stores only the numeric rates so a save can't corrupt them. */
type TargetSet = Record<string, number>;
interface KpiTargets {
  current: { npan: TargetSet; who: TargetSet };
  defaults: { npan: TargetSet; who: TargetSet };
  source: { npan: string; who: string };
  target_year: number | null;  // null → auto-derive (latest data year + horizon)
}

const KPI_LABELS: { key: string; en: string; bm: string }[] = [
  { key: 'stunting_rate',    en: 'Stunting Rate',    bm: 'Kadar Stunting' },
  { key: 'wasting_rate',     en: 'Wasting Rate',     bm: 'Kadar Wasting' },
  { key: 'underweight_rate', en: 'Underweight Rate', bm: 'Kadar Kekurangan Berat' },
  { key: 'overweight_rate',  en: 'Overweight Rate',  bm: 'Kadar Berlebihan Berat' },
];

/* A KPI target is a percentage rate: must be a finite number in [0, 100].
   Empty input → parseFloat('') → NaN → invalid (flagged, save blocked). */
const isValidTarget = (v: number) => Number.isFinite(v) && v >= 0 && v <= 100;

const SOURCE_LABELS: Record<string, { en: string; bm: string }> = {
  npan_2021_2025: { en: 'NPAN 2021–2025 (official)', bm: 'NPAN 2021–2025 (rasmi)' },
  who_2025:       { en: 'WHO Global Targets 2025 (official)', bm: 'Sasaran Global WHO 2025 (rasmi)' },
  custom:         { en: 'Custom override', bm: 'Tetapan tersuai' },
};

export function SettingsPage() {
  const { t } = useLang();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [tab, setTab] = useState<'thresholds' | 'rules' | 'kpi'>('thresholds');
  const [thresholds, setThresholds] = useState<Thresholds>(DEFAULT_THRESHOLDS);
  const [rules, setRules] = useState<Rule[]>([]);
  const [ruleSchema, setRuleSchema] = useState<RuleSchema>('myvass');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [kpi, setKpi] = useState<KpiTargets | null>(null);
  const [kpiSaving, setKpiSaving] = useState(false);
  const [kpiSaved, setKpiSaved] = useState(false);

  useEffect(() => {
    api.get<Thresholds>('/settings/thresholds').then(r => setThresholds(r.data)).catch(console.error);
    api.get<KpiTargets>('/settings/kpi-targets').then(r => setKpi(r.data)).catch(console.error);
    api.get('/settings/rules').then(r => {
      /* Backend (B3) returns { rules: [{ code, en, bm, desc_en, desc_bm,
         locked, enabled }] } — the real cleaner rules, shared with the pipeline. */
      setRules(Array.isArray(r.data?.rules) ? r.data.rules : []);
    }).catch(console.error);
  }, []);

  const saveThresholds = async () => {
    setSaving(true);
    try {
      await api.post('/settings/thresholds', thresholds);
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  };

  const restoreDefaults = () => {
    setThresholds(DEFAULT_THRESHOLDS);
  };

  const setKpiValue = (grp: 'npan' | 'who', key: string, value: number) => {
    setKpi(prev => prev && ({
      ...prev,
      current: { ...prev.current, [grp]: { ...prev.current[grp], [key]: value } },
    }));
  };

  const setKpiYear = (v: number | null) =>
    setKpi(prev => prev && ({ ...prev, target_year: v }));

  const resetKpiSet = (grp: 'npan' | 'who') => {
    setKpi(prev => prev && ({
      ...prev,
      current: { ...prev.current, [grp]: { ...prev.defaults[grp] } },
    }));
  };

  /* True when any current target is out of range / blank — drives the inline
     error and blocks the save so a nonsensical target can't be persisted. */
  /* target_year is valid when blank (auto) or a 4-digit year in [2020, 2100]. */
  const kpiYearValid = !kpi || kpi.target_year == null ||
    (Number.isInteger(kpi.target_year) && kpi.target_year >= 2020 && kpi.target_year <= 2100);
  const kpiHasError = !!kpi && (
    (['npan', 'who'] as const).some(grp =>
      KPI_LABELS.some(ind => !isValidTarget(kpi.current[grp][ind.key]))) ||
    !kpiYearValid
  );

  const saveKpiTargets = async () => {
    if (!kpi || kpiHasError) return;
    setKpiSaving(true);
    try {
      const r = await api.post<KpiTargets>('/settings/kpi-targets', {
        npan: kpi.current.npan,
        who: kpi.current.who,
        target_year: kpi.target_year,
      });
      setKpi(r.data);
      setKpiSaved(true); setTimeout(() => setKpiSaved(false), 2000);
    } finally { setKpiSaving(false); }
  };

  const toggleRule = async (code: string) => {
    const rule = rules.find(r => r.code === code);
    // locked rules are structural; a rule not used by the selected schema can't
    // be toggled from this view (switch schema to manage it).
    if (!rule || rule.locked || !rule.source_types.includes(ruleSchema)) return;
    const enabled = !rule.enabled;
    setRules(prev => prev.map(r => r.code === code ? { ...r, enabled } : r));
    await api.post('/settings/rules/toggle', { rule: code, enabled }).catch(console.error);
  };

  const sliderStyle: React.CSSProperties = { width: '100%', accentColor: 'var(--kkm-blue)' };

  /* Threshold metadata. `scale` is the multiplier from stored value to
     display value: 100 for rate columns (0.05 → 5%), 1 for the z-score.
     `recommended` is shown as a chip + tick mark below the slider. */
  type SliderMeta = {
    key: keyof Thresholds;
    labelEn: string; labelBm: string;
    max: number; step: number; unit: string; scale: number;
    recommended: number;
    descEn: string; descBm: string;
  };
  const sliders: SliderMeta[] = [
    {
      key: 'missing_rate_warn',
      labelEn: 'Missing Rate — Warning', labelBm: 'Kadar Hilang — Amaran',
      max: 30, step: 0.5, unit: '%', scale: 100, recommended: 5,
      descEn: 'Columns missing this fraction of values trigger a Warning on the quality report. NPAN guidance: 5%.',
      descBm: 'Lajur dengan kadar hilang melebihi ini akan mencetuskan Amaran pada laporan kualiti. Garis panduan NPAN: 5%.',
    },
    {
      key: 'missing_rate_fail',
      labelEn: 'Missing Rate — Fail', labelBm: 'Kadar Hilang — Gagal',
      max: 50, step: 0.5, unit: '%', scale: 100, recommended: 15,
      descEn: 'Above this level the column is marked Critical and excluded from KPI roll-ups. NPAN guidance: 15%.',
      descBm: 'Melebihi paras ini, lajur ditanda Kritikal dan dikecualikan dari KPI. Garis panduan NPAN: 15%.',
    },
    {
      key: 'duplicate_rate_warn',
      labelEn: 'Duplicate Rate — Warning', labelBm: 'Kadar Duplikat — Amaran',
      max: 20, step: 0.5, unit: '%', scale: 100, recommended: 2,
      descEn: 'Records sharing the same IC and date are flagged as duplicates. 2% is the recommended ceiling for healthy data entry.',
      descBm: 'Rekod dengan IC dan tarikh yang sama dianggap duplikat. 2% ialah had yang disyorkan untuk kemasukan data yang sihat.',
    },
    {
      key: 'duplicate_rate_fail',
      labelEn: 'Duplicate Rate — Fail', labelBm: 'Kadar Duplikat — Gagal',
      max: 30, step: 0.5, unit: '%', scale: 100, recommended: 10,
      descEn: 'Above this level the dataset is marked Critical for uniqueness. Investigate data-entry workflows before continuing.',
      descBm: 'Melebihi paras ini, dataset ditanda Kritikal untuk keunikan. Periksa aliran kerja kemasukan data sebelum meneruskan.',
    },
    {
      key: 'outlier_zscore_threshold',
      labelEn: 'Outlier Z-score Threshold', labelBm: 'Ambang Z-skor Pencilan',
      max: 5, step: 0.1, unit: '', scale: 1, recommended: 3.0,
      descEn: 'Numeric values further than this many standard deviations from the column mean are flagged as outliers. 3.0 is standard for normal distributions.',
      descBm: 'Nilai numerik yang melebihi bilangan sisihan piawai ini dari min lajur akan ditanda sebagai pencilan. 3.0 adalah piawai untuk taburan normal.',
    },
    {
      key: 'rag_amber_tolerance',
      labelEn: 'RAG Amber Band — Tolerance', labelBm: 'Jalur Amber RAG — Toleransi',
      max: 100, step: 1, unit: '%', scale: 100, recommended: 20,
      descEn: 'How far an indicator may exceed its target before turning Red. Within target → Green; up to this % above target → Amber; beyond → Red. Drives the dashboard, map and breakdown traffic lights.',
      descBm: 'Sejauh mana penunjuk boleh melebihi sasaran sebelum bertukar Merah. Dalam sasaran → Hijau; sehingga % ini di atas sasaran → Amber; melebihi → Merah. Memandu lampu isyarat papan pemuka, peta dan pecahan.',
    },
    {
      key: 'trajectory_atrisk_tolerance',
      labelEn: 'Trajectory At-Risk — Tolerance', labelBm: 'Trajektori Berisiko — Toleransi',
      max: 100, step: 1, unit: '%', scale: 100, recommended: 30,
      descEn: 'On the target trajectory forecast, a district projected within this % above target is flagged "At Risk"; beyond it is "Off Track". Applies to the Geo & Risk trajectory list.',
      descBm: 'Pada unjuran trajektori sasaran, daerah yang diunjur dalam % ini di atas sasaran ditanda "Berisiko"; melebihi itu "Tersasar". Terpakai pada senarai trajektori Geo & Risiko.',
    },
  ];

  const [openHelp, setOpenHelp] = useState<string | null>(null);

  return (
    <div style={{ maxWidth: 700 }}>
      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
        {([
          ['thresholds', t('Thresholds', 'Ambang')],
          ['rules', t('Cleaning Rules', 'Peraturan Pembersihan')],
          ...(isAdmin ? [['kpi', t('KPI Targets', 'Sasaran KPI')] as const] : []),
        ] as const).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id as typeof tab)}
            style={{ background: 'none', border: 'none', borderBottom: tab === id ? '2px solid var(--kkm-blue)' : '2px solid transparent', padding: '10px 20px', fontWeight: tab === id ? 600 : 400, color: tab === id ? 'var(--kkm-blue)' : 'var(--text-secondary)', cursor: 'pointer', fontSize: 14, marginBottom: -1 }}>
            {label}
          </button>
        ))}
      </div>

      {/* Thresholds tab */}
      {tab === 'thresholds' && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: 28, boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            {sliders.map(s => {
              const display = (thresholds[s.key] ?? 0) * s.scale;
              const recDisplay = s.recommended;
              const isOpen = openHelp === s.key;
              const isRecommended = Math.abs(display - recDisplay) < (s.step / 2);
              return (
                <div key={s.key}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      {t(s.labelEn, s.labelBm)}
                      <button
                        type="button"
                        onClick={() => setOpenHelp(isOpen ? null : s.key)}
                        aria-label="Help"
                        style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: isOpen ? 'var(--kkm-blue)' : 'var(--text-muted)', display: 'inline-flex' }}
                      >
                        <Info size={13} />
                      </button>
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {isRecommended && (
                        <span style={{ fontSize: 10, fontWeight: 700, background: 'var(--success-bg)', color: 'var(--success)', borderRadius: 999, padding: '1px 8px', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                          {t('Recommended', 'Disyorkan')}
                        </span>
                      )}
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--kkm-blue)', fontFamily: 'var(--font-mono)' }}>
                        {display.toFixed(s.step < 1 ? 1 : 0)}{s.unit}
                      </span>
                    </div>
                  </div>
                  <input type="range" min={0} max={s.max} step={s.step}
                    value={display}
                    onChange={e => setThresholds(prev => ({ ...prev, [s.key]: parseFloat(e.target.value) / s.scale }))}
                    style={sliderStyle} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                    <span>0{s.unit}</span>
                    <span style={{ color: 'var(--success)', fontWeight: 600 }}>
                      ▼ {t('Rec.', 'Disyor.')} {recDisplay}{s.unit}
                    </span>
                    <span>{s.max}{s.unit}</span>
                  </div>
                  {isOpen && (
                    <div style={{
                      marginTop: 8, padding: '10px 12px', fontSize: 12, lineHeight: 1.6,
                      color: 'var(--text-secondary)', background: 'var(--surface-2)',
                      border: '1px solid var(--border)', borderRadius: 8,
                    }}>
                      {t(s.descEn, s.descBm)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 28 }}>
            <button onClick={saveThresholds} disabled={saving}
              style={{ background: saved ? 'var(--success)' : 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '10px 22px', fontWeight: 600, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Save size={15} />
              {saving ? t('Saving…', 'Menyimpan…') : saved ? t('Saved!', 'Disimpan!') : t('Save', 'Simpan')}
            </button>
            <button onClick={restoreDefaults} type="button"
              style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-btn)', padding: '10px 18px', fontWeight: 600, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <RotateCcw size={14} />
              {t('Restore defaults', 'Pulihkan tetapan asal')}
            </button>
          </div>
        </div>
      )}

      {/* Rules tab — registry-driven (B3): the SAME rules the pipeline runs.
          Two groups share one schema filter: Exclusion Rules (drop) + Review Flags. */}
      {tab === 'rules' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            {t('These rules run during cleaning. Changes are saved and also apply in the upload pipeline. Locked rules are required for valid indicators and always run.',
               'Peraturan ini dijalankan semasa pembersihan. Perubahan disimpan dan turut digunakan dalam saluran muat naik. Peraturan terkunci diperlukan untuk penunjuk sah dan sentiasa dijalankan.')}
          </p>
          {/* Schema filter — shared by both groups; greyed rules = not applicable to schema. */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 8 }}>
              {t('Show rules for schema', 'Tunjuk peraturan untuk skema')}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {([
                ['myvass', 'MyVASS'],
                ['ncdc', 'NCDC'],
                ['kpm', 'KPM'],
                ['general', t('Other', 'Lain-lain')],
              ] as [RuleSchema, string][]).map(([key, label]) => (
                <button key={key} type="button" onClick={() => setRuleSchema(key)}
                  style={{
                    fontSize: 12, fontWeight: 600, padding: '5px 14px', borderRadius: 'var(--radius-pill)', cursor: 'pointer',
                    background: ruleSchema === key ? 'var(--kkm-blue)' : 'var(--surface-2)',
                    color: ruleSchema === key ? '#fff' : 'var(--text-secondary)',
                    border: `1px solid ${ruleSchema === key ? 'var(--kkm-blue)' : 'var(--border)'}`,
                  }}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {rules.length === 0 ? (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: 32, color: 'var(--text-muted)', textAlign: 'center', fontSize: 13 }}>
              {t('No rules found.', 'Tiada peraturan ditemui.')}
            </div>
          ) : (() => {
            const dropRules = rules.filter(r => r.kind === 'drop');
            const reviewRules = rules.filter(r => r.kind === 'review');

            const renderRuleRow = (rule: Rule, i: number, list: Rule[], isReview: boolean) => {
              const applicable = rule.source_types.includes(ruleSchema);
              const disabledToggle = rule.locked || !applicable;
              return (
                <div key={rule.code} style={{ display: 'flex', alignItems: 'flex-start', gap: 16, padding: '14px 20px', borderBottom: i < list.length - 1 ? '1px solid var(--border)' : 'none', opacity: applicable ? 1 : 0.5 }}>
                  <label style={{ position: 'relative', width: 44, height: 24, flexShrink: 0, marginTop: 2, opacity: disabledToggle ? 0.55 : 1 }}>
                    <input type="checkbox" checked={rule.enabled} disabled={disabledToggle} onChange={() => toggleRule(rule.code)} aria-label={t(rule.en, rule.bm)} style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} />
                    <div style={{ position: 'absolute', inset: 0, borderRadius: 12, background: rule.enabled ? 'var(--kkm-blue)' : 'var(--border)', transition: 'background var(--transition)', cursor: disabledToggle ? 'not-allowed' : 'pointer' }}>
                      <div style={{ position: 'absolute', width: 18, height: 18, borderRadius: '50%', background: '#fff', top: 3, left: rule.enabled ? 23 : 3, transition: 'left var(--transition)' }} />
                    </div>
                  </label>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{t(rule.en, rule.bm)}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55, marginTop: 4 }}>{t(rule.desc_en, rule.desc_bm)}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>{rule.code}</div>
                  </div>
                  {!applicable ? (
                    <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-muted)', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                      {t('Not used', 'Tidak digunakan')}
                    </span>
                  ) : rule.locked ? (
                    <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      {t('Always on', 'Sentiasa aktif')}
                    </span>
                  ) : !rule.enabled ? (
                    <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      {t('Disabled', 'Dilumpuhkan')}
                    </span>
                  ) : null}
                </div>
              );
            };

            return (
              <>
                {/* Group 1: Exclusion Rules (drop) */}
                {dropRules.length > 0 && (
                  <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
                    <div style={{ padding: '10px 20px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      <span>{t('Exclusion Rules', 'Peraturan Pengecualian')}</span>
                      <span style={{ display: 'block', fontSize: 10.5, fontWeight: 400, textTransform: 'none', letterSpacing: 0, color: 'var(--text-muted)', marginTop: 2 }}>
                        {t('Removes rows from analysis (kept in the full export).', 'Mengeluarkan baris daripada analisis (disimpan dalam eksport penuh).')}
                      </span>
                    </div>
                    {dropRules.map((rule, i) => renderRuleRow(rule, i, dropRules, false))}
                  </div>
                )}

                {/* Group 2: Review Flags — gold keyline accent via --warning border-left */}
                {reviewRules.length > 0 && (
                  <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
                    <div style={{ padding: '10px 20px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', borderLeft: '3px solid var(--warning)' }}>
                      <span>{t('Review Flags', 'Bendera Semak')}</span>
                      <span style={{ display: 'block', fontSize: 10.5, fontWeight: 400, textTransform: 'none', letterSpacing: 0, color: 'var(--text-muted)', marginTop: 2 }}>
                        {t('Marks rows for a human to review — never removed.', 'Menanda baris untuk disemak manusia — tidak pernah dibuang.')}
                      </span>
                    </div>
                    {reviewRules.map((rule, i) => renderRuleRow(rule, i, reviewRules, true))}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* KPI Targets tab — admin only */}
      {tab === 'kpi' && isAdmin && (
        kpi === null ? (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: 32, color: 'var(--text-muted)', textAlign: 'center', fontSize: 13 }}>
            {t('Loading targets…', 'Memuatkan sasaran…')}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Forecast target year (E1a) — admin policy input. Blank = auto. */}
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
              <div style={{ padding: '10px 20px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                {t('Forecast Target Year', 'Tahun Sasaran Unjuran')}
              </div>
              <div style={{ padding: 20, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                    {t('Target year for the district trajectory forecast', 'Tahun sasaran untuk unjuran trajektori daerah')}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.5 }}>
                    {t('Leave blank to auto-derive from the data (latest measurement year + 4). Projections far beyond the data are flagged as indicative in Geo & Risk.',
                       'Biarkan kosong untuk auto-terbit daripada data (tahun pengukuran terkini + 4). Unjuran jauh melebihi data ditanda sebagai petunjuk dalam Geo & Risiko.')}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
                  <input
                    type="number" min={2020} max={2100} step={1}
                    placeholder={t('Auto', 'Auto')}
                    aria-invalid={!kpiYearValid}
                    value={kpi.target_year ?? ''}
                    onChange={e => setKpiYear(e.target.value === '' ? null : parseInt(e.target.value, 10))}
                    style={{ width: 92, textAlign: 'right', padding: '6px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--navy)', background: 'var(--surface)', border: `1px solid ${kpiYearValid ? 'var(--border)' : 'var(--danger)'}`, borderRadius: 6 }}
                  />
                  {!kpiYearValid && (
                    <span role="alert" style={{ fontSize: 10, fontWeight: 600, color: 'var(--danger)' }}>
                      {t('Year 2020–2100', 'Tahun 2020–2100')}
                    </span>
                  )}
                </div>
              </div>
            </div>
            {(['npan', 'who'] as const).map(grp => {
              const isCustom = kpi.source[grp] === 'custom';
              const officialKey = grp === 'npan' ? 'npan_2021_2025' : 'who_2025';
              const provenance = isCustom ? SOURCE_LABELS.custom : SOURCE_LABELS[officialKey];
              return (
                <div key={grp} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 20px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                      {grp === 'npan' ? t('NPAN National Targets', 'Sasaran Kebangsaan NPAN') : t('WHO Global Targets', 'Sasaran Global WHO')}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 600, borderRadius: 999, padding: '2px 8px', background: isCustom ? 'var(--warning-bg)' : 'var(--success-bg)', color: isCustom ? 'var(--warning)' : 'var(--success)' }}>
                      {t(provenance.en, provenance.bm)}
                    </span>
                  </div>
                  <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {KPI_LABELS.map(ind => {
                      const val = kpi.current[grp][ind.key];
                      const def = kpi.defaults[grp][ind.key];
                      const invalid = !isValidTarget(val);
                      return (
                        <div key={ind.key} style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{t(ind.en, ind.bm)}</div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                              {t('Official', 'Rasmi')}: {def}%
                            </div>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                              <input
                                type="number" min={0} max={100} step={0.1}
                                aria-invalid={invalid}
                                value={Number.isFinite(val) ? val : ''}
                                onChange={e => setKpiValue(grp, ind.key, parseFloat(e.target.value))}
                                style={{ width: 80, textAlign: 'right', padding: '6px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--navy)', background: 'var(--surface)', border: `1px solid ${invalid ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 6 }}
                              />
                              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>%</span>
                            </div>
                            {invalid && (
                              <span role="alert" style={{ fontSize: 10, fontWeight: 600, color: 'var(--danger)' }}>
                                {t('Enter 0–100', 'Masukkan 0–100')}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                    <button onClick={() => resetKpiSet(grp)} type="button"
                      style={{ alignSelf: 'flex-start', background: 'none', border: 'none', padding: 0, marginTop: 2, color: 'var(--kkm-blue)', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <RotateCcw size={12} />
                      {grp === 'npan' ? t('Reset to NPAN 2021–2025', 'Set semula ke NPAN 2021–2025') : t('Reset to WHO 2025', 'Set semula ke WHO 2025')}
                    </button>
                  </div>
                </div>
              );
            })}
            <div>
              <button onClick={saveKpiTargets} disabled={kpiSaving || kpiHasError}
                style={{ background: kpiSaved ? 'var(--success)' : 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '10px 22px', fontWeight: 600, fontSize: 14, cursor: kpiHasError ? 'not-allowed' : 'pointer', opacity: kpiHasError ? 0.5 : 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Save size={15} />
                {kpiSaving ? t('Saving…', 'Menyimpan…') : kpiSaved ? t('Saved!', 'Disimpan!') : t('Save targets', 'Simpan sasaran')}
              </button>
              {kpiHasError && (
                <div role="alert" style={{ fontSize: 11, fontWeight: 600, color: 'var(--danger)', marginTop: 8 }}>
                  {t('Fix the highlighted targets (0–100) before saving.', 'Betulkan sasaran yang ditandakan (0–100) sebelum menyimpan.')}
                </div>
              )}
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 10, lineHeight: 1.5 }}>
                {t(
                  'Changes apply immediately to the dashboard RAG status, district trajectory, and reports. Edits are recorded in the Audit Log.',
                  'Perubahan terpakai serta-merta pada status RAG papan pemuka, trajektori daerah, dan laporan. Suntingan direkodkan dalam Log Audit.',
                )}
              </div>
            </div>
          </div>
        )
      )}
    </div>
  );
}
