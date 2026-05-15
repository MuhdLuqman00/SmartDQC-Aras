import React, { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface Thresholds {
  missing_warn: number; missing_fail: number;
  duplicate_warn: number; duplicate_fail: number;
  outlier_zscore: number;
}

interface Rule { id: string; description: string; enabled: boolean; }

export function SettingsPage() {
  const { t } = useLang();
  const [tab, setTab] = useState<'thresholds' | 'rules'>('thresholds');
  const [thresholds, setThresholds] = useState<Thresholds>({ missing_warn: 5, missing_fail: 15, duplicate_warn: 2, duplicate_fail: 10, outlier_zscore: 3.0 });
  const [rules, setRules] = useState<Rule[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<Thresholds>('/settings/thresholds').then(r => setThresholds(r.data)).catch(console.error);
    api.get<{ rules: Rule[] }>('/settings/rules').then(r => setRules(r.data.rules ?? r.data as unknown as Rule[])).catch(console.error);
  }, []);

  const saveThresholds = async () => {
    setSaving(true);
    try {
      await api.post('/settings/thresholds', thresholds);
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  };

  const toggleRule = async (id: string) => {
    const rule = rules.find(r => r.id === id);
    if (!rule) return;
    const enabled = !rule.enabled;
    setRules(prev => prev.map(r => r.id === id ? { ...r, enabled } : r));
    await api.post('/settings/rules/toggle', { rule_id: id, enabled }).catch(console.error);
  };

  const sliderStyle: React.CSSProperties = { width: '100%', accentColor: 'var(--kkm-blue)' };

  const sliders: { key: keyof Thresholds; labelEn: string; labelBm: string; max: number; step: number; unit: string }[] = [
    { key: 'missing_warn',    labelEn: 'Missing Rate Warn',    labelBm: 'Had Amaran Hilang',       max: 30,  step: 0.5, unit: '%' },
    { key: 'missing_fail',    labelEn: 'Missing Rate Fail',    labelBm: 'Had Gagal Hilang',        max: 50,  step: 0.5, unit: '%' },
    { key: 'duplicate_warn',  labelEn: 'Duplicate Rate Warn',  labelBm: 'Had Amaran Duplikat',     max: 20,  step: 0.5, unit: '%' },
    { key: 'duplicate_fail',  labelEn: 'Duplicate Rate Fail',  labelBm: 'Had Gagal Duplikat',      max: 30,  step: 0.5, unit: '%' },
    { key: 'outlier_zscore',  labelEn: 'Outlier Z-score',      labelBm: 'Z-skor Pencilan',         max: 5,   step: 0.1, unit: ''  },
  ];

  return (
    <div style={{ maxWidth: 700 }}>
      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
        {([['thresholds', t('Thresholds', 'Ambang')], ['rules', t('Cleaning Rules', 'Peraturan Pembersihan')]] as const).map(([id, label]) => (
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
            {sliders.map(s => (
              <div key={s.key}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                    {t(s.labelEn, s.labelBm)}
                  </label>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--kkm-blue)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {thresholds[s.key]}{s.unit}
                  </span>
                </div>
                <input type="range" min={0} max={s.max} step={s.step}
                  value={thresholds[s.key]}
                  onChange={e => setThresholds(prev => ({ ...prev, [s.key]: parseFloat(e.target.value) }))}
                  style={sliderStyle} />
              </div>
            ))}
          </div>
          <button onClick={saveThresholds} disabled={saving}
            style={{ marginTop: 28, background: saved ? 'var(--success)' : 'var(--kkm-blue)', color: '#fff', border: 'none', borderRadius: 'var(--radius-btn)', padding: '10px 22px', fontWeight: 600, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Save size={15} />
            {saving ? t('Saving…', 'Menyimpan…') : saved ? t('Saved!', 'Disimpan!') : t('Save', 'Simpan')}
          </button>
        </div>
      )}

      {/* Rules tab */}
      {tab === 'rules' && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
          {rules.length === 0 ? (
            <div style={{ padding: 32, color: 'var(--text-muted)', textAlign: 'center', fontSize: 13 }}>
              {t('No rules found.', 'Tiada peraturan ditemui.')}
            </div>
          ) : rules.map((rule, i) => (
            <div key={rule.id} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', borderBottom: i < rules.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <label style={{ position: 'relative', width: 44, height: 24, flexShrink: 0 }}>
                <input type="checkbox" checked={rule.enabled} onChange={() => toggleRule(rule.id)} style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} />
                <div style={{ position: 'absolute', inset: 0, borderRadius: 12, background: rule.enabled ? 'var(--kkm-blue)' : 'var(--border)', transition: 'background var(--transition)', cursor: 'pointer' }}>
                  <div style={{ position: 'absolute', width: 18, height: 18, borderRadius: '50%', background: '#fff', top: 3, left: rule.enabled ? 23 : 3, transition: 'left var(--transition)' }} />
                </div>
              </label>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{rule.description || rule.id}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>{rule.id}</div>
              </div>
              {!rule.enabled && (
                <span style={{ fontSize: 10, fontWeight: 600, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 8px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  {t('Disabled', 'Dilumpuhkan')}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
