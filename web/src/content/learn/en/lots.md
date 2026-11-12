<h2 id="product-question">Question</h2>

Why can rounding a desired portfolio produce a bad trade?

<h2 id="product-try">Try it</h2>

Compare no-minimum with minimum. Step from Heuristic to Bounded optimum and inspect the full grid. Each cell is one whole-share pair; feasible cells satisfy the recorded owner checks. Switch to grid for the other fixed target.

<h2 id="product-read">Read the recorded result</h2>

With no minimum fee, the bounded result can hold one share of A and two of B. With a minimum fee, the recorded result changes to one of each. The extra cash cost changes which integer choices fit the budget. A point halfway between two grid cells may require fractional shares and is not an allowed choice: this is the discrete, nonconvex lesson.

<h2 id="product-unknown">What remains unknown</h2>

The domain is only {0,1,2,3}², with cash 14 and prices (6,4). “Optimum” means best within these 16 choices. There is no recorded continuous descent or general global-optimality proof.
