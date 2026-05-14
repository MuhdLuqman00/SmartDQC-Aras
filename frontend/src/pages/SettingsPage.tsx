import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useLang } from '../context/LanguageContext';

interface Thresholds {
  missing_rate_warn: number;
  missing_rate_fail: number;
  duplicate_rate_warn: number;
  duplicate_rate_fail: number;
  outlier_zscore_threshold: number;
}

interface RuleEntry {
  enabled: boolean;
}

type Rules = Record<string, RuleEntry>;

export function SettingsPage() {
  const { t } = useLang();

  const THRESHOLD_LABELS: Record<keyof Thresholds, string> = {
    missing_rate_warn:        t('Missing Rate — Warning',       'Kadar Hilang — Amaran'),
    missing_rate_fail:        t('Missing Rate — Fail',          'Kadar Hilang — Gagal'),
    duplicate_rate_warn:      t('Duplicate Rate — Warning',     'Kadar Berganda — Amaran'),
    duplicate_rate_fail:      t('Duplicate Rate — Fail',        'Kadar Berganda — Gagal'),
    outlier_zscore_threshold: t('Outlier Z-score Threshold',    'Ambang Z-score Outlier'),
  };
  const [thresholds, setThresholds] = useState<Thresholds>({
    missing_rate_warn: 0.05,
    missing_rate_fail: 0.15,
    duplicate_rate_warn: 0.02,
    duplicate_rate_fail: 0.10,
    outlier_zscore_threshold: 3.0,
  });

  const [rules, setRules] = useState<Rules>({});
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [thresholdsRes, rulesRes] = await Promise.all([
          api.get<Thresholds>('/settings/thresholds'),
          api.get<Rules>('/settings/rules'),
        ]);
        setThresholds(thresholdsRes.data);
        setRules(rulesRes.data);
      } catch {
        // Use defaults on error
      }
    };
    fetchSettings();
  }, []);

  const updateThreshold = (key: keyof Thresholds, value: string): void => {
    const parsed = parseFloat(value);
    if (!isNaN(parsed)) {
      setThresholds(prev => ({ ...prev, [key]: parsed }));
    }
  };

  const saveThresholds = async (): Promise<void> => {
    setLoading(true);
    setSaveStatus('idle');
    try {
      await api.post('/settings/thresholds', thresholds);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch {
      setSaveStatus('error');
    } finally {
      setLoading(false);
    }
  };

  const toggleRule = async (ruleName: string): Promise<void> => {
    const current = rules[ruleName]?.enabled ?? false;
    const newEnabled = !current;

    // Optimistic update
    setRules(prev => ({
      ...prev,
      [ruleName]: { enabled: newEnabled },
    }));

    try {
      await api.post('/settings/rules/toggle', { rule: ruleName, enabled: newEnabled });
    } catch {
      // Revert on failure
      setRules(prev => ({
        ...prev,
        [ruleName]: { enabled: current },
      }));
    }
  };

  const getRuleDisplayName = (ruleName: string): string => {
    return ruleName
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div style={styles.container}>
      <div style={styles.cardsGrid}>
        {/* Card 1: Ambang Kualiti */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>{t('Quality Thresholds', 'Ambang Kualiti')}</div>

          {(Object.keys(THRESHOLD_LABELS) as (keyof Thresholds)[]).map(key => {
            const isZScore = key === 'outlier_zscore_threshold';
            return (
              <div key={key} style={styles.fieldRow}>
                <label style={styles.fieldLabel}>{THRESHOLD_LABELS[key]}</label>
                <input
                  type="number"
                  step={isZScore ? '0.1' : '0.01'}
                  min="0"
                  max={isZScore ? '10' : '1'}
                  value={thresholds[key]}
                  onChange={e => updateThreshold(key, e.target.value)}
                  style={styles.numberInput}
                  disabled={loading}
                />
              </div>
            );
          })}

          <div style={styles.buttonContainer}>
            <button
              onClick={saveThresholds}
              disabled={loading}
              style={{
                ...styles.saveButton,
                opacity: loading ? 0.6 : 1,
              }}
            >
              {t('Save', 'Simpan')}
            </button>
          </div>

          {saveStatus === 'success' && (
            <div style={styles.feedbackSuccess}>{t('Settings saved.', 'Tetapan disimpan.')}</div>
          )}
          {saveStatus === 'error' && (
            <div style={styles.feedbackError}>{t('Failed to save.', 'Gagal menyimpan.')}</div>
          )}
        </div>

        {/* Card 2: Peraturan Pembersihan */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>{t('Cleaning Rules', 'Peraturan Pembersihan')}</div>

          {Object.keys(rules).length === 0 && (
            <div style={styles.emptyState}>{t('Loading rules...', 'Memuatkan peraturan...')}</div>
          )}

          {Object.entries(rules).map(([ruleName, entry]) => (
            <div key={ruleName} style={styles.ruleRow}>
              <span style={styles.ruleName}>{getRuleDisplayName(ruleName)}</span>
              <input
                type="checkbox"
                checked={entry.enabled}
                onChange={() => toggleRule(ruleName)}
                style={styles.checkbox}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '0',
  },
  cardsGrid: {
    display: 'flex',
    gap: '20px',
  },
  card: {
    flex: 1,
    background: 'var(--surface)',
    border: '0.5px solid var(--border)',
    borderRadius: '12px',
    padding: '24px',
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    marginBottom: '16px',
  },
  fieldRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
    gap: '12px',
  },
  fieldLabel: {
    fontSize: '14px',
    color: 'var(--text-primary)',
    flex: 1,
  },
  numberInput: {
    border: '0.5px solid var(--border)',
    borderRadius: '8px',
    padding: '8px 12px',
    background: 'var(--surface-2)',
    fontSize: '14px',
    color: 'var(--text-primary)',
    width: '90px',
    textAlign: 'right',
    transition: 'all 0.15s ease',
  },
  buttonContainer: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginTop: '16px',
    paddingTop: '12px',
    borderTop: '0.5px solid var(--border)',
  },
  saveButton: {
    background: 'var(--navy)',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 16px',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  feedbackSuccess: {
    marginTop: '12px',
    padding: '8px 12px',
    fontSize: '13px',
    color: 'var(--success)',
    textAlign: 'center',
  },
  feedbackError: {
    marginTop: '12px',
    padding: '8px 12px',
    fontSize: '13px',
    color: 'var(--danger)',
    textAlign: 'center',
  },
  emptyState: {
    padding: '16px 0',
    fontSize: '14px',
    color: 'var(--text-muted)',
  },
  ruleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 0',
    borderBottom: '0.5px solid var(--border)',
    transition: 'all 0.15s ease',
  },
  ruleName: {
    fontSize: '14px',
    color: 'var(--text-primary)',
  },
  checkbox: {
    width: '18px',
    height: '18px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    accentColor: 'var(--navy)',
  },
};
