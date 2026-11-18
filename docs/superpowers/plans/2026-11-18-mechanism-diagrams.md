# Mechanism diagrams and navigation implementation plan

> For agentic workers: use superpowers:executing-plans, inline execution.

**Goal:** Rework all eight source-bound illustrations into clear mechanism diagrams with the restrained language of quant-workspace-standards, and remove the obsolete eight-question navigation label.

**Architecture:** Retain React/SVG and the exact owner-produced fixtures. Share record formatting and visual primitives, use a dedicated aligned-path component, and add an atomic cross-path event selection action. Financial state is displayed from records only. All explanatory text lives in paired locale catalogs.

**Spec:** The user requested standards-like diagrams, open-source references, clearer complete path comparisons and equivalent attention to every other illustration. Visual references are quant-workspace-standards e63f5d7, Observable Plot's axes/small multiples and Motion Canvas's step sequencing. These references do not add runtime dependencies.

## Design

- Use a neutral document surface, thin aligned rules, a warm active accent and direct labels. Use outlines/dashes as well as color.
- Keep controls and plot bounds stable as records change. Show one source-bound causal explanation per step, with exact previous/current values where useful.
- Account: a connected execution rail and recorded account changes.
- Book: order blocks, explicit unfilled/reported states and an event rail with recorded clocks.
- Costs: gross amount with included-impact annotation and separate cash fees; never add impact twice.
- Impact: two directly labeled observed series, event-order axis and actual clock labels; no invented continuous trajectory.
- Lots: labeled A/B candidate lattice, feasibility, selected finite candidate and accessible cell details.
- Paths: aligned event rail across four independent scenario rows; show each mapped account at the selected point. Missing mappings/clock mismatches remain unavailable. Scenario/event selection is atomic and pauses playback. These supplied cases have no probability weights.
- Selection: signed scores against a common zero, separate current inspection and selected result.
- Risk: paired forecast/observed marks with common units, visible unknowns, and record cards for account presets.
- Replace the eight-question count and sequence breadcrumb with mechanism overview and semantic demonstration categories. Keep all eight URLs and previous/next example links.

## Constraints

- Preserve trace files, financial arithmetic, source pointers and all existing URLs/anchors.
- Preserve continuous loops, manual transport, reduced motion, offscreen pause and complete no-JavaScript tables.
- English default, paired Chinese catalogs, natural prose and Chinese punctuation.
- Never infer probability, learned market response, calibrated queue position or unsupported optimization guarantees.
- Outputs/caches remain in a task-specific external data directory; no production state changes.

## Tasks

- [x] Add tests for comparison alignment, missing evidence, cross-preset selection and precise clock handling.
- [x] Implement shared source-record formatting and atomic path event selection.
- [x] Rebuild all eight illustrations with stable geometry, direct labels and accessible controls.
- [x] Update semantic navigation in both locales and test absence of stale count labels.
- [x] Inspect all diagrams at desktop/mobile sizes and in both themes; review prose and source limitations.
- [x] Audit all 53 published Chinese reference pages and website catalogs for reversal framing; rewrite 41 reference pages with scope stated directly. Preserve code blocks, formulas, headings and financial limitations.
- [ ] Run targeted frontend and complete browser validation, strict site assembly, required repository checks; merge and verify publication.
