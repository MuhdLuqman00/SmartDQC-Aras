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

interface Rule { id: string; description: string; enabled: boolean; }

/* KPI benchmark targets. Both NPAN (national policy) and WHO (clinical
   standard) targets are editable, admin-only. Labels live here; the backend
   stores only the numeric rates so a save can't corrupt them. */
type TargetSet = Record<string, number>;
interface KpiTargets {
  current: { npan: TargetSet; who: TargetSet };
  defaults: { npan: TargetSet; who: TargetSet };
  source: { npan: string; who: string };
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

/* Rule metadata — backend defaults don't ship descriptions, so we
   surface them here. Grouped so the rules tab reads as a checklist
   rather than 9 anonymous toggles. */
const RULE_META: Record<string, { groupEn: string; groupBm: string; nameEn: string; nameBm: string; descEn: string; descBm: string }> = {
  duplicate_check: {
    groupEn: 'Integrity', groupBm: 'Integriti',
    nameEn: 'Duplicate row detection', nameBm: 'Pengesanan baris duplikat',
    descEn: 'Flag exact-duplicate rows (same IC + same measurement date).',
    descBm: 'Tandakan baris duplikat tepat (IC dan tarikh pengukuran sama).',
  },
  missing_value_check: {
    groupEn: 'Integrity', groupBm: 'Integriti',
    nameEn: 'Missing-value check', nameBm: 'Semakan nilai hilang',
    descEn: 'Flag rows where critical columns (IC, height, weight, date) are blank.',
    descBm: 'Tandakan baris di mana lajur kritikal (IC, tinggi, berat, tarikh) kosong.',
  },
  ic_format_check: {
    groupEn: 'Format', groupBm: 'Format',
    nameEn: 'IC number format', nameBm: 'Format nombor IC',
    descEn: 'Verify each IC is a 12-digit Malaysian identification number.',
    descBm: 'Sahkan setiap IC ialah nombor pengenalan Malaysia 12-digit.',
  },
  date_format_check: {
    groupEn: 'Format', groupBm: 'Format',
    nameEn: 'Date format', nameBm: 'Format tarikh',
    descEn: 'Verify dates parse to a valid calendar value (no Feb 30, no future birth dates).',
    descBm: 'Sahkan tarikh dihurai kepada nilai kalendar sah (tiada 30 Februari, tiada tarikh lahir akan datang).',
  },
  gender_value_check: {
    groupEn: 'Format', groupBm: 'Format',
    nameEn: 'Gender value', nameBm: 'Nilai jantina',
    descEn: 'Restrict gender values to L/P (or Male/Female aliases).',
    descBm: 'Hadkan nilai jantina kepada L/P (atau alias Lelaki/Perempuan).',
  },
  age_range_check: {
    groupEn: 'Range', groupBm: 'Julat',
    nameEn: 'Age range', nameBm: 'Julat umur',
    descEn: 'Reject ages outside 0–60 months for paediatric nutrition datasets.',
    descBm: 'Tolak umur di luar 0–60 bulan untuk dataset pemakanan pediatrik.',
  },
  height_range_check: {
    groupEn: 'Range', groupBm: 'Julat',
    nameEn: 'Height range', nameBm: 'Julat tinggi',
    descEn: 'Reject heights outside 40–130 cm (WHO under-5 reference window).',
    descBm: 'Tolak tinggi di luar 40–130 cm (rujukan WHO bawah-5 tahun).',
  },
  weight_range_check: {
    groupEn: 'Range', groupBm: 'Julat',
    nameEn: 'Weight range', nameBm: 'Julat berat',
    descEn: 'Reject weights outside 1.5–35 kg (WHO under-5 reference window).',
    descBm: 'Tolak berat di luar 1.5–35 kg (rujukan WHO bawah-5 tahun).',
  },
  bmi_range_check: {
    groupEn: 'Consistency', groupBm: 'Konsistensi',
    nameEn: 'BMI consistency', nameBm: 'Konsistensi BMI',
    descEn: 'Verify recorded BMI matches weight/height² to within rounding tolerance.',
    descBm: 'Sahkan BMI yang direkodkan sepadan dengan berat/tinggi² dalam toleransi pembundaran.',
  },
};

export function SettingsPage() {
  const { t } = useLang();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [tab, setTab] = useState<'thresholds' | 'rules' | 'kpi'>('thresholds');
  const [thresholds, setThresholds] = useState<Thresholds>(DEFAULT_THRESHOLDS);
  const [rules, setRules] = useState<Rule[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [kpi, setKpi] = useState<KpiTargets | null>(null);
  const [kpiSaving, setKpiSaving] = useState(false);
  const [kpiSaved, setKpiSaved] = useState(false);

  useEffect(() => {
    api.get<Thresholds>('/settings/thresholds').then(r => setThresholds(r.data)).catch(console.error);
    api.get<KpiTargets>('/settings/kpi-targets').then(r => setKpi(r.data)).catch(console.error);
    api.get('/settings/rules').then(r => {
      /* Backend returns a dict keyed by rule-id: { duplicate_check: { enabled }, … }.
         Normalise to Rule[] so an object can never reach rules.map() (was blanking
         the page). Also tolerate a future array or { rules: [...] } shape. */
      const data = r.data?.rules ?? r.data ?? {};
      const list: Rule[] = Array.isArray(data)
        ? data
        : Object.entries(data as Record<string, { enabled?: boolean; description?: string }>)
            .map(([id, v]) => ({
              id,
              description: typeof v?.description === 'string' ? v.description : '',
              enabled: v?.enabled !== false,
            }));
      setRules(list);
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

  const resetKpiSet = (grp: 'npan' | 'who') => {
    setKpi(prev => prev && ({
      ...prev,
      current: { ...prev.current, [grp]: { ...prev.defaults[grp] } },
    }));
  };

  /* True when any current target is out of range / blank — drives the inline
     error and blocks the save so a nonsensical target can't be persisted. */
  const kpiHasError = !!kpi && (['npan', 'who'] as const).some(grp =>
    KPI_LABELS.some(ind => !isValidTarget(kpi.current[grp][ind.key])));

  const saveKpiTargets = async () => {
    if (!kpi || kpiHasError) return;
    setKpiSaving(true);
    try {
      const r = await api.post<KpiTargets>('/settings/kpi-targets', {
        npan: kpi.current.npan,
        who: kpi.current.who,
      });
      setKpi(r.data);
      setKpiSaved(true); setTimeout(() => setKpiSaved(false), 2000);
    } finally { setKpiSaving(false); }
  };

  const toggleRule = async (id: string) => {
    const rule = rules.find(r => r.id === id);
    if (!rule) return;
    const enabled = !rule.enabled;
    setRules(prev => prev.map(r => r.id === id ? { ...r, enabled } : r));
    await api.post('/settings/rules/toggle', { rule: id, enabled }).catch(console.error);
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

      {/* Rules tab */}
      {tab === 'rules' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {rules.length === 0 ? (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', padding: 32, color: 'var(--text-muted)', textAlign: 'center', fontSize: 13 }}>
              {t('No rules found.', 'Tiada peraturan ditemui.')}
            </div>
          ) : (() => {
            // Group rules by RULE_META.group; rules without metadata fall under "Other".
            const groups: Record<string, { en: string; bm: string; items: Rule[] }> = {};
            for (const rule of rules) {
              const meta = RULE_META[rule.id];
              const key = meta?.groupEn ?? 'Other';
              groups[key] ||= { en: meta?.groupEn ?? 'Other', bm: meta?.groupBm ?? 'Lain-lain', items: [] };
              groups[key].items.push(rule);
            }
            return Object.entries(groups).map(([key, g]) => (
              <div key={key} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
                <div style={{ padding: '10px 20px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                  {t(g.en, g.bm)}
                </div>
                {g.items.map((rule, i) => {
                  const meta = RULE_META[rule.id];
                  const name = meta ? t(meta.nameEn, meta.nameBm) : (rule.description || rule.id);
                  const desc = meta ? t(meta.descEn, meta.descBm) : '';
                  return (
                    <div key={rule.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 16, padding: '14px 20px', borderBottom: i < g.items.length - 1 ? '1px solid var(--border)' : 'none' }}>
                      <label style={{ position: 'relative', width: 44, height: 24, flexShrink: 0, marginTop: 2 }}>
                        <input type="checkbox" checked={rule.enabled} onChange={() => toggleRule(rule.id)} style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} />
                        <div style={{ position: 'absolute', inset: 0, borderRadius: 12, background: rule.enabled ? 'var(--kkm-blue)' : 'var(--border)', transition: 'background var(--transition)', cursor: 'pointer' }}>
                          <div style={{ position: 'absolute', width: 18, height: 18, borderRadius: '50%', background: '#fff', top: 3, left: rule.enabled ? 23 : 3, transition: 'left var(--transition)' }} />
                        </div>
                      </label>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{name}</div>
                        {desc && (
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55, marginTop: 4 }}>{desc}</div>
                        )}
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>{rule.id}</div>
                      </div>
                      {!rule.enabled && (
                        <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          {t('Disabled', 'Dilumpuhkan')}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ));
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
                                style={{ width: 80, textAlign: 'right', padding: '6px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--kkm-blue)', background: 'var(--surface)', border: `1px solid ${invalid ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 6 }}
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
