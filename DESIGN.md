---
name: Loom
description: A chat assistant that shows its machinery, woven from a provisional linen, madder, indigo and ink palette.
colors:
  indigo: "#2f4a6b"
  madder: "#b04a2e"
  madder-hover: "#983d24"
  on-madder: "#ffffff"
  linen: "#f1e9dc"
  paper: "#f8f4ec"
  paper-raised: "#fffdf9"
  paper-sunk: "#ede4d5"
  rule: "#e0d5c3"
  ink: "#2a2420"
  ink-2: "#66594f"
  ink-3: "#7a6c61"
  code-bg: "#2a2420"
  code-ink: "#ede4d6"
  inline-code-bg: "#e9dfcf"
  danger: "#a3361d"
  danger-bg: "#f6e3dc"
  side-bg: "#2f4a6b"
  side-ink: "#f1e9dc"
  side-ink-2: "#c3ccd8"
  side-weft: "#d7714f"
  dark-madder: "#d7714f"
  dark-madder-hover: "#e38766"
  dark-on-madder: "#1f1b18"
  dark-paper: "#1f1b18"
  dark-paper-raised: "#2a2420"
  dark-paper-sunk: "#2f2925"
  dark-rule: "#3b342e"
  dark-ink: "#ede4d6"
  dark-ink-2: "#b6a99b"
  dark-ink-3: "#9c8f82"
  dark-code-bg: "#151210"
  dark-inline-code-bg: "#38302a"
  dark-danger: "#f08f72"
  dark-danger-bg: "#3a2620"
  dark-side-bg: "#1b2a3d"
  dark-side-ink-2: "#aab6c5"
typography:
  headline:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.6
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.6
  prose:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.7
  body:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: "tnum"
  label:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 500
    lineHeight: 1
  meta:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.4
  group-label:
    fontFamily: "Work Sans Variable, Work Sans, system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    letterSpacing: "0.04em"
  code:
    fontFamily: "JetBrains Mono Variable, JetBrains Mono, ui-monospace, monospace"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  xs: "4px"
  s: "6px"
  m: "10px"
  l: "14px"
  pill: "999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "6": "24px"
  "8": "32px"
  column: "720px"
  sidebar: "272px"
  title-bar: "56px"
components:
  button-primary:
    backgroundColor: "{colors.madder}"
    textColor: "{colors.on-madder}"
    typography: "{typography.label}"
    rounded: "{rounded.s}"
    padding: "0 12px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "{colors.madder-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.paper-sunk}"
    textColor: "{colors.ink-3}"
  button-quiet:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.s}"
    padding: "0 12px"
    height: "32px"
  button-quiet-hover:
    backgroundColor: "{colors.paper-sunk}"
    textColor: "{colors.ink}"
  button-outline:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.s}"
    padding: "0 12px"
    height: "32px"
  button-icon:
    rounded: "{rounded.s}"
    size: "32px"
  composer:
    backgroundColor: "{colors.paper-raised}"
    rounded: "{rounded.l}"
    padding: "10px 10px 10px 16px"
  composer-send:
    backgroundColor: "{colors.madder}"
    textColor: "{colors.on-madder}"
    rounded: "{rounded.m}"
    size: "32px"
  prompt-block:
    backgroundColor: "{colors.paper-sunk}"
    textColor: "{colors.ink}"
    rounded: "{rounded.l}"
    padding: "12px 16px"
  version-tab:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "0 12px"
    height: "34px"
  version-tab-current:
    textColor: "{colors.ink}"
  conversation-item:
    textColor: "{colors.side-ink-2}"
    rounded: "{rounded.s}"
    padding: "7px 10px"
  conversation-item-current:
    textColor: "{colors.side-ink}"
    padding: "7px 10px 7px 26px"
  sidebar:
    backgroundColor: "{colors.side-bg}"
    textColor: "{colors.side-ink}"
    width: "272px"
  status-flag:
    backgroundColor: "{colors.paper-sunk}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  status-flag-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger}"
  error-notice:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger}"
    rounded: "{rounded.m}"
    padding: "10px 14px"
  code-block:
    backgroundColor: "{colors.code-bg}"
    textColor: "{colors.code-ink}"
    typography: "{typography.code}"
    rounded: "{rounded.m}"
    padding: "14px 16px"
---

# Design System: Loom

> The identity this system is built on (the woven mark, the serif wordmark, and the Linen / Madder / Indigo / Ink palette from `docs/logo/`) is **provisional**. It is recorded here as what the app currently ships, not as a locked brand. Refining or replacing it is expected; when that happens, re-run the document pass rather than defending these values.

## Overview

**Creative North Star: "The Working Loom"**

Loom's interface is cloth on a frame. Indigo is the warp: it holds the whole sidebar, the fixed structure every conversation hangs from. Madder is the weft: a single thread that crosses the structure only where something is chosen or about to happen (the selected conversation, the current version, the Send action). Linen-tinted paper is the ground for reading, and Ink is the text. Nothing else is coloured.

The screen is a working tool, not a showcase. Density is calm desktop density: a fixed sidebar, a 56px title bar, and a single centred 720px reading column with the composer docked beneath it. Replies are full-width formatted prose; prompts sit as quiet sunk blocks offset to the right. The signature of the system is that structure is drawn where it happens: a turn with sibling versions carries a tab strip directly above it, so the message tree is legible in place.

Light and dark are one world seen at different hours. Dark mode comes from the dark app icon: an ink ground, linen text, a deeper indigo sidebar, and a lighter madder that keeps its contrast on dark.

**Key Characteristics:**
- Two-colour structure: indigo shell, paper reading ground; madder only as the selection or action thread.
- One sans family (Work Sans) for all UI and prose; JetBrains Mono only inside code.
- Flat, tonal surfaces; depth comes from paper value steps, not shadows.
- Branch points shown as tabs above the turn, never hidden behind arrows.
- The woven mark is redrawn as SVG and takes its thread colours from CSS, so it re-weaves itself on every ground.

## Colors

A warm, low-chroma paper-and-ink palette held by one structural blue and crossed by one red thread.

### Primary
- **Madder** (`madder`): the weft. The primary action fill (Send, Save), the current-version tab underline, the streaming caret, text carets in inputs, and link underlines in prose. In dark mode it lightens to `dark-madder` and its label flips to `dark-on-madder` (ink), not white.
- **Madder, Pressed Deeper** (`madder-hover`): hover state of a primary action only.

### Secondary
- **Indigo** (`indigo` / `side-bg`): the warp. Owns the entire sidebar surface, the browser theme colour, and the warp threads of the mark on light paper. In dark mode the sidebar deepens to `dark-side-bg`.
- **Sidebar Weft** (`side-weft`): the lighter madder used for threads that sit on indigo (the selected-conversation tick, the mark's weft, the caret in the sidebar input). Plain madder disappears on indigo; this one does not.

### Neutral
- **Paper** (`paper`): the reading ground of the main pane.
- **Paper, Raised** (`paper-raised`): surfaces that take input (composer, in-place editor).
- **Paper, Sunk** (`paper-sunk`): user prompt blocks, quiet-button hover, neutral status flags, disabled primary.
- **Rule** (`rule`): every hairline: title-bar border, tab-strip baseline, composer stroke, table rows, blockquote bar.
- **Ink** (`ink`), **Ink 2** (`ink-2`), **Ink 3** (`ink-3`): primary text; secondary text (stats, inactive tabs, quiet buttons); tertiary text (metadata line, hints, placeholders). Ink 3 clears 4.5:1 on Paper only; do not set running text in it on Paper Sunk.
- **Linen** (`linen` / `side-ink`): text on indigo and the mark's warp in dark mode. **Side Ink 2** (`side-ink-2`): secondary text on indigo.
- **Code Ground / Code Ink** (`code-bg`, `code-ink`): fenced code blocks are always dark, in both themes. **Inline Code Ground** (`inline-code-bg`) for inline code.
- **Danger / Danger Ground** (`danger`, `danger-bg`): error notices and the error status flag.

Sidebar hover and selection are linen washed over indigo at 8% and 14%, and the sidebar rule is linen at 18%; these are alpha tokens in the stylesheet, carried in the sidecar.

### Named Rules
**The One Thread Rule.** Madder marks a choice or an action: what is selected, what is current, what will send. It is never a decorative fill, a heading colour, or a background wash. If removing the madder from an element would not change what the user can do or see as chosen, it should not be madder.

**The Warp Holds Rule.** Indigo is structure, not accent. It fills the sidebar and colours the mark; it does not appear as button fills, links, or highlights inside the reading pane. Focus rings on paper are indigo because focus is structural.

**The Thread Changes On Indigo Rule.** Any madder element placed on the indigo sidebar uses Sidebar Weft, never base Madder.

## Typography

**Display Font:** none; the system has no display face.
**Body Font:** Work Sans Variable (with Work Sans, system-ui fallback), self-hosted via `@fontsource-variable/work-sans`.
**Label/Mono Font:** JetBrains Mono Variable (with ui-monospace fallback), self-hosted via `@fontsource-variable/jetbrains-mono`.

**Character:** A single humanist grotesque doing every job, from sidebar labels to long replies, so the screen reads as one fabric. The mono appears only where text is literally code.

### Hierarchy
- **Headline** (600, 22px, -0.01em): the empty-state greeting only.
- **Title** (600, 15px): the conversation title in the title bar. Deliberately the same size as body; weight alone carries it.
- **Prose** (400, 16px, 1.7): assistant replies. Markdown headings inside replies scale from it in `em` (1.35 / 1.2 / 1.05, weight 600, line-height 1.3).
- **Body** (400, 15px, 1.6, tabular numerals on): the app default, prompts, conversation items, composer.
- **Label** (500, 13.5px): buttons and version tabs (13px on tabs; the current tab goes to 600).
- **Meta** (400, 12.5px, 1.4): the per-reply metadata line (model, tokens in/out, stop reason) and edit hints.
- **Group Label** (600, 11.5px, +0.04em, sentence case): date groups in the conversation list.
- **Code** (JetBrains Mono, 13.5px, 1.6 in blocks; 0.84em inline).

### Named Rules
**The One Family Rule.** Work Sans sets everything that is not code. Do not introduce a second sans, a serif for headings, or the mono for labels and numbers; tabular numerals in Work Sans already handle token counts.

**The Wordmark Is Not Type Rule.** The serif lowercase "loom" is an image (extracted from the primary lockup and applied as a CSS mask so it takes `currentColor`). Never set it, or any UI text, in a serif font.

## Layout

A two-pane app shell. The sidebar is fixed at 272px on the left; the main pane is a column of title bar (56px, hairline beneath), scrolling transcript, and docked composer. Transcript and composer share one centred column: 720px of content plus 24px gutters each side (16px below the breakpoint). The transcript scroller reserves a stable scrollbar gutter so the column does not shift when content overflows.

Rhythm: 28px between turns; 32px above the first turn; 10px between a version strip and the turn it labels; 6px between reply and its metadata line. User prompts are right-aligned with a 64px inset on the left (24px on narrow screens), and their version strip shares that inset so it hugs the prompt. The composer dock fades the transcript out beneath it with a 16px gradient into Paper.

Below 860px the sidebar becomes a drawer: fixed, up to 86vw wide, hidden (visibility, not just transform) while closed so it leaves the tab order, sliding in over a 40% ink scrim. The title bar gains a menu button, the token stats and keyboard hint are hidden, and the main pane is made inert while the drawer is open.

Spacing values cluster on a 4px grid (4, 8, 12, 16, 24, 32) with 6, 10, 14, 22 and 28 used as optical in-between steps; it is a rhythm, not a strict scale.

## Elevation & Depth

Flat by default. Depth is tonal: Paper Sunk sits below the ground (prompts), Paper Raised sits above it (composer, editor), and hairline Rules separate regions. There are exactly two shadows in the system, and both are tied to a role.

### Shadow Vocabulary
- **Composer lift** (`box-shadow: 0 2px 10px rgb(42 36 32 / 0.05)`): a barely-there ambient lift on the docked composer so it reads as sitting over the scrolled transcript.
- **Drawer** (`box-shadow: 8px 0 40px rgb(20 24 32 / 0.25)`): the sidebar only, only while it is open as a mobile drawer.

### Named Rules
**The Paper Steps Rule.** To separate a surface, step its paper value (sunk or raised) or draw a Rule. Reach for a shadow only when the surface genuinely floats over scrolling content.

## Shapes

Soft, consistent rounding in three steps: small (6px) for buttons, tabs' focus caps and list items; medium (10px) for the sidebar's New button and input, code blocks, error notices and the Send/Stop button; large (14px) for content containers that hold text (prompt blocks, composer, in-place editor). Inline code uses 4px; status flags are full pills. Borders are 1px hairlines in Rule (or linen at 18% on indigo). The mark is built from fully rounded bars (rx equal to half the bar width), the one place the system uses capsule geometry, and the selected-conversation tick echoes it as a short 9x4px rounded bar.

## Components

### Buttons
One shape, three weights.
- **Shape:** gently rounded (6px), 32px tall, 12px horizontal padding, 13.5px / 500 label, 6px gap to an optional 16 to 18px line icon (Lucide).
- **Primary:** Madder fill, white label (ink label in dark). Used for Send and Save; at most one per region.
- **Quiet:** transparent, Ink 2 label; hover washes Paper Sunk and darkens the label to Ink. The default for secondary actions (Cancel, Edit, Regenerate, the menu toggle).
- **Outline:** 1px Rule stroke, Ink label, Paper Sunk on hover. Used for Stop.
- **Icon-only:** a 32px square of any weight; must carry an `aria-label`.
- **Hover / Focus:** colour transitions at 150ms on the shared ease-out curve; focus is a 2px indigo outline, offset 2px (linen on the sidebar).
- **Disabled:** primary drops to Paper Sunk with Ink 3 label; cursor not-allowed.

### Composer
- Raised paper, 1px Rule stroke, large radius (14px), composer lift shadow. The stroke darkens to Ink 3 on focus-within instead of showing a ring.
- An autosizing textarea (to 40vh) with a madder caret and Ink 3 placeholder; Send is a 32px madder icon button at medium radius, swapped for an outline Stop square while streaming.

### Version Tabs (signature)
- A strip of text tabs ("Version 1", "Reply 2") sitting on a 1px Rule baseline directly above any turn with siblings. 34px tall, 13px / 500, Ink 2.
- **Current:** Ink, weight 600, a 2px Madder underline that overlaps the baseline. **Hover:** Ink label with a Rule-coloured underline.
- The strip scrolls horizontally without a visible scrollbar; on a prompt it shares the prompt's left inset.

### Transcript
- **Prompt block:** Paper Sunk, large radius, 12px 16px padding, pre-wrapped text, right-aligned. Quiet icon actions (Edit) sit to its left in Ink 3.
- **Reply:** unboxed Markdown prose at 16px / 1.7. Links are Ink with a Madder underline offset 3px; blockquotes take a 1px Rule bar; tables use Rule row lines.
- **Metadata line:** Meta type in Ink 3 under each reply (model, tokens, stop reason), with a Quiet 28px Regenerate button and optional pill status flags (neutral, or danger for errors).
- **Streaming:** a blinking Madder block caret after the last Markdown element; "Thinking" in Ink 3 breathes between full and 45% opacity before the first token.
- **In-place edit:** the prompt becomes a raised, Rule-stroked, 14px container with its own textarea and a Quiet Cancel / Primary Save pair.

### Navigation (sidebar)
- Indigo surface holding, top to bottom: the brand row (mark at 26px plus masked wordmark at 22px tall), a full-width New conversation button (40px, linen-at-18% stroke, medium radius), the grouped conversation list, and a footer health line (12px, Side Ink 2, with a 7px status dot).
- **Conversation item:** 14px Side Ink 2, small radius, single-line ellipsis. Hover washes linen at 8%. **Current:** linen at 14%, Side Ink, weight 500, the left padding opens to 26px and a Sidebar Weft tick appears in the gap.
- **Inline create:** a 40px input on a 14% black wash with a weft caret, plus a ghost and a solid (linen-on-indigo) small button.
- **Mobile:** the sidebar becomes the drawer described in Layout, with a close icon button in the brand row.

### Error Notice
- Danger Ground panel, Danger text, medium radius, 10px 14px padding, a 16px alert-circle icon leading. Sits in the dock above the composer.

### Mark
- The woven mark is an inline SVG whose threads read `--mark-warp`, `--mark-weft` and `--mark-gap`. On indigo: linen warp, Sidebar Weft weft, indigo gap. On light paper: indigo warp, Madder weft. On dark paper: linen warp. The favicon carries the same weave with its own light and dark palettes.

## Do's and Don'ts

### Do:
- **Do** keep Madder to selection, current state, and the primary action (The One Thread Rule).
- **Do** switch any madder element on the sidebar to Sidebar Weft.
- **Do** separate surfaces by stepping paper value (sunk / raised) or a 1px Rule before reaching for a shadow.
- **Do** draw tree structure where it happens: a version strip directly above the turn that branches.
- **Do** set every non-code string in Work Sans; use the mono only for code.
- **Do** use the shared button weights (primary, quiet, outline) at 32px rather than inventing new button styles.
- **Do** honour `prefers-reduced-motion`: all transitions and animations drop to 0ms.
- **Do** define every new colour as a token on `:root` with a dark-mode counterpart.

### Don't:
- **Don't** use Indigo inside the reading pane as an accent, link, or button fill.
- **Don't** put base Madder on Indigo; it falls below legible contrast there.
- **Don't** hide branch points behind small "2/3" arrows under a message.
- **Don't** set the wordmark, or any UI text, in a serif face.
- **Don't** box assistant replies in bubbles; replies are open prose on paper.
- **Don't** treat this palette or mark as final; the brand is provisional (see the note at the top).
