---
name: Kizuna Signal
description: Evidence-aware pre-release intelligence for Japanese media entering India.
colors:
  ink: "#171817"
  mineral-paper: "#f4f4f2"
  panel: "#fafaf8"
  rule: "#d5d7d4"
  muted: "#696c69"
  evidence-green: "#168765"
  caution-amber: "#a86a18"
  risk-red: "#b44536"
typography:
  display:
    fontFamily: "Instrument Serif, Georgia, serif"
    fontSize: "clamp(3rem, 6vw, 5.125rem)"
    fontWeight: 400
    lineHeight: 0.92
    letterSpacing: "-0.035em"
  body:
    fontFamily: "DM Sans, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "IBM Plex Mono, Consolas, monospace"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "0.05em"
rounded:
  control: "9px"
  surface: "14px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "20px"
  lg: "35px"
  xl: "55px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    rounded: "{rounded.pill}"
    padding: "12px 17px"
  button-ghost:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "12px 17px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "46px"
---

# Design System: Kizuna Signal

## Overview

**Creative North Star: "Signal Plane"**

Kizuna Signal is an editorial intelligence instrument: quiet enough for consequential reading, precise enough for dense evidence, and memorable through one live spectral signal that represents evidence moving through the system. The system uses the compositional calm and typographic contrast of the supplied Octolane reference while retaining original Kizuna identity, copy, data, and workflows.

It is restrained rather than decorative. A pale mineral canvas holds black controls, hairline evidence structures, measured semantic color, and large serif conclusions. Dense decision content is progressively disclosed without disguising uncertainty or unsupported capabilities.

**Key Characteristics:**

- Editorial serif conclusions paired with neutral interface typography.
- Flat mineral surfaces separated by rules instead of stacked shadows.
- One spectral evidence rail as the recurring signature.
- Monospaced labels for versions, measurements, and provenance.
- Responsive reading order that preserves evidence before decoration.

## Colors

The palette is nearly monochrome, with semantic color appearing only when it carries evidence status.

### Primary

- **Graphite Ink:** Primary text, dark actions, result planes, and the status rail.

### Secondary

- **Evidence Green:** Connected services, available sources, positive drivers, and confirmed states.
- **Caution Amber:** Cached evidence, unvalidated capabilities, and calibration warnings.
- **Risk Red:** Failed sources, blocked states, and negative drivers.

### Neutral

- **Mineral Paper:** Page canvas and long reading surfaces.
- **Quiet Panel:** Bounded working areas and form surfaces.
- **Hairline Rule:** Table structure, field boundaries, and section separation.
- **Graphite Muted:** Secondary copy and measurement labels.

**The Evidence Color Rule.** Semantic color must describe a state; it is never used as general decoration.

## Typography

**Display Font:** Instrument Serif (with Georgia fallback)
**Body Font:** DM Sans (with Arial fallback)
**Label/Mono Font:** IBM Plex Mono (with Consolas fallback)

**Character:** The display face makes decisions feel editorial and considered. The sans face keeps controls neutral, while the mono face makes evidence metadata visibly different from narrative copy.

### Hierarchy

- **Display** (400, fluid 48–82px, 0.92): Page names, major scores, and decision statements.
- **Headline** (400, fluid 30–46px, 1): Evidence-section titles.
- **Title** (400, 21–31px, 1.1): Titles, component headings, and scenario labels.
- **Body** (400, 13–18px, 1.5): Explanations and guidance, normally kept below 75 characters per line.
- **Label** (400, 9–10px, tracked uppercase): Versions, statuses, ranks, and provenance.

**The Two Voices Rule.** Serif communicates conclusions; sans and mono communicate interaction and evidence.

## Layout

Desktop uses a 248px sticky operating rail and a centered evidence canvas no wider than 1300px. Sections are separated by one-pixel rules and 55px vertical beats. At 820px the rail becomes a compact top navigation and multi-column evidence stacks. At 560px controls become single-column, tabular rows become labelled lists, and the live rail scrolls horizontally without exposing a scrollbar. The minimum supported width is 360px.

## Elevation & Depth

The system is flat by default. Tonal shifts and hairline rules create depth; a restrained shadow appears only on the primary floating action. The spectral trace creates atmosphere without turning containers into floating cards.

### Shadow Vocabulary

- **Floating action** (`0 8px 20px rgba(0,0,0,.12)`): Primary pill actions only.

**The Flat-by-Default Rule.** If a surface can be separated by spacing, tone, or a hairline, it does not receive a shadow.

## Shapes

Controls use gently curved 9px corners, working surfaces use 14px corners, and primary actions use pill geometry. Result tables and evidence ledgers remain rectangular and rule-led. Circular geometry is reserved for the Kizuna mark, rank actions, and the analysis-progress orbit.

## Components

### Buttons

- **Shape:** Compact pill with 12px vertical and 17px horizontal padding.
- **Primary:** Graphite ink with quiet-panel text and a restrained floating-action shadow.
- **Hover / Focus:** One-pixel visual rise on hover; a clearly visible focus outline for keyboard users.
- **Ghost:** Quiet panel, hairline border, and no resting shadow.

### Cards / Containers

- **Corner Style:** Gently curved working surface (14px).
- **Background:** Mineral paper or quiet panel.
- **Shadow Strategy:** Flat at rest.
- **Border:** One-pixel hairline rule.
- **Internal Padding:** Normally 20–35px, larger only for hero score fields.

### Inputs / Fields

- **Style:** Quiet-panel fill, neutral stroke, 9px corner, and at least 46px control height.
- **Focus:** Visible browser-independent outline or border shift.
- **Error / Disabled:** Risk tint for errors; reduced opacity only when the action truly cannot run.

### Navigation

The active route uses a filled graphite-neutral track, not a colored icon tile. On mobile, icon-only links retain accessible names and native tooltips.

### Signal Rail

A narrow black status strip combines live connection state, version or workflow context, and a restrained spectral baseline. It scrolls horizontally on small screens and respects reduced-motion preferences.

### Score Field

Market potential, classification, confidence, and expected range share one joined plane. Opportunity and confidence are always presented as separate concepts.

## Do's and Don'ts

### Do:

- **Do** show provenance, warnings, and scoring versions next to decision outputs.
- **Do** use semantic color together with readable status text.
- **Do** preserve large editorial moments around the score and final decision.
- **Do** keep incomplete model and dataset capabilities explicitly labelled.

### Don't:

- **Don't** copy Octolane logos, proprietary copy, assets, or distinctive brand marks.
- **Don't** turn every section into a floating card or use gradients as generic decoration.
- **Don't** present confidence as prediction accuracy or public demand proxies as guaranteed revenue.
- **Don't** label deterministic metadata or scoring as AI-generated until a real inference endpoint is connected.
