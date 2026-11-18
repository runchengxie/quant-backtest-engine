<h2 id="product-question">Question</h2>

How does waiting between purchases change the second fill price?

<h2 id="product-try">Try it</h2>

Start with 100 shares, 60 seconds, no permanent term and inspect recovery between the fills. Then select 100 shares, 10 seconds, no permanent term and compare the second fill. Both have unaffected price 10.

<h2 id="product-read">Read the result</h2>

With a 60-second pause, the second fill price is approximately 10.1736. With 10 seconds, it is approximately 10.2693. Both are rounded to four decimal places. Check the exact values in the tables below. Transient impact shrinks while waiting, so the shorter pause leaves a larger price offset in this model. The final recovery event still has positive transient impact.

The nondecaying stress assumption retains a permanent term after waiting. Its persistence is specified by the model. Fill or mark offset is recorded separately under its own timing and pricing convention. Read that output directly. Summing the two states would introduce another pricing rule.

<h2 id="product-unknown">Evidence limits</h2>

The 200-share, 120-second case changes quantity and pause together. The other two cases without a permanent term use 100 shares with pauses of 60 and 10 seconds. The nondecaying case uses 100 shares, 60 seconds and coefficient 0.001. All cases have transient coefficient 0.002 and decay time 60 seconds. These presets compare assumptions. Real permanent and cross-asset impact remain uncalibrated.
