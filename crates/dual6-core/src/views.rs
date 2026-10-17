use crate::error::Dual6Result;
use crate::symbol::{check_digit, decode_digit};

/// Materialize the bit channel of a symbol sequence.
///
/// This is intentionally a copy-friendly helper.  A true zero-copy view can be
/// added later when the C ABI shape is fixed.
pub fn bits(symbols: &[u8]) -> Dual6Result<Vec<u8>> {
    let mut out = Vec::with_capacity(symbols.len());
    for &d in symbols {
        check_digit(d)?;
        out.push(d / 3);
    }
    Ok(out)
}

/// Materialize the balanced-trit channel of a symbol sequence.
pub fn trits(symbols: &[u8]) -> Dual6Result<Vec<i8>> {
    let mut out = Vec::with_capacity(symbols.len());
    for &d in symbols {
        let (_, t) = decode_digit(d)?;
        out.push(t);
    }
    Ok(out)
}
