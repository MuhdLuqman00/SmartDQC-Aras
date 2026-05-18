export interface PersistInfo { persisted?: boolean; persist_error?: string | null; }

/** Message to show when a clean/EDA run succeeded but was NOT saved to the
 *  database. Returns null when saved, or when the backend didn't send the
 *  flag (older backend — stay silent rather than false-alarm). */
export function persistWarning(d: PersistInfo, lang: 'en' | 'bm'): string | null {
  if (d.persisted !== false) return null;
  return lang === 'bm'
    ? 'Data dibersihkan tetapi TIDAK disimpan ke pangkalan data — papan pemuka akan kosong. Pangkalan data tidak dapat dihubungi.'
    : 'Data was cleaned but NOT saved to the database — the dashboard will be empty. The database is unreachable.';
}
