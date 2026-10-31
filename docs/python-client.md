# Python wire client

The `quant-backtest-engine-client` distribution provides a standard-library-only Python 3.11+ client. It does not require quant-platform, pandas, NumPy, or the runtime service. Install from an engine source checkout.

```sh
python -m pip install ./python
```

Select an absolute executable path and a SHA256 digest verified against the release manifest.

```python
import json
from pathlib import Path
from quant_backtest_engine import EngineClient

client = EngineClient(
    Path('/absolute/path/to/quant-backtest-engine'),
    sha256='REPLACE_WITH_VERIFIED_RELEASE_SHA256',
    timeout=30,
    source_revision='REPLACE_WITH_RELEASE_SOURCE_REVISION',
)
request = json.loads(Path('fixtures/sessions.json').read_text())
result = client.run_sessions(request)
print(result['final_nav'])
```

`size(request)` accepts `sizing_request.v1` and returns `sizing_result.v1`; `run_sessions(request)` accepts `engine_request.v2` and returns `engine_result.v2`. Both return plain dictionaries with monetary decimal strings and integer UTC nanosecond timestamps preserved. The optional source revision is caller metadata, not a substitute for the executable digest.

The client checks the executable digest and runs a private copy of the verified program.
After the process succeeds, it strictly parses JSON and checks that every requested
order has a result, fills occur at eligible times and valuation marks match the request.
It also checks result fields and statuses, daily cash, shares, fees, NAV and configured
T+1 sell eligibility. Process failures or inconsistent results raise `EngineProtocolError`
(a `ValueError`). Invalid constructor arguments raise `ValueError`. The engine enforces
the trading rules in the request. Quantity planning estimates orders at reference
prices; later quotes and available cash determine actual fills.

The SDK owns transport and wire validation. Consumers own conversion to their tables, strategy interfaces, and persistence; the SDK contains no matching or portfolio simulation. The existing Rust engine and its upstream accounting remain authoritative. The Python code is distributed under this repository's LGPL-3.0-only license; its boundary checks were extracted from the same owner's quant-platform client.

Run synthetic SDK tests using an installed wheel from outside the checkout. Set `QUANT_ENGINE_BINARY` to additionally run the release-binary integration test. CI builds a wheel, installs it without dependencies in a clean environment, runs the suite, and then exercises the Rust-built CLI.

[简体中文](python-client.zh-CN.md)

CNY session validation requires the host timezone database to include `Asia/Shanghai` (normally supplied by system tzdata). Minimal containers and Windows hosts must provide that database; missing zones raise `EngineProtocolError` with an installation hint.
