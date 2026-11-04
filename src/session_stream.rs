//! Bounded, interactive whole-session NDJSON transport. Reports remain provisional.
use crate::{
    run_sessions_iter_with_reports,
    session_contract::{MarketSession, SessionConfig},
};
use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    io::{BufRead, Read, Write},
    sync::{Arc, Mutex},
};

pub const MAX_FRAME_BYTES: usize = 67_108_864;
const INPUT_SCHEMA: &str = "engine_session_stream.v1";
const OUTPUT_SCHEMA: &str = "engine_session_stream_result.v1";

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase", deny_unknown_fields)]
enum Frame {
    Start {
        schema_version: String,
        sequence: u64,
        config: SessionConfig,
    },
    Session {
        schema_version: String,
        sequence: u64,
        session: MarketSession,
    },
    Finish {
        schema_version: String,
        sequence: u64,
    },
}
impl Frame {
    fn header(&self) -> (&str, u64) {
        match self {
            Self::Start {
                schema_version,
                sequence,
                ..
            }
            | Self::Session {
                schema_version,
                sequence,
                ..
            }
            | Self::Finish {
                schema_version,
                sequence,
            } => (schema_version, *sequence),
        }
    }
}

fn read_frame(reader: &mut impl BufRead, limit: usize) -> Result<(Frame, Vec<u8>)> {
    let mut bytes = Vec::new();
    reader
        .take((limit + 1) as u64)
        .read_until(b'\n', &mut bytes)?;
    ensure!(bytes.len() <= limit, "input frame exceeds maximum bytes");
    ensure!(bytes.last() == Some(&b'\n'), "missing or truncated frame");
    bytes.pop();
    let frame = serde_json::from_slice::<Frame>(&bytes).context("invalid session stream JSON")?;
    ensure!(
        frame.header().0 == INPUT_SCHEMA,
        "unsupported session stream schema"
    );
    Ok((frame, bytes))
}

struct BoundedBuffer {
    bytes: Vec<u8>,
    limit: usize,
}
impl Write for BoundedBuffer {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if bytes.len() > self.limit.saturating_sub(self.bytes.len()) {
            return Err(std::io::Error::other("output frame exceeds maximum bytes"));
        }
        self.bytes.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
fn write_frame(writer: &mut impl Write, value: &impl Serialize, limit: usize) -> Result<()> {
    let mut buffer = BoundedBuffer {
        bytes: Vec::new(),
        limit,
    };
    serde_json::to_writer(&mut buffer, value)?;
    buffer.write_all(b"\n")?;
    writer.write_all(&buffer.bytes)?;
    writer.flush()?;
    Ok(())
}
fn hex(digest: &[u8; 32]) -> String {
    digest.iter().map(|b| format!("{b:02x}")).collect()
}

struct Source<R> {
    reader: R,
    sequence: u64,
    prefix: [u8; 32],
    finished: bool,
    limit: usize,
}
impl<R: BufRead> Source<R> {
    fn pull(&mut self) -> Result<Option<MarketSession>> {
        let (frame, bytes) = read_frame(&mut self.reader, self.limit)?;
        ensure!(
            frame.header().1 == self.sequence + 1,
            "nonmonotone frame sequence"
        );
        let mut hash = Sha256::new();
        hash.update(self.prefix);
        hash.update(bytes);
        self.prefix = hash.finalize().into();
        self.sequence += 1;
        match frame {
            Frame::Session { session, .. } => Ok(Some(session)),
            Frame::Finish { .. } => {
                ensure!(self.sequence > 1, "finish requires at least one session");
                let mut trailing = [0_u8; 1];
                ensure!(
                    self.reader.read(&mut trailing)? == 0,
                    "trailing input after finish"
                );
                self.finished = true;
                Ok(None)
            }
            Frame::Start { .. } => bail!("repeated start frame"),
        }
    }
}

/// Serves a single stream. The caller must close input after finish to establish EOF.
pub fn serve<R, W>(reader: R, writer: W) -> Result<()>
where
    R: BufRead + Send + 'static,
    W: Write + Send + 'static,
{
    serve_with_limit(reader, writer, MAX_FRAME_BYTES)
}
fn serve_with_limit<R, W>(mut reader: R, mut writer: W, limit: usize) -> Result<()>
where
    R: BufRead + Send + 'static,
    W: Write + Send + 'static,
{
    let (frame, bytes) = read_frame(&mut reader, limit)?;
    let config = match frame {
        Frame::Start {
            sequence: 0,
            config,
            ..
        } => config,
        _ => bail!("stream requires start sequence 0"),
    };
    config.validate()?;
    let prefix: [u8; 32] = Sha256::digest(bytes).into();
    write_frame(
        &mut writer,
        &serde_json::json!({"schema_version":OUTPUT_SCHEMA,"type":"ready","sequence":0,"header_sha256":hex(&prefix),"max_frame_bytes":limit}),
        limit,
    )?;
    let source = Arc::new(Mutex::new(Source {
        reader,
        sequence: 0,
        prefix,
        finished: false,
        limit,
    }));
    let writer = Arc::new(Mutex::new(writer));
    let input = source.clone();
    let sessions = std::iter::from_fn(move || input.lock().unwrap().pull().transpose());
    let current = source.clone();
    let output = writer.clone();
    let result = run_sessions_iter_with_reports(config, sessions, move |report| {
        let current = current.lock().unwrap();
        write_frame(
            &mut *output.lock().unwrap(),
            &serde_json::json!({"schema_version":OUTPUT_SCHEMA,"type":"session","sequence":current.sequence,"prefix_sha256":hex(&current.prefix),"report":report}),
            limit,
        )
    })?;
    let current = source.lock().unwrap();
    ensure!(current.finished, "missing finish frame");
    write_frame(
        &mut *writer.lock().unwrap(),
        &serde_json::json!({"schema_version":OUTPUT_SCHEMA,"type":"finished","sequence":current.sequence,"prefix_sha256":hex(&current.prefix),"result":result}),
        limit,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    struct FailedReader;
    impl Read for FailedReader {
        fn read(&mut self, _: &mut [u8]) -> std::io::Result<usize> {
            Err(std::io::Error::other("source failed"))
        }
    }
    impl BufRead for FailedReader {
        fn fill_buf(&mut self) -> std::io::Result<&[u8]> {
            Err(std::io::Error::other("source failed"))
        }
        fn consume(&mut self, _: usize) {}
    }
    struct FailedWriter;
    impl Write for FailedWriter {
        fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
            Err(std::io::Error::other("sink failed"))
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    #[test]
    fn io_failures_are_propagated() {
        assert!(
            read_frame(&mut FailedReader, 100)
                .unwrap_err()
                .to_string()
                .contains("source failed")
        );
        assert!(
            write_frame(&mut FailedWriter, &"a", 100)
                .unwrap_err()
                .to_string()
                .contains("sink failed")
        );
    }
    #[derive(Clone, Default)]
    struct Collected(Arc<Mutex<Vec<u8>>>);
    impl Write for Collected {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            self.0.lock().unwrap().extend_from_slice(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    fn fixture_frames() -> (crate::session_contract::SessionRequest, Vec<String>) {
        let request: crate::session_contract::SessionRequest =
            serde_json::from_str(include_str!("../python/tests/fixtures/sessions.json")).unwrap();
        let mut frames = vec![serde_json::json!({"type":"start", "sequence":0, "schema_version": INPUT_SCHEMA, "config": SessionConfig::from(&request)}).to_string()];
        for (index, session) in request.sessions.iter().enumerate() {
            frames.push(serde_json::json!({"type":"session", "sequence":index+1, "schema_version":INPUT_SCHEMA, "session":session}).to_string());
        }
        frames.push(serde_json::json!({"type":"finish", "sequence":request.sessions.len()+1, "schema_version":INPUT_SCHEMA}).to_string());
        (request, frames)
    }
    #[test]
    fn final_response_over_limit_preserves_only_complete_provisional_frames() {
        let (request, frames) = fixture_frames();
        let result = crate::run_sessions(&request).unwrap();
        let final_size = serde_json::to_vec(&serde_json::json!({"type":"finished", "sequence":request.sessions.len()+1, "schema_version":OUTPUT_SCHEMA, "prefix_sha256":"0".repeat(64), "result":result})).unwrap().len()+1;
        assert!(frames.iter().all(|frame| frame.len() + 1 < final_size));
        let output = Collected::default();
        let observer = output.clone();
        assert!(
            serve_with_limit(
                Cursor::new(frames.join("\n") + "\n"),
                output,
                final_size - 1
            )
            .is_err()
        );
        let bytes = observer.0.lock().unwrap();
        let lines = String::from_utf8(bytes.clone()).unwrap();
        let messages = lines
            .lines()
            .map(|line| serde_json::from_str::<serde_json::Value>(line).unwrap())
            .collect::<Vec<_>>();
        assert_eq!(messages.len(), request.sessions.len() + 1);
        assert_eq!(messages.last().unwrap()["type"], "session");
    }
    #[test]
    fn source_io_error_after_report_suppresses_finished() {
        let (_, frames) = fixture_frames();
        let reader = Cursor::new(frames[..2].join("\n") + "\n").chain(FailedReader);
        let output = Collected::default();
        let observer = output.clone();
        assert!(
            serve(reader, output)
                .unwrap_err()
                .to_string()
                .contains("source failed")
        );
        let bytes = observer.0.lock().unwrap();
        let lines = String::from_utf8(bytes.clone()).unwrap();
        assert_eq!(lines.lines().count(), 2);
        assert!(!lines.contains("\"type\":\"finished\""));
    }
    #[test]
    fn input_boundary_is_inclusive_and_requires_newline() {
        let line = b"{\"type\":\"finish\",\"schema_version\":\"engine_session_stream.v1\",\"sequence\":1}\n";
        assert!(read_frame(&mut Cursor::new(line), line.len()).is_ok());
        assert!(read_frame(&mut Cursor::new(line), line.len() - 1).is_err());
        assert!(read_frame(&mut Cursor::new(&line[..line.len() - 1]), line.len()).is_err());
        assert!(read_frame(&mut Cursor::new(b"\xff\n"), 10).is_err());
    }
    #[test]
    fn serialization_boundary_never_writes_partial_frame() {
        let mut output = Vec::new();
        write_frame(&mut output, &"a", 4).unwrap();
        assert_eq!(output, b"\"a\"\n");
        output.clear();
        assert!(write_frame(&mut output, &"a", 3).is_err());
        assert!(output.is_empty());
    }
    #[test]
    fn duplicate_and_unknown_keys_are_rejected_without_value_conversion() {
        for line in [
            "{\"type\":\"finish\",\"type\":\"finish\",\"schema_version\":\"engine_session_stream.v1\",\"sequence\":1}\n",
            "{\"type\":\"finish\",\"schema_version\":\"engine_session_stream.v1\",\"sequence\":1,\"sequence\":1}\n",
            "{\"type\":\"finish\",\"schema_version\":\"engine_session_stream.v1\",\"sequence\":1,\"config\":null}\n",
            "{\"type\":\"finish\",\"schema_version\":\"engine_session_stream.v1\",\"sequence\":NaN}\n",
        ] {
            assert!(read_frame(&mut Cursor::new(line), 1024).is_err());
        }
    }
}
