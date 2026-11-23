# Analytic liquidation reference implementation plan

[简体中文](2026-11-23-control-reference.zh-CN.md)

**Goal and design:** Add a standard-library-only, single-asset finite-horizon LQ liquidation reference to `quant_backtest_core.planning.liquidation_reference`. Minimize the integral of `eta*v² + lambda*sigma²*x²`, with `dx/dt=-v`, positive horizon and eta, nonnegative initial inventory, lambda and sigma, and hard zero terminal inventory. Return inventory, rate and remaining value at caller-supplied elapsed seconds. This is an analytic benchmark, with no accounting, forecasts, fills or general PDE solver.

**Architecture:** Frozen request/result dataclasses and a pure evaluation function. Use dimensionless hyperbolic ratios and expm1 for stable zero-risk and large-argument limits. Reject nonfinite inputs and unrepresentable intermediate/output domains explicitly. Time and coefficients are caller supplied in seconds, shares and one chosen currency.

**Plan:**

- [ ] Add tests first: hand-computed TWAP, analytic inventory properties, numerical cost integral and HJB residual, zero inventory, terminal boundary, extreme coefficients and invalid inputs; observe failure.
- [ ] Implement the small independent module; run tests and optional core regressions.
- [ ] Add paired capability/decision documentation comparing existing MPC and transient impact with this reference and unimplemented stochastic control; link from impact planning.
- [ ] Run repository Rust, ownership and documentation validation; record exact results and source revision; commit for independent review.

**Review focus:** near-zero risk cancellation; large hyperbolic arguments; finite inputs with overflowing derived costs; terminal value singularity for nonzero inventory; no implied execution or calibration certificate.
