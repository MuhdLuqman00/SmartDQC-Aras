import React from 'react';
import { ComposableMap, Geographies, Geography } from 'react-simple-maps';

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

export function ragToColor(rag: 'green' | 'amber' | 'red' | undefined): string {
  if (rag === 'green') return '#00b5a5';
  if (rag === 'amber') return '#e0a13c';
  if (rag === 'red')   return '#d9534f';
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
    overweightRag:  rateToRag(overweight),
  };
}

const RAG_LABEL: Record<'green' | 'amber' | 'red', string> = {
  green: 'Baik', amber: 'Sederhana', red: 'Kritikal',
};

interface TooltipState { x: number; y: number; district: District; }

interface Props {
  districts: District[];
  selectedDistrict?: string | null;
  onDistrictClick?: (district: string | null) => void;
}

export function ChoroplethMap({ districts, selectedDistrict, onDistrictClick }: Props): JSX.Element {
  const [tooltip, setTooltip] = React.useState<TooltipState | null>(null);
  const lookup = React.useMemo(() => buildDistrictLookup(districts), [districts]);

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
          ['#00b5a5', 'Green'],
          ['#e0a13c', 'Amber'],
          ['#d9534f', 'Red'],
          ['var(--surface-2)', 'No data'],
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

      {tooltip && (
        <div style={{
          position: 'fixed',
          top: tooltip.y + 14, left: tooltip.x + 14,
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 8, padding: '10px 14px',
          pointerEvents: 'none', zIndex: 9999,
          minWidth: 164, boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
        }}>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 13, marginBottom: 6 }}>
            {tooltip.district.name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>
            Stunting: {(Number(tooltip.district.stunting_rate) * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
            Wasting: {(Number(tooltip.district.wasting_rate) * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: ragToColor(tooltip.district.risk_rag) }}>
            ● {RAG_LABEL[tooltip.district.risk_rag]}
          </div>
        </div>
      )}
    </div>
  );
}
