<h2 id="product-question">Question</h2>

With cash of 14, which whole-share portfolios can you afford?

<h2 id="product-try">Try it</h2>

Compare No minimum fee with Minimum fee 1. Step from Heuristic to Bounded optimum and inspect the full grid. A costs 6 and B costs 4. Each square represents one integer share pair, colored by recorded feasibility. Full 16-point grid uses another fixed target.

<h2 id="product-read">Read the result</h2>

Without a minimum fee, the bounded result holds one A and two B, using all cash. With a minimum fee, it holds one of each, pays fees of 2 and retains cash of 2. Buying more A leaves less cash for B. Minimum fees also change which portfolios fit the budget.

Inspect the selected square and its neighbors for cash and feasibility. A midpoint between whole-share portfolios may require half a share, outside the allowed choices. This discrete restriction gives a nonconvex feasible set. There are no continuous trading choices between grid points. Read failed feasibility checks as rejected choices.

<h2 id="product-unknown">Evidence limits</h2>

The search covers only {0,1,2,3}², or 16 choices. Optimality applies within that domain. No continuous descent is recorded, and the case supplies neither general global-optimality proof nor an HJB solution.
