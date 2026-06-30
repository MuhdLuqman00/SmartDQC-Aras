// @vitest-environment jsdom
//
// Guards Track C: the advisory reroute card shown when /upload/preview
// detects source_type="general" but returns a reroute recommendation.
// Verifies:
//   1. Card renders after a preview that includes a reroute card.
//   2. Clicking Accept fires a second /upload/preview call whose FormData
//      carries source_type equal to the recommended schema.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Capture the onDrop callback from inside useDropzone so the test can
// trigger a file drop. Must use vi.hoisted so it's available inside the
// (hoisted) vi.mock factory below.
const dropzoneRef = vi.hoisted(() => ({ onDrop: null as ((files: File[]) => void) | null }));

vi.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop }: { onDrop: (files: File[]) => void }) => {
    dropzoneRef.onDrop = onDrop;
    return { getRootProps: () => ({}), getInputProps: () => ({}), isDragActive: false };
  },
}));

const mockPost = vi.hoisted(() => vi.fn());
vi.mock('../api/client', () => ({
  api: {
    post: mockPost,
    get: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock('../context/SessionContext', () => ({
  useSession: () => ({ setSession: vi.fn(), cacheId: '', filename: '' }),
}));

vi.mock('../context/LanguageContext', () => ({
  useLang: () => ({ lang: 'en', setLang: () => {}, toggleLang: () => {}, t: (en: string) => en }),
}));

vi.mock('../components/RagBadge', () => ({ RagBadge: () => null, scoreToRag: () => 'green' }));
vi.mock('../lib/persistWarning', () => ({ persistWarning: () => null }));
vi.mock('../lib/issueCatalog', () => ({ translateIssue: (c: unknown) => c, translateRule: (c: unknown) => c }));
vi.mock('../lib/issueFix', () => ({ suggestFix: () => null }));

import { UploadPage } from './UploadPage';

const REROUTE_CARD = {
  kind: 'reroute', type: 'wide_multiyear', confidence: 0.8,
  matched_count: 1, total_signals: 5,
  signals: [{ name: 'ic no passport', evidence: 'column IC_NO_PASSPORT matched', matched: true }],
  rationale_en: 'Column names closely match the MyVASS/TASKA wide format.',
  rationale_bm: 'Nama lajur sepadan dengan format MyVASS/TASKA lebar.',
};

const PREVIEW_GENERAL = {
  cache_id: 'cache-1', filename: 'data.csv', source_type: 'general',
  rows: 2, columns: ['IC_NO_PASSPORT', 'Nama'], sample: [],
  auto_mapping: {}, unmapped_columns: [], sheets: [], active_sheet: null,
  page: 1, page_size: 20, total_pages: 1,
  recommendations: [REROUTE_CARD],
};

const PREVIEW_MYVASS = {
  ...PREVIEW_GENERAL,
  source_type: 'wide_multiyear',
  recommendations: [],
};

describe('UploadPage — advisory reroute card (Track C)', () => {
  beforeEach(() => { mockPost.mockReset(); });

  it('renders reroute card and re-previews with correct schema on Accept', async () => {
    mockPost
      .mockResolvedValueOnce({ data: PREVIEW_GENERAL })   // first preview (general + reroute card)
      .mockResolvedValueOnce({ data: PREVIEW_MYVASS });   // accept re-preview (wide_multiyear, no card)

    render(<MemoryRouter><UploadPage /></MemoryRouter>);

    // Trigger a file drop to populate the files state
    await waitFor(() => expect(dropzoneRef.onDrop).not.toBeNull());
    dropzoneRef.onDrop!([new File(['col\nval\n'], 'data.csv', { type: 'text/csv' })]);

    // Click "Next" to run /upload/preview
    const nextBtn = await screen.findByRole('button', { name: /next/i });
    fireEvent.click(nextBtn);

    // Card renders in step 2
    await waitFor(() => {
      expect(screen.getByText(/Schema advisory/i)).toBeTruthy();
    });
    expect(screen.getByText(/resembles MYVASS/i)).toBeTruthy();
    expect(screen.getByText(/ic no passport/i)).toBeTruthy();

    // Click Accept — triggers a second /upload/preview with source_type=wide_multiyear
    fireEvent.click(screen.getByRole('button', { name: /Re-route as MYVASS/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledTimes(2);
    });
    const secondCallArgs = mockPost.mock.calls[1] as [string, FormData];
    expect(secondCallArgs[1].get('source_type')).toBe('wide_multiyear');
  });

  it('dismisses card and proceeds as general when Keep is clicked', async () => {
    mockPost.mockResolvedValueOnce({ data: PREVIEW_GENERAL });

    render(<MemoryRouter><UploadPage /></MemoryRouter>);

    await waitFor(() => expect(dropzoneRef.onDrop).not.toBeNull());
    dropzoneRef.onDrop!([new File(['col\nval\n'], 'data.csv', { type: 'text/csv' })]);

    const nextBtn = await screen.findByRole('button', { name: /next/i });
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(screen.getByText(/Schema advisory/i)).toBeTruthy();
    });

    // Dismiss — card disappears, no second post fired
    fireEvent.click(screen.getByRole('button', { name: /Keep as General/i }));
    await waitFor(() => {
      expect(screen.queryByText(/Schema advisory/i)).toBeNull();
    });
    expect(mockPost).toHaveBeenCalledTimes(1);
  });
});
