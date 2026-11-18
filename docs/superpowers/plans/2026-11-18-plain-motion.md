# Plain language and event-linked motion

**Goal** Make the existing eight synthetic lessons easier to follow through short event explanations, restrained motion and direct Chinese prose.

**Architecture** Keep all owner-generated trace bytes, replay event IDs and accounting unchanged. Add presentation-only transitions and event-linked captions. Existing controls own timing and selection. English remains the default, with aligned Chinese text in locale catalogs. Use human-writing for the Chinese tutorial copy and keep assumptions visible.

**Design decision** Build on the current warm-paper layout. One main illustration stays visible in each lesson. A short current-step caption names the observed action, followed by exact recorded values. Motion illustrates transitions between records. The user selected continuous automatic looping. It starts when the chart first enters view after hydration. Manual actions and hidden/offscreen transitions pause it until explicit Play. Reduced motion remains manual. Short transitions connect exact recorded states. Keep complete tables and provenance available.

- [x] Rewrite EN/ZH lesson copy and presentation catalogs. Chinese prose uses direct statements and Chinese punctuation, with no rhetorical reversal, colons, em dashes, quotation marks or semicolons.
- [x] Add a coherent event-linked motion layer for all eight scenes. Keep simple visuals for fills and account changes, and use clear highlighting for finite portfolio choices and separate scenario accounts.
- [x] Verify exact replay state, unknown values, keyboard use, pause/reset, reduced motion and no-JS tables. Inspect actual desktop/mobile screenshots and motion in a browser.
- [ ] Run affected security, ownership, site and required repository checks. Independently review, deliver through an owned PR, deploy, verify live source/hashes/interactions and retire only this task worktree.

**File ownership** The writing worker owns learn Markdown, editorial locale JSON and teaching-catalog wording. The parent owns components, CSS, replay controls, new motion catalogs, integration and tests. Coordinate shared catalog keys before editing. All Git writes belong to the parent.

**Visual references** Study the diagram/control coupling in Red Blob Games A* explanations, the restrained labels and pause controls in Bartosz Ciechanowski Mechanical Watch, and Distill article reading width. Borrow explanatory patterns, no source artwork or code. Match the owner standards project previous/play/next/restart controls. Chinese typography uses an explicit CJK sans stack with comfortable line height and tabular figures.
