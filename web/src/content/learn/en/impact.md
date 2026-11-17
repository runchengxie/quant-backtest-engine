<h2 id="product-question">Question</h2>

Does your first trade make the next trade more expensive?

<h2 id="product-try">What changes</h2>

Start with small and step through fill, recovery, fill and recovery. Compare Unaffected price, Transient displacement and Fill/mark offset. Then choose close to see the shorter pause. Choose nondecaying to separate the persistent assumption from the decaying state.

<h2 id="product-read">What to notice</h2>

The last small event still records a positive displacement: “recovering” does not mean it has instantly returned to the unaffected price. In nondecaying, the persistent term remains after waiting. That difference comes from the specified model assumption.

A transient state can shrink during a pause while the permanent state stays put. The fill/mark offset is a separate recorded output with its own timing and pricing convention; adding the state bars would create a second pricing model. Permanent impact here is a sensitivity assumption, not proof that a real price will never recover.

<h2 id="product-unknown">What remains unknown</h2>

Large changes two inputs together: 200 shares and 120 seconds, compared with small’s 100 shares and 60 seconds. Close uses 100 shares and 10 seconds. Nondecaying uses 100 shares, 60 seconds and coefficient 0.001. All transient coefficients are 0.002 with decay time 60 seconds. These are prepared sensitivity cases, not calibrated permanent or cross-asset impact.
