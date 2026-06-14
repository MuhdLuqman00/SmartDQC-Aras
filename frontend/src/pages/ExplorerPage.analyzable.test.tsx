// @vitest-environment jsdom
//
// Guards the Explorer "Analyzable only" toggle reactivity (fixed in 3f426fc).
// The bug was a stale useMemo dependency array: `searchFiltered` referenced
// `analyzableFiltered` in its body but did not list it as a dependency, so
// flipping `showAnalyzableOnly` recomputed `analyzableFiltered` while the
// rendered `filtered` (which drives both the rows and the "x / y" count) stayed
// stale — the excluded rows never disappeared. A plain logic test cannot catch
// this; only re-rendering the real component on a toggle does.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// 3 analyzable + 2 excluded rows. Small enough that the virtual-scroll window
// mounts all of them, so we can assert on individual cells. Defined via
// vi.hoisted so the (hoisted) vi.mock factories below can reference it.
const ROWS = vi.hoisted(() => [
  { _row_id: 0, nama: 'Aishah', _flagged: false, _exclude_label: null },
  { _row_id: 1, nama: 'Bala',   _flagged: false, _exclude_label: null },
  { _row_id: 2, nama: 'Chong',  _flagged: false, _exclude_label: null },
  { _row_id: 3, nama: 'Devi',   _flagged: true,  _exclude_label: 'dropped_invalid_gender' },
  { _row_id: 4, nama: 'Ehsan',  _flagged: true,  _exclude_label: 'dropped_invalid_gender' },
]);

vi.mock('../api/client', () => ({
  api: {
    post: vi.fn().mockResolvedValue({ data: { rows: ROWS, total: ROWS.length } }),
    get: vi.fn().mockResolvedValue({ data: {} }), // /config/clinical-ranges → defaults
  },
}));

vi.mock('../context/SessionContext', () => ({
  useSession: () => ({ cacheId: 'test-cache', filename: 'sample.csv', rowCount: ROWS.length }),
}));

vi.mock('../context/LanguageContext', () => ({
  useLang: () => ({ lang: 'en', setLang: () => {}, toggleLang: () => {}, t: (en: string) => en }),
}));

import { ExplorerPage } from './ExplorerPage';

describe('ExplorerPage — "Analyzable only" toggle', () => {
  it('drops non-analyzable rows and updates the count when toggled', async () => {
    render(<ExplorerPage />);

    // Wait for the mocked rows to load. The toggle button only appears once
    // there are excluded rows (excludedCount === 2 here).
    const toggle = await screen.findByText('Hide excluded (2)');

    // Before toggling: all rows present and the filtered/total count is hidden
    // because filtered.length === rows.length.
    expect(screen.getByText('Devi')).toBeTruthy();
    expect(screen.getByText('Aishah')).toBeTruthy();
    expect(screen.queryByText(/3\s*\/\s*5/)).toBeNull();

    fireEvent.click(toggle);

    // After toggling: the two excluded rows are gone and the "3 / 5" count
    // appears — proving `filtered` recomputed in response to the toggle.
    await waitFor(() => {
      expect(screen.queryByText('Devi')).toBeNull();
    });
    expect(screen.queryByText('Ehsan')).toBeNull();
    expect(screen.getByText('Aishah')).toBeTruthy();
    expect(screen.getByText(/3\s*\/\s*5/)).toBeTruthy();
  });
});
