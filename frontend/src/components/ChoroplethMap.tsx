import React from 'react';
import { createPortal } from 'react-dom';
import { ComposableMap, Geographies, Geography } from 'react-simple-maps';
import { useLang } from '../context/LanguageContext';

export interface District {
  name: string;
  stunting_rate: number;
  wasting_rate: number;
  underweight_rate: number;
  overweight_rate: number;
  risk_rag: 'green' | 'amber' | 'red';
  vs_target: number;
}

export interface Aggregates {
  stunting: number;
  wasting: number;
  underweight: number;
  overweight: number;
  stuntingRag: 'green' | 'amber' | 'red';
  wastingRag: 'green' | 'amber' | 'red';
  underweightRag: 'green' | 'amber' | 'red';
  overweightRag: 'green' | 'amber' | 'red';
}

/* Status palette migrated from the old generic RAG (#00b5a5/#e0a13c/#d9534f)
   to the KKM Navy-Gold-Brick set: --status-good (sky), --status-watch (gold),
   --status-critical (brick). Tokens defined in tokens.css. */
export function ragToColor(rag: 'green' | 'amber' | 'red' | undefined): string {
  if (rag === 'green') return 'var(--status-good)';
  if (rag === 'amber') return 'var(--status-watch)';
  if (rag === 'red')   return 'var(--status-critical)';
  return 'var(--surface-2)';
}

export function buildDistrictLookup(districts: District[]): Map<string, District> {
  const map = new Map<string, District>();
  for (const d of districts) map.set(d.name.trim().toLowerCase(), d);
  return map;
}

function rateToRag(rate: number): 'green' | 'amber' | 'red' {
  if (rate > 0.15) return 'red';
  if (rate > 0.08) return 'amber';
  return 'green';
}

export function computeAggregates(districts: District[]): Aggregates {
  if (!districts.length) {
    return {
      stunting: 0, wasting: 0, underweight: 0, overweight: 0,
      stuntingRag: 'green', wastingRag: 'green', underweightRag: 'green', overweightRag: 'green',
    };
  }
  const n = districts.length;
  const stunting    = districts.reduce((s, d) => s + d.stunting_rate, 0) / n;
  const wasting     = districts.reduce((s, d) => s + d.wasting_rate, 0) / n;
  const underweight = districts.reduce((s, d) => s + d.underweight_rate, 0) / n;
  const overweight  = districts.reduce((s, d) => s + d.overweight_rate, 0) / n;
  return {
    stunting, wasting, underweight, overweight,
    stuntingRag:    rateToRag(stunting),
    wastingRag:     rateToRag(wasting),
    underweightRag: rateToRag(underweight),
    overweightRag: rateToRag(overweight),
  };
}

/* Reverse of DashboardPage/GeoPage STATE_TO_CODE — display only.
   Canonical "Pulau Pinang" preferred over "Penang" (matches MOH/KKM usage). */
const CODE_TO_STATE_DISPLAY: Record<string, string> = {
  jhr: 'Johor',
  kdh: 'Kedah',
  ktn: 'Kelantan',
  kul: 'Kuala Lumpur',
  lbn: 'Labuan',
  mlk: 'Melaka',
  nsn: 'Negeri Sembilan',
  pjy: 'Putrajaya',
  pls: 'Perlis',
  png: 'Pulau Pinang',
  prk: 'Perak',
  phg: 'Pahang',
  sbh: 'Sabah',
  sgr: 'Selangor',
  swk: 'Sarawak',
  trg: 'Terengganu',
};

function displayStateName(code: string): string {
  const k = code.trim().toLowerCase();
  return CODE_TO_STATE_DISPLAY[k] || code.toUpperCase();
}

interface TooltipState { x: number; y: number; district: District; }

interface Props {
  districts: District[];
  selectedDistrict?: string | null;
  onDistrictClick?: (district: string | null) => void;
}

export function ChoroplethMap({ districts, selectedDistrict, onDistrictClick }: Props): JSX.Element {
  const { t } = useLang();
  const [tooltip, setTooltip] = React.useState<TooltipState | null>(null);
  const lookup = React.useMemo(() => buildDistrictLookup(districts), [districts]);

  const ragLabel = (rag: 'green' | 'amber' | 'red'): string => {
    if (rag === 'green') return t('Good', 'Baik');
    if (rag === 'amber') return t('Moderate', 'Sederhana');
    return t('Critical', 'Kritikal');
  };

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ center: [109.5, 3.8], scale: 2400 }}
        width={800}
        height={360}
        style={{ width: '100%', height: 'auto', display: 'block' }}
      >
        <Geographies geography="/my-districts.json">
          {({ geographies }: { geographies: { rsmKey: string; properties: Record<string, string> }[] }) =>
            geographies.map(geo => {
              // Match by 3-letter state code (geo.properties.state) so all districts
              // in a state share the same KPI colour.
              const geoCode = String(geo.properties['state'] ?? '').trim().toLowerCase();
              const district = lookup.get(geoCode);
              const isSelected = selectedDistrict && geoCode === selectedDistrict.toLowerCase();
              const fill = district ? ragToColor(district.risk_rag) : 'var(--surface-2)';

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={fill}
                  stroke={isSelected ? 'var(--kkm-sky)' : 'var(--text-muted)'}
                  strokeWidth={isSelected ? 2.5 : 1.25}
                  style={{
                    default: {
                      outline: 'none',
                      opacity: 1,
                      strokeLinejoin: 'round',
                      transition: 'opacity 0.15s ease, fill 0.15s ease',
                    },
                    hover:   { outline: 'none', opacity: 0.85, cursor: 'pointer', strokeLinejoin: 'round' },
                    pressed: { outline: 'none' },
                  }}
                  onClick={() => {
                    if (!onDistrictClick) return;
                    onDistrictClick(isSelected ? null : geoCode);
                  }}
                  onMouseEnter={(evt: React.MouseEvent) => {
                    if (!district) return;
                    setTooltip({ x: evt.clientX, y: evt.clientY, district });
                  }}
                  onMouseMove={(evt: React.MouseEvent) => {
                    setTooltip(prev => prev ? { ...prev, x: evt.clientX, y: evt.clientY } : null);
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>

      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 10,
        fontSize: 11, color: 'var(--text-secondary)',
      }}>
        {([
          ['var(--status-good)', t('Good', 'Baik')],
          ['var(--status-watch)', t('Moderate', 'Sederhana')],
          ['var(--status-critical)', t('Critical', 'Kritikal')],
          ['var(--surface-2)', t('No data', 'Tiada data')],
        ] as const).map(([c, label]) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              width: 10, height: 10, borderRadius: 3, background: c,
              border: '1px solid var(--border)', display: 'inline-block',
            }} />
            {label}
          </span>
        ))}
      </div>

      {/* Tooltip is portaled to document.body so the .page-enter
         animation (which leaves a `transform` on every page ancestor)
         can't capture position:fixed and pull the tooltip away from
         the cursor. */}
      {tooltip && createPortal(
        <div style={{
          position: 'fixed',
          top: tooltip.y + 14, left: tooltip.x + 14,
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 8, padding: '10px 14px',
          pointerEvents: 'none', zIndex: 9999,
          minWidth: 184, boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
        }}>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 13, marginBottom: 6 }}>
            {displayStateName(tooltip.district.name)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>
            {t('Stunting', 'Kelaparan')}: {(Number(tooltip.district.stunting_rate) * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
            {t('Wasting', 'Kurus')}: {(Number(tooltip.district.wasting_rate) * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: ragToColor(tooltip.district.risk_rag) }}>
            ● {ragLabel(tooltip.district.risk_rag)}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
