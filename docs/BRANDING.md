# EduZone: Brand, Colours and Theme

> The full reference for how EduZone looks. Use it for screens, posts, posters, slides, emails and print.
>
> **The source of truth is the code:** `frontend/packages/ui/src/tokens.css`. If this file and the tokens
> disagree, the tokens win and this file must be corrected. `FRONTEND.md` section 9 is the short version.
>
> Written from the code on 2026-11-24. Contrast ratios are calculated with the WCAG 2.1 formula.

**Contents:** [1 Brand](#1-the-brand-in-one-page) · [2 Logo](#2-logo) · [3 Colours](#3-colours) ·
[4 Contrast](#4-contrast-and-safe-combinations) · [5 Typography](#5-typography) ·
[6 Shape, shadow, layout](#6-shape-shadow-and-layout) · [7 Motion](#7-motion) ·
[8 Textures](#8-textures-and-effects) · [9 Components](#9-components) ·
[10 Covers, avatars, icons](#10-covers-avatars-and-icons) · [11 Photography](#11-photography) ·
[12 Voice](#12-voice-and-wording) · [13 Outside the website](#13-using-the-brand-outside-the-website) ·
[14 Rules](#14-rules) · [15 Copy-paste tokens](#15-copy-paste-tokens) · [16 Known gaps](#16-known-gaps)

---

## 1. The brand in one page

| | |
|---|---|
| **Name** | EduZone (capital E, capital Z, one word) |
| **Company** | SwitchOps Tech (Pvt) Ltd, Sri Lanka |
| **What it is** | A learning marketplace: tuition classes and self-paced courses |
| **Direction** | **Scholarly modern**: "Scholarly, modern, calm." |
| **Feels like** | Calm and trustworthy for parents, premium enough to stand beside global platforms |
| **Primary colour** | Forest green `#124A33` |
| **Emphasis colour** | Warm gold `#D4A03F` |
| **Page background** | Ivory paper `#FAF8F3` |
| **Text colour** | Ink `#14201A` |
| **Heading font** | Fraunces |
| **Text font** | Instrument Sans |
| **Sinhala font** | Noto Sans Sinhala |
| **Theme** | Light only in v1. Dark *panels* are part of the look; dark *mode* is not built |

**What each colour says**

- **Forest green:** trust, growth, study. It carries the brand and every main action.
- **Warm gold:** achievement. It is for *emphasis only*, never a second main colour.
- **Ivory paper:** a page in a good book. It replaces cold grey and pure white page backgrounds.

**Balance on a typical screen (a guide):** about 70% ivory and white, 20% green, 8% ink text, 2% gold.

---

## 2. Logo

**The Scholar Shield** (chosen 2026-11-24): a laurel sprig growing out of an open book, on a gold-lined shield.
All files, sizes, spacing and don'ts: `docs/brand/logo/GUIDELINES.md`.

| Part | Colour | Hex |
|---|---|---|
| Shield | brand-700 | `#124A33` |
| Keyline, leaves (and the edge on dark) | gold-500 | `#D4A03F` |
| Lit side of the leaves | gold-300 | `#ECD08F` |
| Book, wordmark on dark | on-brand | `#FBFAF5` |
| Wordmark on light, icon tile | brand-800 | `#0E3A28` |

**In the product:** `Logo`, `LogoMark` (`detailed` for 48 px and larger) and `Wordmark` from `@eduzone/ui`; outlines in
`packages/ui/src/logo-paths.ts` (the certificate PDF has the same ones in `backend/app/modules/courses/logo_art.py`).
Inside `.ez-grain` panels the shield gets its gold edge by itself. The name is drawn EDUZONE in the logo and written
EduZone in text.

**Small mark as SVG:**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" role="img" aria-labelledby="title"><title id="title">EduZone</title><path fill="#124a33" d="M128 14 C148 28 186 28 224 22 V124 C224 186 180 220 128 242 C76 220 32 186 32 124 V22 C70 28 108 28 128 14 Z"/><path fill="#d4a03f" d="M122 151 V121 H134 V151 Z"/><path fill="#d4a03f" d="M116 142 C88.6 153.7 62.9 134.3 64.9 103.5 C94 93.1 119.7 112.5 116 142 Z"/><path fill="#ecd08f" d="M116 142 C119.7 112.5 94 93.1 64.9 103.5 Z"/><path fill="#d4a03f" d="M140 142 C136.3 112.5 162 93.1 191.1 103.5 C193.1 134.3 167.4 153.7 140 142 Z"/><path fill="#ecd08f" d="M140 142 C136.3 112.5 162 93.1 191.1 103.5 Z"/><path fill="#d4a03f" d="M128 114 C98.1 96 98.1 56.7 128 36 C157.9 56.7 157.9 96 128 114 Z"/><path fill="#ecd08f" d="M128 114 C157.9 96 157.9 56.7 128 36 Z"/><path fill="#fbfaf5" d="M123 166 C115.2 152 92 151.3 70 155.9 V189.9 C92 185.3 115.2 186 123 200 Z M133 166 C140.8 152 164 151.3 186 155.9 V189.9 C164 185.3 140.8 186 133 200 Z"/></svg>
```

---

## 3. Colours

### 3.1 Brand: forest green

| Token | Hex | RGB | HSL | Tailwind | Use |
|---|---|---|---|---|---|
| `--ez-brand-950` | `#06190F` | 6, 25, 15 | 148°, 61%, 6% | `brand-950` | Deepest panels (home hero), overlays, text on gold |
| `--ez-brand-900` | `#0A2A1D` | 10, 42, 29 | 156°, 62%, 10% | `brand-900` | Console sidebar, dark panels, share images |
| `--ez-brand-800` | `#0E3A28` | 14, 58, 40 | 155°, 61%, 14% | `brand-800` | Primary hover, active chips and menu items, logo tile |
| **`--ez-brand-700`** | **`#124A33`** | 18, 74, 51 | 155°, 61%, 18% | **`brand`** | **The brand colour.** Primary buttons, links, active states |
| `--ez-brand-600` | `#17603F` | 23, 96, 63 | 153°, 61%, 23% | `brand-600` | Eyebrows, icons, emphasised words on light |
| `--ez-brand-500` | `#23805A` | 35, 128, 90 | 155°, 57%, 32% | `brand-500` | Focus ring, glows, lighter accents |
| `--ez-brand-300` | `#8CC3A5` | 140, 195, 165 | 147°, 31%, 66% | `brand-300` | Icons and secondary text on dark green |
| `--ez-brand-100` | `#D8ECE0` | 216, 236, 224 | 144°, 34%, 89% | `brand-100` | Body text on dark green, soft fills, rings |
| `--ez-brand-50` | `#EDF6F0` | 237, 246, 240 | 140°, 33%, 95% | `brand-50` | Tinted backgrounds, badges, active tab |
| `--ez-on-brand` | `#FBFAF5` | 251, 250, 245 | 50°, 43%, 97% | `on-brand` | Text on green (warm white, not pure white) |

There is no 200 or 400 step.

### 3.2 Gold: emphasis only

| Token | Hex | RGB | HSL | Tailwind | Use |
|---|---|---|---|---|---|
| `--ez-gold-600` | `#8A6118` | 138, 97, 24 | 38°, 70%, 32% | `gold-strong` | Gold text and marks on light |
| **`--ez-gold-500`** | **`#D4A03F`** | 212, 160, 63 | 39°, 63%, 54% | **`gold`** | Gold buttons, cart count, "New", icons on dark |
| `--ez-gold-300` | `#ECD08F` | 236, 208, 143 | 42°, 71%, 74% | `gold-300` | Highlighted headline words on dark, gold hover, text selection |
| `--ez-gold-100` | `#F8EED4` | 248, 238, 212 | 43°, 72%, 90% | `gold-100` | Soft gold tiles and badges |

### 3.3 Neutrals: warm paper

| Token | Hex | RGB | HSL | Tailwind | Use |
|---|---|---|---|---|---|
| `--ez-surface` | `#FAF8F3` | 250, 248, 243 | 43°, 41%, 97% | `background` | **Page background** |
| `--ez-bg` | `#FFFFFF` | 255, 255, 255 | 0°, 0%, 100% | `surface` | **Cards, inputs, dialogs** |
| `--ez-sunken` | `#F2EEE4` | 242, 238, 228 | 43°, 35%, 92% | `sunken` | Recessed areas, hover fills, neutral badges |
| `--ez-border` | `#E5DFD2` | 229, 223, 210 | 41°, 27%, 86% | `border` | Card borders, dividers |
| `--ez-border-strong` | `#CFC6B4` | 207, 198, 180 | 40°, 22%, 76% | `border-strong` | Input borders, secondary buttons |
| `--ez-text` | `#14201A` | 20, 32, 26 | 150°, 23%, 10% | `foreground` | Main text (green-black ink) |
| `--ez-text-muted` | `#5C6862` | 92, 104, 98 | 150°, 6%, 38% | `muted` | Supporting text, hints |
| `--ez-text-subtle` | `#646C68` | 100, 108, 104 | 150°, 4%, 41% | `subtle` | Placeholders, quiet notes, small icons. Light backgrounds only |

> **The names are crossed; take care.** The CSS variable `--ez-surface` is the *page*, and Tailwind calls it
> `background`. The variable `--ez-bg` is a *card*, and Tailwind calls it `surface`. In components use the
> Tailwind names: `bg-background` for the page, `bg-surface` for cards.

### 3.4 Status: never themed

| Meaning | Text | RGB | Background | RGB | Tailwind |
|---|---|---|---|---|---|
| Success | `#17703F` | 23, 112, 63 | `#E3F3E8` | 227, 243, 232 | `success` / `success-bg` |
| Warning | `#9A5B00` | 154, 91, 0 | `#FDF0D6` | 253, 240, 214 | `warning` / `warning-bg` |
| Danger | `#B42318` | 180, 35, 24 | `#FDECEA` | 253, 236, 234 | `danger` / `danger-bg` |
| Info | `#1C5F8F` | 28, 95, 143 | `#E5F0F8` | 229, 240, 248 | `info` / `info-bg` |

Status is never shown by colour alone: always add a word, and a dot or icon.

### 3.5 Access pills: one clear state per month

| State | Tone | Text | Background |
|---|---|---|---|
| Paid | success | `#17703F` | `#E3F3E8` |
| Unpaid | gold | `#8A6118` | `#F8EED4` |
| Pending | warning | `#9A5B00` | `#FDF0D6` |
| Closed | neutral | `#5C6862` | `#F2EEE4` |
| Upcoming | info | `#1C5F8F` | `#E5F0F8` |

### 3.6 Accent: the only themable colour

| Token | Today |
|---|---|
| `--ez-accent` | `--ez-brand-700` |
| `--ez-accent-hover` | `--ez-brand-800` |
| `--ez-on-accent` | `--ez-on-brand` |

- **Marketplace:** always EduZone green. Teachers and institutes have **no logo or colours of their own**.
- **Company sites (v1.1, not built):** may replace `--ez-accent` only, contrast-checked, with `--ez-on-accent`
  switching between white and near-black to meet WCAG AA.

### 3.7 Print approximations (CMYK)

Converted by formula from RGB, so treat them as a starting point and **ask the printer for a proof**.

| Colour | Hex | C | M | Y | K |
|---|---|---|---|---|---|
| Forest green | `#124A33` | 76 | 0 | 31 | 71 |
| Dark green | `#0A2A1D` | 76 | 0 | 31 | 84 |
| Gold | `#D4A03F` | 0 | 25 | 70 | 17 |
| Ivory | `#FAF8F3` | 0 | 1 | 3 | 2 |
| Ink | `#14201A` | 38 | 0 | 19 | 87 |

---

## 4. Contrast and safe combinations

WCAG AA needs **4.5:1** for normal text, and **3:1** for large text (24 px, or 18.66 px bold) and for icons and
controls.

### Safe for any text

| Text | Background | Ratio |
|---|---|---|
| Ink `#14201A` | White | 16.78 |
| Ink `#14201A` | Ivory | 15.81 |
| Warm white `#FBFAF5` | brand-900 | 14.76 |
| Ink `#14201A` | gold-100 | 14.52 |
| Ink `#14201A` | Sunken | 14.49 |
| brand-100 | brand-900 | 12.48 |
| Warm white | brand-800 | 12.15 |
| brand-950 | gold-300 | 12.12 |
| gold-300 | brand-900 | 10.27 |
| brand-700 | White | 10.23 |
| Warm white | brand-700 (primary button) | 9.79 |
| brand-700 | Ivory | 9.64 |
| brand-700 | brand-50 | 9.27 |
| brand-950 | gold-500 (gold button) | 7.71 |
| brand-300 | brand-900 | 7.68 |
| brand-600 | White | 7.55 |
| Warm white | brand-600 | 7.22 |
| brand-600 | Ivory | 7.11 |
| gold-300 | brand-700 | 6.81 |
| Danger | White | 6.57 |
| gold-500 | brand-900 | 6.53 |
| Info | Info background | 5.89 |
| Muted | White | 5.81 |
| Danger | Danger background | 5.75 |
| Muted | Ivory | 5.48 |
| gold-600 | White | 5.52 |
| Subtle | White | 5.40 |
| Success | Success background | 5.33 |
| gold-600 | Ivory | 5.20 |
| Subtle | Ivory | 5.09 |
| Muted | Sunken | 5.02 |
| brand-500 | White | 4.88 |
| Warning | Warning background | 4.81 |
| gold-600 | gold-100 | 4.78 |
| gold-600 | Sunken | 4.77 |
| Warm white | brand-500 | 4.67 |
| Subtle | Sunken | 4.66 |
| brand-500 | Ivory | 4.59 |

### Large text and icons only

| Text | Background | Ratio |
|---|---|---|
| gold-500 | brand-700 | 4.33 |

### Never for text

| Text | Background | Ratio | Use instead |
|---|---|---|---|
| gold-500 | White | 2.36 | gold-600, or brand-700 |
| White | gold-500 | 2.36 | brand-950 |

---

## 5. Typography

### 5.1 Fonts

All three are free on Google Fonts (SIL Open Font License). The apps load them with `next/font`, so they are
self-hosted.

| Role | Font | CSS variable | Tailwind | Loaded |
|---|---|---|---|---|
| Headings, big numbers | **Fraunces** (variable: `SOFT`, `opsz`) | `--font-display-serif` | `font-display` | Yes |
| Text and interface | **Instrument Sans** | `--font-body` | `font-sans` | Yes |
| Sinhala | **Noto Sans Sinhala** | `--font-sinhala` | in both stacks | Yes |
| Tamil | **Noto Sans Tamil** | none yet | none yet | No (planned) |

```css
--font-sans: var(--font-body), var(--font-sinhala), ui-sans-serif, system-ui, sans-serif;
--font-display: var(--font-display-serif), var(--font-sinhala), ui-serif, Georgia, serif;

/* font-display settings */
font-variation-settings: "SOFT" 50, "WONK" 0;
letter-spacing: -0.02em;
```

**When the fonts aren't available** (Word, email): Georgia for headings, Arial for text, Iskoola Pota for Sinhala.

### 5.2 Scale

| Style | Size | Font and weight | Notes |
|---|---|---|---|
| Hero | 43 → 56 → 64 px (phone → tablet → desktop) | Fraunces 600 | line-height 1, tracking -0.02em |
| Sign-in panel headline | 48 px | Fraunces 600 | line-height 1.05 |
| Page title | 30 px, 36 px from `sm` | Fraunces 600 | line-height 1.25 |
| Section title | 24 px | Fraunces 600 | |
| Card title | 20 px | Fraunces 600 | |
| Lead text | 18 px | Instrument Sans 400 | relaxed line-height |
| Body | 16 px | Instrument Sans 400 | line-height 1.5 |
| Interface text | 15 px | Instrument Sans 400 / 600 | inputs, buttons, descriptions |
| Small | 14 px | Instrument Sans 400 | hints, secondary text |
| Caption, badge | 12 px | Instrument Sans 500 / 600 | |
| **Eyebrow** | 12 px | Instrument Sans 700 | UPPER CASE, 0.14em tracking, brand-600 |
| Big amounts | 30 px | Fraunces 600 | tabular figures |

### 5.3 Rules

- Weights used: 400, 500, **600 (the default for headings and buttons)**, 700 for eyebrows and tiny labels.
- Line-height is 1.5, and **1.6 for Sinhala** (`:lang(si)`); Tamil will follow the same.
- *Italic Fraunces* marks one key phrase in a headline: gold-300 on dark, brand-600 on light.
- Money and table numbers use `tabular-nums`.
- Body text uses the font features `"ss01", "cv11"`.

---

## 6. Shape, shadow and layout

### Radius

| Token | Value | Tailwind | Use |
|---|---|---|---|
| `--ez-radius-sm` | 8 px | `rounded-ez-sm` | Small elements |
| `--ez-radius` | 12 px | `rounded-ez` | Buttons, inputs, alerts, toasts |
| `--ez-radius-lg` | 20 px | `rounded-ez-lg` | Cards, dialogs, tiles |
| full | 999 px | `rounded-full` | Badges, pills, chips, avatars |

Home hero photos use a larger 28 px corner.

### Shadow: green-black, never pure black on light pages

| Token | Value | Tailwind | Use |
|---|---|---|---|
| `--ez-shadow-sm` | `0 1px 2px rgb(20 32 26 / 0.06)` | `shadow-ez-sm` | Cards at rest |
| `--ez-shadow` | `0 1px 2px rgb(20 32 26 / 0.05), 0 4px 16px -4px rgb(20 32 26 / 0.1)` | `shadow-ez` | Card hover |
| `--ez-shadow-lg` | `0 2px 4px rgb(20 32 26 / 0.04), 0 18px 40px -12px rgb(20 32 26 / 0.22)` | `shadow-ez-lg` | Dialogs, toasts, drawers |

### Layout

| Item | Value |
|---|---|
| Container widths | sm 448 · md 768 · **lg 1152 (default)** · xl 1280 px |
| Side padding | 16 px, 24 px from `sm` |
| Card padding | 20 px, 24 px from `sm` |
| Site header | 64 px, sticky, ivory at 85% with blur |
| Console sidebar | 272 px, brand-900, from `lg` |
| Phone tab bar | 60 px, fixed at the bottom, below `md` |
| Breakpoints (Tailwind) | sm 640 · md 768 · lg 1024 · xl 1280 |
| Spacing unit | 4 px (Tailwind scale) |
| Touch target | 44 px minimum |

---

## 7. Motion

One easing curve everywhere: `--ez-ease: cubic-bezier(0.22, 1, 0.36, 1)` (Tailwind `ease-ez`).

| Name | What it does | Timing |
|---|---|---|
| `ez-rise` | Page-load reveal: fade and 10 px up; stagger with `--i` | 0.6 s + 70 ms per step |
| `ez-float` / `ez-float-slow` | Slow 8 px drift for hero cards | 6 s / 8 s loop |
| `ez-marquee` | Endless strip; pauses on hover | 60 s |
| `ez-fade` | Dialog backdrop | 0.2 s |
| `ez-pop` | Dialog on desktop / toast (from 96% size) | 0.24 s / 0.28 s |
| `ez-sheet` | Bottom sheet on phones | 0.32 s |
| `ez-drawer` | Side drawer | 0.3 s |
| `ez-shimmer` | Skeleton loading | 1.6 s loop |
| Buttons | Colour change; 1 px down when pressed | 0.2 s |
| Interactive cards | 2 px up, stronger shadow | 0.3 s |

`prefers-reduced-motion` turns off the reveal, float, marquee and skeleton animations, and makes transitions
instant. Use skeletons rather than full-page spinners.

---

## 8. Textures and effects

| Helper | Effect | Where |
|---|---|---|
| `ez-grain` | Fine film grain (22% overlay) | Dark green panels: hero, sidebar, dark tiles |
| `ez-ruled` | Faint ruled-paper lines every 32 px | Light sections |
| `ez-mark` | Gold highlighter behind one word | Headlines on light |
| `ez-skeleton` | Shimmering placeholder | Loading states |
| `ez-scroll-dark` | Thin, quiet scrollbar | Dark sidebar |
| `ez-seek` | Gold thumb on the video seek bar | Video player |

**Home hero recipe**

1. Base: brand-950 with `ez-grain`.
2. Warm glow, top right: radial `rgb(212 160 63 / 0.28)` to transparent.
3. Green glow, bottom left: radial `rgb(35 128 90 / 0.35)` to transparent.
4. Dot grid: `rgb(255 255 255 / 0.07)` dots, 22 px apart, masked so they fade out.
5. Headline in warm white, with the key phrase in gold-300 italic over a hand-drawn gold underline.

**Photo overlays:** always a green gradient, for example `from-brand-950/85 via-brand-950/25 to-transparent`,
never plain black. (The video player's controls are the exception.)

**Text selection:** gold-300 background with brand-950 text.

---

## 9. Components

Live style guide: `/design` in `apps/web` (development only).

### Buttons

| Variant | Look | Hover | Use |
|---|---|---|---|
| `primary` | brand-700, warm white text | brand-800 | The one main action |
| `secondary` | white, strong border | sunken | Other actions |
| `outline` | transparent, green border and text | brand-50 | Softer alternative |
| `ghost` | text only | sunken | Low emphasis, toolbars |
| `gold` | gold-500, brand-950 text | gold-300 | Main action on a dark panel |
| `danger` | white, red text and border | danger-bg | Delete, revoke |
| `link` | green text | underline | Inline actions |

| Size | Minimum height | Side padding | Text |
|---|---|---|---|
| `sm` | 36 px | 12 px | 14 px |
| `md` (default) | 44 px | 18 px | 15 px |
| `lg` | 52 px | 24 px | 16 px |

All: radius 12, weight 600. Disabled is 50% opacity.

### Form fields

White, 44 px minimum height, radius 12, `border-strong`. Focus: green border and a 4 px green ring at 12%.
Error: danger border with the message below in danger. Labels are 14 px 600; hints are 12 px muted.

### Badges

Full pill, 12 px 600, with a 1 px inset ring.

| Tone | Text | Background |
|---|---|---|
| neutral | muted | sunken |
| brand | brand-700 | brand-50 |
| gold | gold-600 | gold-100 |
| success, warning, danger, info | status colour | status background |

### Other components

| Component | Look |
|---|---|
| Card | White, radius 20, `border`, `shadow-ez-sm` |
| StatTile | `plain` white · `brand` dark green with grain and gold icon · `gold` soft gold |
| Alert | Status background, status border at 20%, radius 12 |
| Dialog | Bottom sheet on phones, centred card from `sm`; backdrop brand-950 at 45% with blur |
| Toast | White, radius 12, `shadow-ez-lg`; bottom on phones, top right on desktop |
| FilterChips | Pills, 40 px; active brand-800 with warm white text |
| Header link | Active: a 2 px green underline |
| Side menu | brand-900; active brand-800, gold icon and a gold bar on the left edge |
| Tab bar | White blur; active green on a brand-50 pill |
| Cart count | gold-500 circle, brand-900 number |
| EmptyState | Dashed border, icon in a brand-50 circle, and the next action |
| Focus | 2 px brand-500 outline, 2 px offset |

Every data screen has four states: **loading** (skeleton), **empty** (what to do next), **error** (retry),
**success**.

---

## 10. Covers, avatars and icons

### Generated class covers (`ClassCover`)

When a class has no image, a 16:10 "book cover" is drawn: a palette and one of three patterns (circles, dots,
stripes) chosen from its name, a spine on the left, and a large italic Fraunces symbol.

| # | Background | Symbol and spine | Soft shape | Label |
|---|---|---|---|---|
| 1 | `#0E3A28` | `#D4A03F` | `#17603F` | `#FBFAF5` |
| 2 | `#124A33` | `#ECD08F` | `#23805A` | `#FBFAF5` |
| 3 | `#F2EEE4` | `#124A33` | `#D8ECE0` | `#0A2A1D` |
| 4 | `#D4A03F` | `#0A2A1D` | `#ECD08F` | `#0A2A1D` |
| 5 | `#0A2A1D` | `#8CC3A5` | `#124A33` | `#FBFAF5` |
| 6 | `#EDF6F0` | `#17603F` | `#D8ECE0` | `#0A2A1D` |

Symbols: Physics Φ · Chemistry ⚗ · Biology β · Maths ∑ · Combined Maths ∫ · Science λ · ICT <> · English Aa ·
Accounting % · Economics €. Any other subject uses its first letter.

### Avatars

Initials in a circle, 32 / 40 / 56 px, weight 600, with a tone chosen from the name.

| Background | Text |
|---|---|
| brand-100 | brand-800 |
| gold-100 | gold-600 |
| brand-800 | gold-300 |
| sunken | foreground |
| brand-50 | brand-600 |

### Icons

**Lucide** outline icons only, usually 16 to 20 px, in `currentColor`. Gold on dark panels, brand-600 on light.
No emoji as interface icons.

---

## 11. Photography

- **Subject:** real moments of studying: a library, a desk, an online lesson, a classroom, a lab.
- **Feel:** warm natural light, calm and focused; Sri Lankan or South Asian students where possible.
- **Treatment:** rounded corners; a green gradient overlay when text sits on top.
- **Source today:** Pexels (free licence), listed in `apps/web/lib/photos.ts` and drawn by
  `components/photo.tsx`. Copy them to our own storage before launch.
- **Stay neutral:** heroes, banners and marketing bands never show a particular teacher, their class or their
  price. Those belong only in lists and pages the visitor chose.
- **Avoid:** staged smiling groups, blue or neon technology images, stock clip-art.

---

## 12. Voice and wording

**Plain, warm, exact.** Write for a student on a phone and a parent paying fees.

| Say | Not |
|---|---|
| Pay for October | Purchase entitlement |
| Past month | Expired billing period |
| You have access | Entitlement active |
| The code is wrong. 4 tries left. | Error: invalid OTP |

- Short sentences, and one idea in each. Explain every block and give the one action that fixes it.
- Money: `Rs. 2,000.00` (lists may drop `.00`). Dates: `Sat, 4 Oct · 8:00 AM`, Colombo time.
  Phones: `077 123 4567`.
- Sinhala and Tamil are written by native speakers, never machine-translated.

**Lines in the product today**

- Home headline: *Learn from Sri Lanka's best teachers, **month by month.***
- Home text: *Live Zoom classes, recordings and tutes for Grade 5, O/L and A/L. One account for every teacher;
  pay only for the months you need.*
- Footer: *Live classes, recordings and tutes in one place. Pay month by month and learn from anywhere.*
- Trust points: *Pay month by month* · *Live and recorded* · *Secure payments*

---

## 13. Using the brand outside the website

### Two main looks

| | Paper (light) | Forest (dark) |
|---|---|---|
| Background | `#FAF8F3` | `#0A2A1D` (or `#06190F`) |
| Headline | `#14201A` Fraunces 600 | `#FBFAF5` Fraunces 600 |
| Key phrase | `#17603F` italic | `#ECD08F` italic |
| Body | `#5C6862` | `#D8ECE0` |
| Eyebrow | `#17603F` | `#D4A03F` |
| Button | `#124A33` with `#FBFAF5` | `#D4A03F` with `#06190F` |
| Best for | Documents, receipts, email, slides | Covers, posters, social posts |

### Share images

1200 × 630. Background `#0A2A1D`; the logo top left; eyebrow `#D4A03F`; title `#FBFAF5`; subtitle `#8CC3A5`; initials in
`#0E3A28` on a `#D8ECE0` circle; a gold bar 240 × 10 px at the bottom (`components/og-card.tsx`).

### Certificates (A4 landscape)

Ivory page `#FAF8F3`, thick green frame `#124A33`, thin gold inner frame `#D4A03F`, the shield and wordmark at the top,
names in a serif (`certificates.py`, `logo_art.py`).

### Slides and documents

Ivory background, Fraunces titles, Instrument Sans text, green tables with `#E5DFD2` lines, and gold for one key
number per page.

### Social templates (proposed)

| Format | Size |
|---|---|
| Square post | 1080 × 1080 |
| Story or status | 1080 × 1920 |
| Facebook cover | 820 × 312 |
| YouTube thumbnail | 1280 × 720 |

---

## 14. Rules

**Do**

- Read every colour, radius and shadow from the `--ez-*` tokens, through the Tailwind names.
- Use one primary button per area, and use gold for one thing per view.
- Keep page backgrounds ivory and cards white.
- Put dark text on gold, and warm white text on green.
- Check new components on `/design`, at 360 px and on desktop.

**Don't**

- Use raw palette classes (`bg-green-600`, `text-gray-500`) or hex values in components.
- Use gold for body text, or white text on gold.
- Use gold as a second brand colour or a large background on the website.
- Use cold greys, pure black, blue or purple as brand colours.
- Add dark mode, or a teacher's or institute's own colours, on the marketplace.
- Show status by colour alone.
- Feature one teacher in EduZone's own marketing.

**Where hex is allowed:** places that cannot read CSS variables (`og-card.tsx`, the PDF certificate, the SVG in
`cover.tsx`). Keep those equal to the tokens by hand.

---

## 15. Copy-paste tokens

### CSS variables

```css
:root {
  /* Brand: forest green */
  --ez-brand-950: #06190f;
  --ez-brand-900: #0a2a1d;
  --ez-brand-800: #0e3a28;
  --ez-brand-700: #124a33;
  --ez-brand-600: #17603f;
  --ez-brand-500: #23805a;
  --ez-brand-300: #8cc3a5;
  --ez-brand-100: #d8ece0;
  --ez-brand-50: #edf6f0;
  --ez-on-brand: #fbfaf5;

  /* Gold: emphasis only */
  --ez-gold-600: #8a6118;
  --ez-gold-500: #d4a03f;
  --ez-gold-300: #ecd08f;
  --ez-gold-100: #f8eed4;

  /* Accent */
  --ez-accent: var(--ez-brand-700);
  --ez-accent-hover: var(--ez-brand-800);
  --ez-on-accent: var(--ez-on-brand);

  /* Neutrals: warm paper */
  --ez-bg: #ffffff;            /* cards, inputs */
  --ez-surface: #faf8f3;       /* page */
  --ez-sunken: #f2eee4;
  --ez-border: #e5dfd2;
  --ez-border-strong: #cfc6b4;
  --ez-text: #14201a;
  --ez-text-muted: #5c6862;
  --ez-text-subtle: #646c68;

  /* Status */
  --ez-success: #17703f;
  --ez-success-bg: #e3f3e8;
  --ez-warning: #9a5b00;
  --ez-warning-bg: #fdf0d6;
  --ez-danger: #b42318;
  --ez-danger-bg: #fdecea;
  --ez-info: #1c5f8f;
  --ez-info-bg: #e5f0f8;

  /* Shape */
  --ez-radius-sm: 8px;
  --ez-radius: 12px;
  --ez-radius-lg: 20px;
  --ez-shadow-sm: 0 1px 2px rgb(20 32 26 / 0.06);
  --ez-shadow: 0 1px 2px rgb(20 32 26 / 0.05), 0 4px 16px -4px rgb(20 32 26 / 0.1);
  --ez-shadow-lg: 0 2px 4px rgb(20 32 26 / 0.04), 0 18px 40px -12px rgb(20 32 26 / 0.22);

  /* Motion */
  --ez-ease: cubic-bezier(0.22, 1, 0.36, 1);
}
```

### JSON (design tools)

```json
{
  "brand": {
    "950": "#06190F", "900": "#0A2A1D", "800": "#0E3A28", "700": "#124A33", "600": "#17603F",
    "500": "#23805A", "300": "#8CC3A5", "100": "#D8ECE0", "50": "#EDF6F0", "on": "#FBFAF5"
  },
  "gold": { "600": "#8A6118", "500": "#D4A03F", "300": "#ECD08F", "100": "#F8EED4" },
  "neutral": {
    "page": "#FAF8F3", "card": "#FFFFFF", "sunken": "#F2EEE4", "border": "#E5DFD2",
    "borderStrong": "#CFC6B4", "text": "#14201A", "muted": "#5C6862", "subtle": "#646C68"
  },
  "status": {
    "success": ["#17703F", "#E3F3E8"], "warning": ["#9A5B00", "#FDF0D6"],
    "danger": ["#B42318", "#FDECEA"], "info": ["#1C5F8F", "#E5F0F8"]
  },
  "radius": { "sm": 8, "md": 12, "lg": 20 },
  "font": { "display": "Fraunces", "body": "Instrument Sans", "sinhala": "Noto Sans Sinhala" }
}
```

### Short list for a designer

```
Forest green  #124A33     Dark green  #0A2A1D     Soft green  #EDF6F0
Gold          #D4A03F     Soft gold   #F8EED4     Ivory       #FAF8F3
Ink           #14201A     Muted       #5C6862     Border      #E5DFD2
Fonts: Fraunces 600 (headings), Instrument Sans 400/600 (text), Noto Sans Sinhala
```

### Prompt for an image or design tool

```
EduZone brand: scholarly, modern, calm. Deep forest green (#124A33, #0A2A1D) with small touches of warm
gold (#D4A03F) on ivory paper (#FAF8F3). Elegant soft serif headings (Fraunces), clean sans text
(Instrument Sans). Rounded corners, soft green-black shadows, subtle film grain on dark green panels,
faint ruled-paper lines on light areas. Warm natural light. No blue, no purple, no neon, no cold grey.
```

---

## 16. Known gaps

| Gap | Detail | Suggested fix |
|---|---|---|
| Trademark | The logo hasn't been searched | Trademark and reverse image search before launch |
| Certificate fonts | `certificates.py` uses the PDF base fonts | Embed Fraunces and Noto Sans Sinhala |
| Ruled lines | The About and Contact pages use `rgb(26 67 49)`, which is not a token | Use a brand token |
| Tamil font | Not loaded | Add Noto Sans Tamil with the Tamil interface |
| Admin colour field | The organization form still asks for a brand colour (example `#1E6FD9`) that the marketplace ignores | Hide it until company sites (v1.1) |
| Photos | Served from Pexels | Copy to our own storage before launch |
