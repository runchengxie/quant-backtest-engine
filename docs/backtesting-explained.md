# Backtesting explained

[简体中文](backtesting-explained.zh-CN.md)

A forecast becomes useful only when an affordable order can fill and the resulting account can support the next decision. A return curve hides much of that journey. Follow the quantities and cash below, then change one prepared scenario at a time.

These examples were exported from the public implementations linked beside each scene. All inputs are synthetic. Python Platform owns the richer execution, impact and optimization examples; the Rust Engine example has its own narrower contract. Real order-book calibration, historical auction queues and prospective performance remain unverified.

The tables contain every prepared state, even without JavaScript. **Play** is optional; **Step** advances one event. Scenario choices replay separately generated owner results. The browser does not calculate fills or rerun a financial model. Monetary strings retain the owner's precision; a long decimal in a table is an exported numerical value, not additional economic accuracy.

## 1. From forecast to the next account

**Takeaway: each decision must use the account produced by actual fills.**

A strategy supplies a forecast. A planner turns it into a feasible order. The execution owner determines eligible fills and settles fees. The resulting cash, holdings and outstanding orders constrain the next decision. Runtime supervises execution and recovery; it does not invent another matching or accounting engine.

Start with the Rust Engine's existing round-trip fixture. It buys 10 shares at USD 10, then sells those 10 at USD 12. The quote at USD 11 arrives later and does not set the exit price. The fee is 10 basis points per trade, so commissions total USD 0.22 and the final cash is USD 10,019.78. An order can use only a strictly subsequent eligible quote. This is a conformance example with supplied orders; it does not contain a forecast optimizer.

<!-- method:flow -->

??? details "The accounting and the next decision"
    `10,000 − 10 × 10 − 0.10 + 10 × 12 − 0.12 = 10,019.78`.
    The information and fill clocks in this table are UTC nanoseconds. They are encoded as strings so the browser cannot round them.

    In a rolling plan, only the first action is executed before planning again. [Boyd and colleagues](https://stanford.edu/~boyd/papers/cvx_portfolio.html) explain this general multi-period approach. Their paper does not establish the quality of these synthetic forecasts. For a runnable Engine planning example, continue to the [target-weight walkthrough](tutorial.md).

## 2. An order meets a finite book

**Takeaway: a visible price is not a promise that your whole order can trade there.**

The synthetic best bid is 99. There are only 5 shares offered at 101 and another 10 at 110. A 20-share buy limit at 110 takes 5 shares from the nearer offer and 10 from the next level. Five requested shares remain unfilled. The actual gross payment is `5 × 101 + 10 × 110 = 1,605`; the fill-weighted average is 107.

The first two fill rows represent the two executions at the same 1,000 ms matching event. They are displayed separately so you can see depth disappear. The final row illustrates a report arriving at 1,600 ms. That 600 ms delivery rule is a declared presentation assumption. The financial-session recovery example later uses the actual owner's delayed-report mechanism.

<!-- method:book -->

??? details "Spread, depth and evidence limits"
    The initial best-quote spread is `101 − 99 = 2`. Prices here are synthetic currency units per share; time is elapsed milliseconds. Python Platform's ticknet price-time matcher generated the fills. This diagram does not reconstruct a historical queue, infer hidden liquidity or implement auction priority. A partial fill leaves an outstanding quantity; it does not silently complete the order at the final mark.

## 3. Trading can leave a state behind

**Takeaway: distinguish the external price path from your assumed impact state.**

Hold the unaffected price at 10. In the reference case a 100-share buy adds 0.2 to transient displacement. Its average execution offset is 0.1 because the owner uses half of the current order's increment in the execution price. After 60 seconds the remaining displacement is about 0.0735758882. A second buy encounters that remaining state.

Compare a larger order, closer spacing and an explicitly nondecaying stress assumption. Size and spacing are discrete prepared controls, not freely calibrated parameters. The nondecaying term is zero in the reference. Its nonzero alternative is an assumption for sensitivity analysis.

<!-- method:impact -->

??? details "Published formula and units"
    For signed quantity `q`, the transient state just before execution is `x⁻ = x × exp(−Δt / τ)`. The execution offset is `x⁻ + p + (η + γ)q/2`; the new states are `x⁺ = x⁻ + ηq` and `p⁺ = p + γq`. Here `η = 0.002` price units per share, `τ = 60` seconds, and `γ` is either zero or the stated nondecaying stress coefficient.

    The lines show state displacement, including the zero unaffected-price displacement baseline. The table separately retains the unaffected price and the execution or mark offset. Same-clock decay and fill rows have the same elapsed second. [Obizhaeva and Wang](https://web.mit.edu/wangj/www/pap/ObizhaevaWang13.pdf) motivate dynamic liquidity and recovery. They do not calibrate these coefficients or prove that a permanent component is present in a particular market.

## 4. Pay each cost once

**Takeaway: a cost inside the execution price must not be debited again as a fee.**

One 100-share fill at 10.1 costs 1,010 before the fee. Relative to the unaffected price of 10, that price already includes 10 of impact. A minimum commission of 1 brings the total cash debit to 1,011. Starting from 12,000 leaves 10,989. The impact model updates once, and the cash ledger pays once.

Spread and price impact affect the execution price; commission is a separate cash charge. Benchmark shortfall also describes the cost of waiting or not filling. Those descriptive comparisons do not automatically create a new cash payment. Subtracting the 10 of impact again would incorrectly report 10,979.

<!-- method:cost -->

??? details "Cash and opportunity measures"
    `cash_after = cash_before − gross_payment − cash_fees` for this buy. The synthetic coefficient in this case is a nondecaying sensitivity assumption of 0.002 per share. It is not the transient reference from scene 3.

    For a buy, a simple benchmark decomposition compares filled quantity times execution-price difference, explicit fees, and unfilled quantity times a stated comparison-price difference. The last component depends on the chosen benchmark. Keep it outside the cash ledger. [Execution assumptions](execution.md) describe the Engine's own supported fee and price semantics.

## 5. Whole shares and minimum fees change the feasible set

**Takeaway: rounding and fixed costs can change which portfolio is affordable.**

There are two assets priced at 6 and 4, with cash of 14. Each can have zero to three whole shares. A target of 1.6 shares in each asset chooses `(1, 2)` when minimum fees are zero. Adding a minimum fee of 1 per nonzero order changes the best feasible answer to `(1, 1)` and leaves cash of 2.

The third scenario changes the target to `(1.5, 1.5)` and exposes all 16 grid states. Seven are feasible with the minimum fee. The best squared tracking error is 0.5 at `(1, 1)`. The displayed heuristic happens to match the bounded optimum here; that agreement is a result of this case, not a general promise.

<!-- method:lots -->

??? details "Objective and funding domain"
    Minimize `(qA − targetA)² + (qB − targetB)²` over integer holdings in `{0,1,2,3}²`, subject to the cash and fee constraint. Buys and all fees must be prefunded. Projected sale proceeds cannot finance another order before the owning ledger actually settles the sale. No global-optimality claim extends beyond this explicitly enumerated domain.

## 6. Change execution separately from the market

**Takeaway: reuse the forecast, then rerun each account and its decisions independently.**

The first two cases use identical forecast and external-price inputs. Participation caps differ, so the thin case buys only 200 shares while the deeper case buys 1,000. Their cash and pending orders evolve independently. Changing only the final external price to 10.5 changes the thin account's later cost. That is a market-path change, separate from execution capacity.

The feedback case reads the 100 shares actually obtained at the next decision and changes its target weight to 0.1. It preserves that inventory instead of continuing toward the original full-investment request. The decision rows retain actual cash and pending-order status. Replaying one fixed forecast does not create new independent observations of a real market.

<!-- method:paths -->

??? details "What is recomputed"
    Each scenario calls the public minute execution owner with a fresh account. A decision uses strictly prior marks and actual visible holdings. The simple declared policy either preserves a pending order or, in the feedback case, targets the weight of the actual holding. The exporter records separate forecast and market hashes, complete fills and orders. There is no fitted forecasting model or browser-side simulator in this page.

## 7. Keep every attempted path

**Takeaway: selecting the largest historical return changes the question you are answering.**

The public no-signal fixture has four synthetic returns, two at `−1/64` and two at `+1/64`. Its supplied forecast has zero covariance with return. Before looking at results, this teaching search declares all six equal-weight, two-asset subsets. It then scores every subset on the same four observations and selects the maximum.

The scores are `−1/64, 0, 0, 0, 0, +1/64`. The winning 1.5625% is visible, and so are the losing and zero-return attempts. The mean of the six scores is zero. This finite illustration deliberately shows how a maximum can look favorable under a no-signal construction. It is not an estimate of a real strategy's false-positive probability.

<!-- method:selection -->

??? details "Selection evidence and its boundary"
    This is a scripted, exhaustive teaching enumeration over the public null fixture. There is no private research import, adaptive campaign, statistical significance test or new out-of-sample result. [Bailey and colleagues](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) discuss backtest overfitting from selecting configurations. Their PBO/CSCV method differs from this simple demonstration. Retain the full attempted set before making any claim about selection.

## 8. Recovery and a finished chart do not finish an exit

**Takeaway: preserve restrictions and unsettled state, and distinguish marked wealth from cash you can realize.**

Choose a prepared risk case. The recovery case interrupts a Python Platform session at every unfinished event boundary, restores its checkpoint, and compares its financial tables with an uninterrupted run. Delayed reports can leave the strategy unaware of an economic fill; the session keeps that outstanding state and prevents duplicate submission. The replay shows those verified outcomes, not a live process kill.

The shared-liquidity case combines two 500-share demands into one external 1,000-share request. One bar permits just 100 shares. Allocation consumes the single physical fill and fee once, including when the same fill record is presented twice. Its deterministic priority gives 100 shares to the first sleeve and zero to the second in this example. It does not grant each sleeve another independent capacity budget.

The exit case buys 500 shares, encounters a locked next day, then sells only 100 when capacity allows. Final cash is 6,000 and 400 shares remain. A fresh mark of 10 gives marked wealth of 10,000, while fully realized wealth remains unknown. Stale or absent marks would also make marked wealth unknown. A mark never manufactures liquidation proceeds.

The financial-action case starts with 200 shares and cash of 8,000. On the ex-date, 200 cash rights and 200 stock rights preserve wealth of 10,000 at a 4.5 mark. Payment and release produce 400 shares and cash of 8,200. A separate continuation marks those shares at 3, giving wealth of 9,400 before a 1,000 deposit. Wealth then reaches 10,400; that deposit is external capital, not trading profit. Every unfinished event boundary in that continuation is also restored and compared, including the rights and pending reports.

The risk audit matches forecast and outcome on the same one-day horizon and basis-point units. Four synthetic forecast variances average 2.5, while squared realized residuals average 12.5, giving a ratio of 5. In the missing-outcome case, the two illiquid rows remain in the report with zero coverage and unknown cohort variance diagnostics. Missing observations do not become zero losses or disappear from the denominator. Four target intervals do not establish independence or real calibration; the owner explicitly marks calibration unavailable and certification false.

<!-- method:risk -->

??? details "Operational recovery is a separate acceptance boundary"
    These frames verify Platform financial state restoration, including delayed visibility. Runtime owns process supervision and persisted job recovery; see its [financial-session evidence](https://github.com/runchengxie/quant-backtest-runtime/blob/01ed4c34f955ef6cd39d13aa073b6d61b610d321/docs/financial-sessions.md). A browser replay does not reproduce that process-kill acceptance. Checkpoint hashes detect accidental changes and bind inputs and loaded source; they are not a security boundary against a malicious author.

## Evidence map and reproduction

| Component | What this page checks | What remains outside this evidence |
| --- | --- | --- |
| Rust Engine | Existing synthetic quote fills, fees and final balances | The Python impact model, discrete optimizer and minute policy are not Rust capabilities |
| Python Platform | Synthetic book matching, impact state, fee/lot feasibility, independent accounts, feedback, allocation and financial restoration | Real market calibration, historical queue reconstruction, actual liquidation and prospective profitability |
| Runtime | Linked merged public process-recovery acceptance | The animation itself does not run or kill a worker |
| Teaching selection search | Every one of six fixed null-fixture portfolios | PBO/CSCV, general error control and real out-of-sample evidence |

[Fixture JSON](assets/method/fixtures.json) retains exact merged owner identities, source and input hashes, clocks, units and economic outputs. The exporter file hash identifies the actual exporting code, including before its commit. The page embeds those local states at build time and sends no requests for data, scripts, fonts or telemetry outside this site.

Fixture configuration bindings include typed, fully resolved public-owner call definitions. The exporter executes those serialized definitions, preserving exact float bits, frame dtypes, clocks and every configuration default. Action baselines and continuations are separate runs. Each run has its own digest, and the overall input/configuration digest covers all contributing runs; mutation tests verify that changed cash, capacity, latency, impact and report delay change the binding and the actual owner behavior.

Normal Rust, standalone Python client and documentation builds do not require Platform or Runtime. To regenerate the optional fixtures, use clean checkouts at the pinned public revisions in the JSON and a separately locked Platform development environment with its microstructure dependencies. Build the Engine from the recorded source revision, then run the exporter with explicit paths. Keep environment, build and output paths outside source repositories.

```bash
python project_tools/export_method_fixtures.py \
  --platform "$PLATFORM_CHECKOUT" --runtime "$RUNTIME_CHECKOUT" \
  --engine "$ENGINE_BINARY" --output "$OUTPUT_DIR/fixtures.json"
python -m unittest discover -s project_tools -p 'test_method_*.py'
node --test project_tools/test_method_replay.cjs
```

Set `METHOD_OWNER_PARITY=1`, `METHOD_PLATFORM`, `METHOD_RUNTIME`, `METHOD_PYTHON` and `QUANT_ENGINE_BINARY` to rerun the optional owner-export parity test against the checked-in fixture. The [development guide](development.md) covers the locked docs build and existing Rust/client checks. Continue to [capabilities](capabilities.md) for the exact supported Engine contract.

For the optional mounted-control tests, copy `project_tools/method-tests/package.json` and its lockfile to a separate tooling directory, run `npm ci --ignore-scripts` there, and set `NODE_PATH` to that directory's `node_modules` when running `node --test project_tools/test_method_dom.cjs`. These DOM tests verify behavior without claiming real-browser acceptance. The manually dispatched **Method fixture owner parity** workflow regenerates with pinned public owners in a separate job; normal builds remain independent of those owners.
