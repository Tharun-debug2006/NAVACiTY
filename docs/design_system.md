# NavaCity — Design system

The rules that keep the public and the authority interface looking like one
product. **Change a value here, not in a page.** The tokens live in
`frontend/src/styles/tokens.css` (the single source of truth) and are mirrored
as Tailwind utilities in `frontend/tailwind.config.js`.

---

## 1. The colour tokens

| Token | Value | Used for |
|---|---|---|
| `--nc-metro` | `#1D3FBF` (indigo-700) | metro lines, primary actions, the selected nav item |
| `--nc-metro-soft` | `#EEF2FF` (indigo-50) | tinted metro backgrounds |
| `--nc-bus` | `#B7791F` (amber-600) | bus routes, the bus family |
| `--nc-bus-soft` | `#FFFBEB` (amber-50) | tinted bus backgrounds |
| `--nc-crowd-low` | `#0F8A5F` (emerald-600) | the "Low" crowd level |
| `--nc-crowd-moderate` | `#0369A1` (sky-600) | the "Moderate" crowd level |
| `--nc-crowd-high` | `#C2410C` (orange-600) | the "High" crowd level |
| `--nc-crowd-critical` | `#B91C1C` (red-700) | the "Critical" crowd level |
| `--nc-heading` | `#0F172A` (slate-900) | headings |
| `--nc-body` | `#334155` (slate-700) | body text |
| `--nc-muted` | `#64748B` (slate-500) | secondary text |
| `--nc-border` | `#E2E8F0` (slate-200) | borders and table rules |
| `--nc-page` | `#F8FAFC` (slate-50) | the page background |
| `--nc-surface` | `#FFFFFF` | cards |
| `--nc-notice-bg` / `-text` / `-border` | amber-50 / amber-900 / amber-200 | the simulated-data notice |
| `--nc-focus` | `#4F46E5` (indigo-600) | the focus ring |

### The rules

1. **Metro is indigo, bus is amber.** Every screen, every chart and the map
   use the same two families. On the map a metro line is **solid** and a bus
   route is **dashed**.
2. **The crowd palette is never used for a route** and a route colour is never
   used for a crowd level.
3. **Colour is never the only carrier of meaning.** Every crowd level has an
   icon shape (filled circle → half-filled circle → triangle → octagon) *and*
   a text label. Every mode has a text label. Every route on the map has its
   id and name in the tooltip.
4. **A page uses at most three accent colours at once** (the metro family, the
   bus family and the crowd legend).

---

## 2. Typography

* Font: `ui-sans-serif, system-ui, "Segoe UI", Roboto, "Noto Sans", sans-serif`
  — a system stack, so Indian-language text renders with the same family.
* Scale: **12 / 14 / 16 / 18 / 24 / 32 px**.
  * Body: 16 px on the public page, 14 px on the dense authority tables.
* Headings are **semibold** (600), never bold (700).
* Body line-height 1.5.
* Numbers in tables and KPI cards use `tabular-nums` so that the columns
  align.

---

## 3. Spacing and shape

* A **4 px** base grid (`--nc-space-1` … `--nc-space-8`).
* Card padding: **20 px** (public) and **16 px** (authority).
* Gap between cards: **16 px**.
* Border radius: **12 px** (cards), **8 px** (inputs and buttons), **999 px**
  (badges).
* Shadows: none, or a single `shadow-sm`. No glass effects, no gradients.
* Maximum content width: **1152 px**, centred (`max-w-content`).

---

## 4. The components

| Component | File | What it guarantees |
|---|---|---|
| `CrowdBadge` | `components/CrowdBadge.jsx` | icon + text label + optional percentage; never colour alone |
| `OccupancyBar` | `components/CrowdBadge.jsx` | the occupancy bar with the 40 / 65 / 85 % threshold ticks |
| `ModeSwitch` | `components/ModeSwitch.jsx` | the Metro / Bus segmented control with arrow-key support and `aria-pressed` |
| `StationPicker` | `components/StationPicker.jsx` | the From / To pickers, filtered to the chosen route, with a swap button |
| `AnswerCard` | `components/AnswerCard.jsx` | the single primary answer: crowd badge, one sentence, wait / ride / total, the occupancy bar |
| `AlternativeCard` | `components/AlternativeCard.jsx` | one alternative: route, mode, total time, crowd badge, transfers, the difference against the chosen route |
| `StatCard` | `components/StatCard.jsx` | a KPI card with a label, a value, a unit and a context line |
| `ChartCard` | `components/ChartCard.jsx` | a title, a visible legend, the chart body and a caption with the data period |
| `LegendItem` | `components/ChartCard.jsx` | one legend entry (a coloured line plus its name) |
| `DataNotice` | `components/DataNotice.jsx` | the simulated-data banner, identical on every page |
| `EmptyState` | `components/States.jsx` | a short message plus an action — never a blank panel |
| `ErrorState` | `components/States.jsx` | a short message plus a retry action, `role="alert"` |
| `LoadingSkeleton` | `components/States.jsx` | skeletons shaped like the content — never a spinner on an empty page |
| `CollapsibleSection` | `components/CollapsibleSection.jsx` | a foldable section with an `aria-expanded` button |
| `TransitMap` | `components/TransitMap.jsx` | the schematic map: one colour system, visible station labels, a legend |
| `formatNumber` etc. | `lib/format.js` | the one number formatter (Indian grouping) |

---

## 5. Layout rules

### The public interface (mobile first)

* Designed at **375 px**, enhanced at **768 px** and **1280 px**.
* The controls stack vertically on mobile and become a row on desktop.
* The **answer card is the first thing below the header** on every viewport.
  Once a result exists it sits **above** the controls.
* On the first load the controls are open; once a result exists they collapse
  into a summary bar ("Metro · M1 Blue Line · Typical weekday 08:00 · Change")
  that expands when tapped.
* Touch targets are at least **44 × 44 px** (the `.btn` class has
  `min-h-[44px]`).
* The header is sticky and carries only the product name, a "Simulated data"
  pill and the navigation.

### The authority interface (desktop first)

* Minimum supported width **1024 px**.
* A **left sidebar** with the four sections: Overview, Metro, Bus, Model & Data.
  A sidebar, not tabs, so the section is always visible. The sidebar is
  `sticky`, so it stays visible while the page scrolls.
* Each section has a page title, a one-line description and a **right-aligned
  filter bar** (date, route, severity). The filter bar is the same in the
  Metro and the Bus section.
* Tables: sticky header row, zebra striping with slate-50, right-aligned
  numbers, units in the column heading ("Occupancy %", "Peak load,
  pax/vehicle").
* Charts: Recharts with a fixed height of **280 px**, a visible legend above
  the plot, axis titles with units, and a caption below giving the data period
  and the granularity.

---

## 6. Copy and tone

* Plain English for passengers. "Stretch between stations" or the two station
  names instead of "segment". "How full" instead of "occupancy" in the
  passenger-facing copy. The model name is never shown to a passenger.
* Short sentences. Each crowd level has one sentence describing what a
  passenger will experience.
* Authority copy is precise and neutral: it states the unit, the period and
  the heuristic nature of a recommendation.
* No exclamation marks, no marketing language.

---

## 7. Accessibility checklist

* Body text has at least 4.5 : 1 contrast; large text and graphics at least
  3 : 1.
* Every icon-only button has an `aria-label` (for example the swap button of
  the `StationPicker`).
* Every chart has a visible legend, an axis unit and a caption; the data is
  also available as a table where it matters (the route table, the peak hours).
* Colour is never the only carrier of meaning.
* `prefers-reduced-motion` disables the entrance animations
  (`frontend/src/styles/tokens.css`).
* Every form control has a visible `<label>`; errors are announced with
  `role="alert"`.
* The focus ring is **2 px solid indigo with a 2 px offset** and is never
  removed (`index.css`, `:focus-visible`).
