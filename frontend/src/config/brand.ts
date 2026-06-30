/* Deployment branding — the single place that names the owning organisation.
 *
 * Neutral defaults so the app ships unbranded; set these to your organisation's
 * identity per deployment (or wire to import.meta.env values). Presentation
 * only — no domain logic depends on these. Bilingual (EN / BM) to match the
 * app's bilingual UI. */
export const BRAND = {
  appName: 'SmartDQC',
  orgNameEn: 'Your Organisation',
  orgNameBm: 'Organisasi Anda',
} as const;
