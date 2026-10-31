//! Pure owner-authoritative validation of exact request bytes, without simulation.
use crate::Request;
use anyhow::{Context, Result};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{fmt, io::Read};

pub const INPUT_LIMIT: usize = 1024 * 1024;

/// Malformed, oversized or semantically unsupported input (CLI exit status 2).
#[derive(Debug)]
pub struct ValidationRejected(String);
impl fmt::Display for ValidationRejected {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}
impl std::error::Error for ValidationRejected {}

#[derive(Debug, Serialize)]
pub struct ValidationReceipt {
    pub schema_version: &'static str,
    pub request_schema: &'static str,
    pub validator_version: u32,
    pub valid: bool,
    pub input_sha256: String,
}

/// Read at most limit-plus-one bytes, parse with the execution boundary's serde
/// type, and reuse its semantic validator. I/O failures remain infrastructure errors.
pub fn validate_reader(source: impl Read) -> Result<ValidationReceipt> {
    let mut bytes = Vec::new();
    source
        .take((INPUT_LIMIT + 1) as u64)
        .read_to_end(&mut bytes)
        .context("cannot read validation input")?;
    if bytes.len() > INPUT_LIMIT {
        return Err(ValidationRejected("request exceeds 1 MiB".into()).into());
    }
    let request: Request = serde_json::from_slice(&bytes)
        .map_err(|e| ValidationRejected(format!("invalid request JSON: {e}")))?;
    request
        .validate()
        .map_err(|e| ValidationRejected(format!("invalid request: {e:#}")))?;
    Ok(ValidationReceipt {
        schema_version: "engine_validation.v1",
        request_schema: "engine_request.v1",
        validator_version: 1,
        valid: true,
        input_sha256: format!("{:x}", Sha256::digest(&bytes)),
    })
}
