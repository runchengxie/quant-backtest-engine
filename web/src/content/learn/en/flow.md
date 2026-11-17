<h2 id="product-question">Question</h2>

Why can an account end above its starting cash even after fees?

<h2 id="product-try">What changes</h2>

Open the replay and press Step to move from the supplied order to the buy fill and then the sell fill. Watch Cash, Shares and Fees together. The initial “input” is a supplied-order setup, not a prediction discovered by the system.

<h2 id="product-read">What to notice</h2>

At the final sell event, shares return to zero, fees remain paid, and the final cash can be checked against the original Rust result below. Read those fields together: a cash increase alone does not tell you whether inventory remains.

The conceptual map connects prediction, portfolio target, order, execution, account and replanning. This supplied-order example starts after prediction and target selection; those stages remain unknown. Portfolio constraints shape intentions, execution determines actual holdings, and the resulting account informs the next decision. These public modeling ideas do not authenticate an unpublished proprietary algorithm.

<h2 id="product-unknown">What remains unknown</h2>

This is one synthetic round trip. It verifies the recorded accounting path; it cannot show whether a strategy forecasts prices well.
