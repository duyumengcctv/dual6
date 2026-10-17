use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    Ok,
    InvalidDigit,
    InvalidPacking,
    WidthMismatch,
    InvalidBit,
    InvalidTrit,
    InvalidLayout,
    UnsupportedVersion,
    CrcMismatch,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Dual6Error {
    pub code: ErrorCode,
    pub message: String,
}

impl Dual6Error {
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

impl fmt::Display for Dual6Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.message.is_empty() {
            write!(f, "{:?}", self.code)
        } else {
            write!(f, "{:?}: {}", self.code, self.message)
        }
    }
}

impl std::error::Error for Dual6Error {}

pub type Dual6Result<T> = Result<T, Dual6Error>;
