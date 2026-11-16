# Kaltstart design system

Direction **Ignition** (chosen by the owner, 2026-11-16): graphite, an
ignition orange, and since the owner's first try of the app a second, cold
colour (ice blue) for information, so the app reads livelier and airier. A
cold start that catches fire. The app should feel fast
and startup-like, different from the blue of most tech sites, with a premium
touch that comes from restraint: one colour for actions, fine borders,
figures in a monospace, dense rows.

Reference studied: tech-internships.eu (the owner's pick): dark first, a
single action colour, dense bordered rows, small tags. Kaltstart keeps that
density and replaces its blue and Inter with its own colour and type. No
other site was compared (UXKIN was not used).

Every page uses the tokens below by name (CSS variables), never raw values.

## Colour

Dark is the default; light follows the same roles. All text pairs below
reach at least 4.5:1 (checked).

| Token | Dark | Light | Role |
|---|---|---|---|
| `--bg` | `#0B0D12` | `#F7F7F8` | Page background |
| `--surface` | `#12151C` | `#FFFFFF` | Rows, cards, inputs, the mail preview |
| `--surface-2` | `#1A1E27` | `#F0F1F3` | Secondary buttons, tags, hover of a row |
| `--border` | `#252A35` | `#E2E4E9` | 1px borders of rows, inputs, cards |
| `--border-strong` | `#353B48` | `#C9CDD5` | Hover and selected borders |
| `--text` | `#ECEEF3` | `#12141A` | Body text and headings |
| `--muted` | `#98A1B0` | `#5B6372` | Secondary text: sector, city, dates, helper text |
| `--faint` | `#6E7685` | `#9AA1AD` | Disabled text and decorative marks only, never body text |
| `--primary` | `#FF7A2F` | `#FF7A2F` | The one action colour: primary buttons, focus ring, the "Kalt" of the logo |
| `--on-primary` | `#140A03` | `#140A03` | Text on primary buttons (7.5:1) |
| `--primary-dim` | `#7A4220` | `#FFD9C2` | Hover border of a row, selected chip background |
| `--primary-soft` | `#33231F` | `#FFF1E8` | Tinted backgrounds: the suggested person, a selected choice, the Small size tag, step numbers |
| `--accent` | `#7CC4FF` | `#1D6FB8` | The cold second colour, for information only, never for actions: the Medium size tag, "Person suggested", the kicker of a page, finished steps |
| `--accent-soft` | `#212E3C` | `#EAF4FD` | Tinted background of accent tags and notes |
| `--link` | `#FF8A45` | `#B8470A` | Links in text |
| `--success` | `#3DD68C` | `#11804F` | Sent, positive reply |
| `--warning` | `#F5B83D` | `#9A6400` | "Last slot", the 72-hour reminder |
| `--error` | `#FF6B6B` | `#C72C2C` | Refusals and form errors |

No gradient, no glow, no glass. Status colours appear as text or a 1px
border, never as large fills. Tinted backgrounds (`--primary-soft`,
`--accent-soft`) are used only for tags, the selected choice and the
suggested person, so colour points at what matters.

## Typography

- **Geist** for everything, figures included, with tabular figures so
  amounts and dates line up. **Geist Mono** is kept in the files but no
  longer used on screen: the owner found the monospaced labels harsh
  (2026-11-16). Both fonts are under the SIL Open Font License and are
  served from the app itself (no third-party font service), as variable
  woff2 files with their licence.
- Figures use `font-variant-numeric: tabular-nums`.
- Headings: weight 700, letter spacing -0.03em at 26px and above, -0.02em
  below.

| Token | Size / line height | Use |
|---|---|---|
| `--text-xs` | 12 / 16 | Tags, mono labels |
| `--text-sm` | 13 / 18 | Secondary text in rows, helper text |
| `--text-base` | 16 / 24 | Body text, inputs, the mail preview |
| `--text-md` | 15 / 22 | Row titles, buttons |
| `--text-lg` | 20 / 28 | Section headings ("Step 1 · Who are you writing to?") |
| `--text-xl` | 26 / 32 | Page titles |
| `--text-2xl` | 36 / 40 | Sign-in page title only |

Body text is never below 16px; rows use 15px titles and 13px details, as
dense lists do. Running text is at most 68 characters wide.

## Spacing and layout

- Scale (4px base): `--space-1` 4, `--space-2` 8, `--space-3` 12,
  `--space-4` 16, `--space-5` 24, `--space-6` 32, `--space-7` 48,
  `--space-8` 64.
- Content width 1120px, centred, with a 16px side gutter on phones; no
  horizontal scroll at 360px. Pages open with 48px above the title.
- A row of the company list: 16px vertical and 18px horizontal padding,
  8px between rows. On phones the columns stack in the row.
- The company page is one column of at most 720px.

## Shape and depth

- Radius: `--radius-sm` 6px (tags, small chips), `--radius-md` 8px
  (buttons, inputs), `--radius-lg` 10px (rows, cards, the mail preview),
  `--radius-full` for the pending-mails pill.
- Depth comes from borders, not shadows. One shadow only, in light mode,
  for menus that float: `0 8px 24px rgba(18, 20, 26, 0.12)`.

## Components

- **Primary button**: `--primary` background, `--on-primary` text, weight
  600. Hover: 8% darker. Focus: 2px `--primary` ring with 2px offset.
  Disabled: `--surface-2` background, `--faint` text. One primary button per
  screen ("Generate my mail", "Create account", "Save").
- **Secondary button**: `--surface-2` background, 1px `--border`, `--text`.
  Used for Copy, I sent it, filters.
- **Quiet button**: text only in `--muted`, underline on hover. Used for
  Abandon, Delete my account.
- **Copy button**: secondary; after a click it reads "Copied" for 2 seconds
  with a check icon.
- **Inputs**: `--surface` background, 1px `--border`, 8px radius, 16px text;
  focus ring as buttons; error shows a 1px `--error` border and a 13px
  message under the field. Word counters in Geist Mono, `--warning` at 90 %
  of the limit, `--error` above it.
- **Company row**: `--surface`, 1px `--border`, 10px radius; hover border
  `--border-strong` and background `--surface-2`; the whole row is the link.
- **Tag** (month, "Suggested"): a pill, Geist 12px weight 500,
  `--surface-2` background, `--muted` text.
- **Size tag**: a pill (full radius), Geist 12px weight 500, sentence case,
  with a 6px dot of its colour before the word. Small: `--primary-soft` and
  `--link`; Medium: `--accent-soft` and `--accent`; Large: `--surface-2`
  and `--text` with a 1px `--border-strong`. A one-line legend under the
  filters says what each size means for the student.
- **Kicker**: Geist 13px weight 600 in `--accent`, above a page title.
- **Checkbox and radio**: drawn by the app, 18px, `--surface` with a 1.5px
  `--border-strong` border; hover border `--primary`; a checked checkbox is
  filled `--primary` with an `--on-primary` tick; a checked radio has a
  `--primary` border and dot.
- **In-progress counter** (navigation): "N of 5 mails in progress", a pill
  that links to My mails, where the limit is explained.
- **Stepper** (company page): three numbered steps in a row; the number in
  a 24px circle, `--primary-soft` with `--link` for the current step,
  `--accent-soft` with `--accent` and a check for a finished one.
- **Choice card**: a whole card is the label of a radio button; selected,
  it takes a `--primary` border and `--primary-soft` background. Used for
  "who are you writing to".
- **Navigation**: logo ("**Kalt**start", "Kalt" in `--primary`), then
  Companies, My mails, Profile; on the right the pending pill
  ("2 / 5 pending") in Geist Mono. One line on desktop; on phones the links
  sit in a row under the logo.
- **Notices**: the 72-hour reminder and refusals use a 1px coloured border
  (`--warning` or `--error`) on `--surface`, with an icon; never a filled
  coloured box.
- **Mail preview**: `--surface`, mono labels SUBJECT and TO in `--muted`,
  the body in Geist 16px with its own line breaks.

## Icons and imagery

- **Lucide** icons (ISC licence), inline SVG, 16px, stroke 1.75, colour
  `currentColor`. No emoji in the interface.
- No photos and no illustrations: the content is the companies. Company
  logos are not shown (not in the data).

## Motion

Only to confirm an action: 120ms colour transitions on hover and focus, the
"Copied" change. Nothing moves on page load. `prefers-reduced-motion` turns
transitions off.

## Theme switch

The app follows the system setting and offers a toggle in the footer,
remembered in the browser.
