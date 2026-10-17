use crate::error::{Dual6Error, Dual6Result, ErrorCode};
use crate::symbol::{check_digit, DIGIT_BASE};

/// Maximum supported width for the `u128`-backed interleaved helpers.
///
/// 6^48 < 2^125, so all fixed blocks in this crate fit.  Wider containers
/// belong in a big-integer layer or in the Python reference implementation.
pub const MAX_INTERLEAVED_SYMBOLS: usize = 48;

pub fn pack_digits(digits: &[u8]) -> Dual6Result<u128> {
    if digits.len() > MAX_INTERLEAVED_SYMBOLS {
        return Err(Dual6Error::new(
            ErrorCode::InvalidPacking,
            format!(
                "width {} exceeds Rust u128 helper maximum {}",
                digits.len(),
                MAX_INTERLEAVED_SYMBOLS
            ),
        ));
    }
    let mut value: u128 = 0;
    for &d in digits.iter().rev() {
        check_digit(d)?;
        value = value * DIGIT_BASE as u128 + d as u128;
    }
    Ok(value)
}

pub fn unpack_digits(value: u128, width: usize) -> Dual6Result<Vec<u8>> {
    if width > MAX_INTERLEAVED_SYMBOLS {
        return Err(Dual6Error::new(
            ErrorCode::InvalidPacking,
            format!(
                "width {} exceeds Rust u128 helper maximum {}",
                width, MAX_INTERLEAVED_SYMBOLS
            ),
        ));
    }
    let limit = (DIGIT_BASE as u128).pow(width as u32);
    if value >= limit {
        return Err(Dual6Error::new(
            ErrorCode::InvalidPacking,
            format!("value {value} out of range [0, {limit}) for width {width}"),
        ));
    }
    let mut v = value;
    let mut out = Vec::with_capacity(width);
    for _ in 0..width {
        out.push((v % DIGIT_BASE as u128) as u8);
        v /= DIGIT_BASE as u128;
    }
    Ok(out)
}

pub fn max_interleaved(width: usize) -> Dual6Result<u128> {
    if width > MAX_INTERLEAVED_SYMBOLS {
        return Err(Dual6Error::new(
            ErrorCode::InvalidPacking,
            format!(
                "width {} exceeds Rust u128 helper maximum {}",
                width, MAX_INTERLEAVED_SYMBOLS
            ),
        ));
    }
    Ok((DIGIT_BASE as u128).pow(width as u32) - 1)
}

pub fn fits_unsigned_word(width: usize, word_bits: u32) -> bool {
    if width > MAX_INTERLEAVED_SYMBOLS {
        return false;
    }
    if word_bits >= 128 {
        return true;
    }
    (DIGIT_BASE as u128).pow(width as u32) <= (1u128 << word_bits)
}
