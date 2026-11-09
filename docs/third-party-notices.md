# Third-party notices

This project directly depends on NautilusTrader 0.66.0 crates, including
nautilus-backtest, nautilus-model, nautilus-trading, nautilus-common,
nautilus-execution and nautilus-core.

Upstream. https://github.com/nautechsystems/nautilus_trader
Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
License. GNU Lesser General Public License, version 3 only (LGPL-3.0-only).

This repository uses public upstream APIs. It does not vendor or fork the engine.
The adapter source is original integration code. Cargo.lock records exact dependency
versions and checksums. Transitive dependencies retain their own licenses, documented
in their published crate packages. Preserve applicable notices when distributing
source or binaries, including LGPL/GPL texts and corresponding-source obligations.

The GNU LGPL version 3 text is in [LICENSE](https://github.com/runchengxie/quant-backtest-engine/blob/main/LICENSE). Its referenced GNU GPL version 3 text
is in [COPYING](https://github.com/runchengxie/quant-backtest-engine/blob/main/COPYING). These files do not transfer third-party copyright to this project.

## Extracted quant-platform leaves

The Python core contains source, tests and documentation extracted from
[quant-platform revision 7a618bd](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355),
originally distributed under Apache-2.0. The original tree has no NOTICE file.
Per-file source paths and SHA256 values are recorded in
[core notices](https://github.com/runchengxie/quant-backtest-engine/blob/main/core/THIRD_PARTY_NOTICES.md).
The original Apache license is reproduced byte-for-byte and included with those
notices in the wheel license metadata. Original terms and attribution are
preserved; the Engine package license does not replace them. Changes relocate
modules/helpers and imports, format source, and add typed quote transport;
financial arithmetic is unchanged. Paired leaf documentation preserves the
source scope and limitations with Engine namespace/examples.
