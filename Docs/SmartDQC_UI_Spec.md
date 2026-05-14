# SmartDQC — UI Specification
### Internal Reference Document

---

## §1 — Overview and Design System

### Product
SmartDQC is a web-based data quality and clinical analytics platform for Malaysia's Ministry of Health (KKM). It ingests MyVASS and Klinik Kesihatan datasets, runs automated cleaning and quality scoring, and produces district-level nutrition reports.

### Palette — KKM Navy (canonical)
| Token            | Hex       | Usage                        |
|------------------|-----------|------------------------------|
| primary          | #1B2A4A   | Header, sidebar, primary CTAs |
| primary-dark     | #0F1B2F   | Hover states, active items    |
| primary-light    | #2E4A7A   | Secondary buttons, badges     |
| accent           | #C8962E   | Warning badges, highlights    |
| surface          | #F5F7FA   | Page background               |
| surface-card     | #FFFFFF   | Card backgrounds              |
| text-primary     | #1A1A2E   | Body copy                     |
| text-secondary   | #4A5568   | Labels, captions              |
| success          | #2D7D46   | Passing indicators            |
| danger           | #C0392B   | Failing indicators            |

> All four existing teal components (`ReportPage.tsx`, `ReportOptionsPanel.tsx`, `ReportPreviewPane.tsx`, `useReportGeneration.ts`) must be updated to use the navy palette before Day 6 UI is integrated.

### Typography
- Font: DM Sans (Google Fonts, existing in report components)
- Heading: DM Sans 600; Body: DM Sans 400; Monospace: JetBrains Mono (code/IC numbers)

### Routing
All pages live under a single React SPA. Auth-gated routes redirect to `/login` if no valid JWT is in `localStorage`.

| Path          | Component          | Auth Required |
|---------------|--------------------|---------------|
| /login        | LoginPage          | No            |
| /             | DashboardPage      | Yes           |
| /upload       | UploadPage         | Yes           |
| /explorer     | ExplorerPage       | Yes           |
| /quality      | QualityPage        | Yes           |
| /cleaning     | CleaningPage       | Yes           |
| /ai           | AIPage             | Yes           |
| /geo          | GeoPage            | Yes           |
| /reports      | ReportsPage        | Yes           |
| /chatbot      | ChatbotPage        | Yes           |
| /datasets     | DatasetLibraryPage | Yes           |
| /history      | HistoryPage        | Yes           |
| /settings     | SettingsPage       | Yes (admin)   |
| /audit        | AuditPage          | Yes (admin)   |

### Global Layout
- Top navbar: logo + nav links + user chip (username, role badge) + logout button
- Sidebar: collapsible, 64px icons collapsed / 220px expanded
- Content area: full-height scroll, 24px padding

### API Base URL
All API calls use `VITE_API_BASE_URL` env var (default `http://localhost:8000`). Set to remote GPU server URL in production.

### Auth
JWT stored in `localStorage` as `smartdqc_token`. Sent as `Authorization: Bearer <token>` header. Expiry: 8 hours. On 401 response: clear token and redirect to `/login`.

---

## §2 — Login Page (`/login`)

### Purpose
Authenticate user, obtain JWT, redirect to `/`.

### Layout
- Centered card (480px wide)
- Navy left panel: KKM logo + product name "SmartDQC"
- Right panel: username input, password input, "Masuk" button
- Error banner: danger red background if 401 returned

### API
`POST /auth/login` — form-encoded `username` + `password`

Response:
```json
{ "access_token": "ey...", "token_type": "bearer", "role": "admin" }
```

### Behaviour
1. On submit: POST to `/auth/login`
2. Store `access_token` in `localStorage["smartdqc_token"]`
3. On success: navigate to `/`
4. On 401: show "Nama pengguna atau kata laluan tidak sah" error banner
5. Default dev credentials: `admin` / `ADMIN_SEED_PASSWORD_PLACEHOLDER`

### Components
- `LoginCard` — centered form wrapper
- `useAuth` hook — wraps login/logout/me calls; exports `{ user, login, logout, isAuthenticated }`

---

## §3 — Dashboard Page (`/`)

### Purpose
System overview: recent sessions, quality trend, quick-action buttons.

### Layout
- Top row: 4 KPI cards (Active Sessions, Avg Quality Score, Total Rows Processed, Alerts)
- Middle row: Quality Score Trend sparkline (last 10 sessions) | Recent Sessions table
- Bottom row: Quick Actions — Upload New Dataset / View Reports / Open Chatbot

### APIs
- `GET /sessions` → `[{ cache_id, filename, source_type, row_count, quality_score }]`
- `GET /health` → `{ status: "ok" }` (green/red dot in header)

### Recent Sessions Table
| Column  | Source field  | Notes                                   |
|---------|---------------|-----------------------------------------|
| File    | filename      |                                         |
| Source  | source_type   |                                         |
| Rows    | row_count     |                                         |
| Quality | quality_score | Badge: ≥80 green, 60–79 amber, <60 red |
| Actions |               | View → /quality?cache_id=X              |

### Components
- `KpiCard` — icon, label, value, delta vs previous session
- `QualitySparkline` — recharts LineChart, navy stroke
- `SessionsTable` — sortable, row click navigates to /quality
- `QuickActions` — 3 navy CTA buttons
