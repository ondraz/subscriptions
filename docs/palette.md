# Color Palette

Single source of truth for Tidemill colors. Implemented in:

- **Frontend:** `frontend/src/lib/colors.ts`, `frontend/src/index.css`
- **Plotly/Reports:** `tidemill/reports/_style.py`
- **Logo/Favicon:** `docs/assets/*.svg`, `frontend/public/favicon.svg`
- **Documentation:** `docs/mkdocs.yml` (theme: deep orange / amber)

---

## Brand

| Swatch | Name | Hex | Usage |
|--------|------|-----|-------|
| ![#F59E0B](https://placehold.co/24x24/F59E0B/F59E0B) | **Amber 500** | `#F59E0B` | Primary brand, UI primary, colorway lead |
| ![#EA580C](https://placehold.co/24x24/EA580C/EA580C) | Orange 600 | `#EA580C` | Hub fill, favicon, past-due status |
| ![#F97316](https://placehold.co/24x24/F97316/F97316) | Orange 500 | `#F97316` | Logo blade gradient start |
| ![#C2410C](https://placehold.co/24x24/C2410C/C2410C) | Orange 700 | `#C2410C` | Logo blade gradient end |
| ![#F59E0B](https://placehold.co/24x24/F59E0B/F59E0B) | Amber 500 | `#F59E0B` | Logo accent blade gradient start |
| ![#D97706](https://placehold.co/24x24/D97706/D97706) | Amber 600 | `#D97706` | Logo accent blade gradient end |
| ![#F97316](https://placehold.co/24x24/F97316/F97316) | Orange 500 | `#F97316` | Logo wordmark text |

## Semantic (charts & metrics)

| Swatch | Role | Hex | Mapped to |
|--------|------|-----|-----------|
| ![#16A34A](https://placehold.co/24x24/16A34A/16A34A) | **Positive / Growth** | `#16A34A` | new, active, converted, GRR |
| ![#2563EB](https://placehold.co/24x24/2563EB/2563EB) | **Expansion** | `#2563EB` | expansion, NRR |
| ![#EAB308](https://placehold.co/24x24/EAB308/EAB308) | **Contraction** | `#EAB308` | contraction |
| ![#DC2626](https://placehold.co/24x24/DC2626/DC2626) | **Churn / Negative** | `#DC2626` | churn, canceled, expired, logo churn |
| ![#8B5CF6](https://placehold.co/24x24/8B5CF6/8B5CF6) | **Special** | `#8B5CF6` | reactivation, ARPU |
| ![#F59E0B](https://placehold.co/24x24/F59E0B/F59E0B) | **Brand accent** | `#F59E0B` | trialing, revenue churn |
| ![#EA580C](https://placehold.co/24x24/EA580C/EA580C) | **Warning** | `#EA580C` | past due |
| ![#78716C](https://placehold.co/24x24/78716C/78716C) | **Neutral** | `#78716C` | starting MRR, pending, grey |
| ![#1C1917](https://placehold.co/24x24/1C1917/1C1917) | **Dark** | `#1C1917` | ending MRR |

## Multi-series colorway

Default cycle for charts with multiple series, in order:

| # | Swatch | Hex | Name |
|---|--------|-----|------|
| 1 | ![#F59E0B](https://placehold.co/24x24/F59E0B/F59E0B) | `#F59E0B` | amber |
| 2 | ![#2563EB](https://placehold.co/24x24/2563EB/2563EB) | `#2563EB` | blue |
| 3 | ![#16A34A](https://placehold.co/24x24/16A34A/16A34A) | `#16A34A` | green |
| 4 | ![#8B5CF6](https://placehold.co/24x24/8B5CF6/8B5CF6) | `#8B5CF6` | violet |
| 5 | ![#DC2626](https://placehold.co/24x24/DC2626/DC2626) | `#DC2626` | red |
| 6 | ![#0891B2](https://placehold.co/24x24/0891B2/0891B2) | `#0891B2` | cyan |
| 7 | ![#DB2777](https://placehold.co/24x24/DB2777/DB2777) | `#DB2777` | pink |
| 8 | ![#84CC16](https://placehold.co/24x24/84CC16/84CC16) | `#84CC16` | lime |
| 9 | ![#78716C](https://placehold.co/24x24/78716C/78716C) | `#78716C` | stone |

## Sequential scale (heatmaps)

Orange ramp used by Plotly `colorscale_sequential`:

| Position | Swatch | Hex | Tailwind |
|----------|--------|-----|----------|
| 0.00 | ![#FFF7ED](https://placehold.co/24x24/FFF7ED/FFF7ED) | `#FFF7ED` | orange-50 |
| 0.25 | ![#FED7AA](https://placehold.co/24x24/FED7AA/FED7AA) | `#FED7AA` | orange-200 |
| 0.50 | ![#FB923C](https://placehold.co/24x24/FB923C/FB923C) | `#FB923C` | orange-400 |
| 0.75 | ![#EA580C](https://placehold.co/24x24/EA580C/EA580C) | `#EA580C` | orange-600 |
| 1.00 | ![#431407](https://placehold.co/24x24/431407/431407) | `#431407` | orange-950 |

## Cohort retention heatmap

Discrete buckets (green = good retention, red = poor):

| Threshold | Swatch | Hex | Tailwind |
|-----------|--------|-----|----------|
| >= 90% | ![#DCFCE7](https://placehold.co/24x24/DCFCE7/DCFCE7) | `#DCFCE7` | green-100 |
| >= 70% | ![#BBF7D0](https://placehold.co/24x24/BBF7D0/BBF7D0) | `#BBF7D0` | green-200 |
| >= 50% | ![#FEF08A](https://placehold.co/24x24/FEF08A/FEF08A) | `#FEF08A` | yellow-200 |
| >= 30% | ![#FED7AA](https://placehold.co/24x24/FED7AA/FED7AA) | `#FED7AA` | orange-200 |
| < 30%  | ![#FECACA](https://placehold.co/24x24/FECACA/FECACA) | `#FECACA` | red-200 |

## UI theme (CSS custom properties)

Defined in `frontend/src/index.css`:

| Property | Value | Purpose |
|----------|-------|---------|
| `--color-primary` | `#F59E0B` | Buttons, links, focus rings |
| `--color-primary-foreground` | `#ffffff` | Text on primary |
| `--color-accent` | `#FFFBEB` | Hover/highlight backgrounds |
| `--color-accent-foreground` | `#1C1917` | Text on accent |
| `--color-destructive` | `#DC2626` | Danger actions |
| `--color-ring` | `#F59E0B` | Focus outlines |
| `--color-border` | `#e5e5e5` | Default borders |
| `--color-muted` | `#f5f5f5` | Page background |

## Neutral tones (stone)

Warm grays used for text, grids, and borders:

| Swatch | Hex | Tailwind | Usage |
|--------|-----|----------|-------|
| ![#E7E5E4](https://placehold.co/24x24/E7E5E4/E7E5E4) | `#E7E5E4` | stone-200 | Grid lines |
| ![#D6D3D1](https://placehold.co/24x24/D6D3D1/D6D3D1) | `#D6D3D1` | stone-300 | Axis lines |
| ![#78716C](https://placehold.co/24x24/78716C/78716C) | `#78716C` | stone-500 | Secondary text, neutral data |
| ![#44403C](https://placehold.co/24x24/44403C/44403C) | `#44403C` | stone-700 | Body text, hover labels |
| ![#1C1917](https://placehold.co/24x24/1C1917/1C1917) | `#1C1917` | stone-900 | Titles, headings |

## Logo assets

All in `docs/assets/`:

| File | Variant |
|------|---------|
| `icon-color.svg` | Orange/amber gradient icon |
| `icon-bw.svg` | Black icon |
| `icon-white.svg` | White icon (dark backgrounds) |
| `logo-color.svg` | Icon + wordmark, color |
| `logo-bw.svg` | Icon + wordmark, black |
| `logo-white.svg` | Icon + wordmark, white |
| `favicon.svg` | Flat orange/amber for browser tabs |
