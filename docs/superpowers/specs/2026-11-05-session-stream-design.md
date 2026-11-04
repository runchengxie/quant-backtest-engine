# Interactive session transport

The authorized next engine step adds `session-stream`, an opt-in synchronous NDJSON
transport over stdin and stdout. Existing v1/v2 commands and results stay compatible.
One dedicated upstream thread owns the living Nautilus engine. Whole sessions are
pulled only after the previous snapshot and provisional report callback complete.

## Approach

A callback extends the existing iterator API while preserving its wrapper. A separate
transport module owns strict frames, bounded IO and the hash chain. Buffering all
frames would prevent interactive feedback. A second execution ledger would duplicate
upstream accounting, so reports instead select the current session's upstream orders,
fills and rejections and reuse its existing daily balance and positions.

Input schema `engine_session_stream.v1` uses `type` and `sequence`. Start sequence 0
contains `config`, session sequences 1 through N contain `session`, and finish sequence
N+1 has no payload. Output schema `engine_session_stream_result.v1` returns ready,
session and finished with matching sequences. Ready includes `header_sha256` and
`max_frame_bytes`. Session includes `prefix_sha256` and `report`. Finished includes
`prefix_sha256` and the unchanged collected v2 `result`.

SHA256 hashes exact UTF-8 JSON bytes excluding the required LF. The start digest is
the header hash. Each later digest hashes the prior raw 32 bytes followed by that
frame's exact JSON bytes. Limits are 67108864 bytes including LF in both directions.
Unknown and duplicate fields, malformed JSON, invalid UTF-8, truncated lines, sequence
violations, empty finish and missing finish fail. Finish must be followed by EOF before
final success. Every output frame is serialized within the bound before writing and
flushed immediately. Earlier reports remain provisional on any later failure.

SessionReport contains zero-based `session_index`, `session_date`, `valuation_ts_ns`,
`balance`, `positions`, `orders`, `fills` and `rejections`. No financial checkpoint,
source path, job activation or constant-total-memory claim is added. Histories and
collected output continue to grow while quote input is held for one session.
