export const theme = {
  navy:          '#1B2A4A',
  navyMid:       '#243759',
  blue:          '#1D6FE8',
  blueLight:     '#3B8BF5',
  steel:         '#B8CCE4',
  bg:            '#F4F6F9',
  surface:       '#ffffff',
  surface2:      '#F8FAFC',
  border:        '#D6E0ED',
  border2:       '#EEF2F7',
  textPrimary:   '#1B2A4A',
  textSecondary: '#5A6E8C',
  textMuted:     '#9EB3CC',
  success:       '#22C55E',
  successBg:     '#F0FDF4',
  warning:       '#F59E0B',
  warningBg:     '#FFFBEB',
  danger:        '#EF4444',
  dangerBg:      '#FEF2F2',
  info:          '#1D6FE8',
  infoBg:        '#EFF6FF',
  purple:        '#6D4FD4',
  purpleBg:      '#F0EEFF',
} as const;

export const darkTheme = {
  bg:           '#0F1923',
  surface:      '#1A2633',
  surface2:     '#233043',
  border:       '#2E3F55',
  border2:      '#1E2E42',
  textPrimary:  '#E8EDF2',
  textSecondary:'#8DA4BF',
  textMuted:    '#4A6080',
  successBg:    '#052e16',
  warningBg:    '#1c1400',
  dangerBg:     '#1f0a0a',
  infoBg:       '#0c1e3a',
  purpleBg:     '#1e1a3a',
} as const;

export function applyTheme(dark: boolean): void {
  const root = document.documentElement;
  const t = dark ? { ...theme, ...darkTheme } : theme;
  Object.entries(t).forEach(([k, v]) => {
    root.style.setProperty('--' + k.replace(/([A-Z])/g, '-$1').toLowerCase(), v);
  });
}
