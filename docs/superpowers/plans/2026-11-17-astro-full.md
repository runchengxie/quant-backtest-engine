# Astro-only documentation and method learning plan

**User decision:** Fully migrate to Astro; retain legacy links and English/Chinese. Reuse existing eight scenes,21 presets, replay state and public synthetic fixtures. This is a renderer/content change, not a financial-backend migration.

**Goal:** One Astro-owned published site for reference docs and richer interactive explanations of how prediction, planning, execution, partial fills, opportunity costs, impact and replanning connect.

**Architecture:** Preserve canonical docs Markdown, locale catalogs, exact owner-generated data and existing state reducer. Add direct reference rendering and same-source receipts; remove MkDocs from active build/deploy. Preserve all historical routes and fragment IDs with meaningful aliases, search,404, asset/download links, locale persistence, reduced-motion and no-JS tables. Public examples remain synthetic. No private market data or claims to know an unpublished proprietary algorithm.

## Independent file ownership

- Renderer worker: Astro reference renderer/preparation and routes, build configuration/workflow, assembly/identity/check tooling and direct tests. Do not alter existing replay components, their catalogs, styles, or financial fixtures.
- Teaching worker: scene-specific visuals and narrative flow; owns replay enhancement components, explanatory content, their own locale catalogs and component styles/tests. Do not alter shared SiteLayout, reference compiler/build tools/workflow or existing bound numerical fixtures.
- Parent: synthesis/docs, any additional bound synthetic opportunity-cost/joint-planning evidence, final cross-component integration and verification. Coordinate shared files explicitly.

## Acceptance tasks

- [x] Direct reference Markdown rendering without running MkDocs; port used tables, details/admonitions, IDs, fences, links and legacy replay placeholders.
- [x] Preserve legacy routes/anchors, assets/search, English default and reciprocal Chinese routes; one complete artifact with byte/source receipts.
- [x] Improve shared event-linked visuals for book depth, impact and finite feasible grids; connect forecast→portfolio→orders→fills→account→replan, making unknown/missing evidence visible.
- [x] Explain opportunity cost without charging missed gains twice; deterministic scenarios are not probabilities; permanent impact parameters are assumed; nonconvex finite search is not a global HJB certificate.
- [x] Verify ownership, locked Astro/type/unit/browser tests, method/export fixtures, link/anchor/locale/no-JS/reduced-motion behavior; run required Rust and CLI checks.
- [ ] Independently review, deliver via user-owned PR, confirm live deployment, archive verified output/source and clean only this task.

## External references

Official Astro content collections support direct Markdown rendering. Starlight demonstrates standard documentation navigation and custom pages. Distill's momentum article and Seeing Theory inform explanation patterns only; do not copy their code/design assets without an explicit compatible license review. Existing financial owner provenance and licenses remain authoritative.

## Implementation verification

The completed local build has 139 Astro HTML routes. Exact legacy route/fragment admission and source identity passed. Ownership/reference/assembly/opportunity tests passed (59), frontend units passed (8), existing method checks passed (12, one optional installed-owner check skipped), legacy replay/DOM checks passed (5/4), and the required Rust formatting, clippy, tests and synthetic roundtrip CLI passed. Local frontend audit found no vulnerabilities. The local Node patch is 26.13.1; CI retains the pinned 26.13.0. Desktop/mobile acceptance includes both languages, no-JavaScript tables, reduced motion, synthetic opportunities, SVG hydration and system theme toggling. Final source acceptance and publication are recorded by the task PR and its exact CI/deployment revisions.
