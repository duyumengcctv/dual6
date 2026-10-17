use crate::error::{Dual6Error, Dual6Result, ErrorCode};

pub const DIGIT_BASE: u8 = 6;
pub const DIGIT_COUNT: u8 = 6;

pub fn check_bit(bit: u8) -> Dual6Result<()> {
    if bit > 1 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidBit,
            format!("bit must be 0 or 1, got {bit}"),
        ));
    }
    Ok(())
}

pub fn check_trit(trit: i8) -> Dual6Result<()> {
    if !(-1..=1).contains(&trit) {
        return Err(Dual6Error::new(
            ErrorCode::InvalidTrit,
            format!("trit must be -1, 0 or 1, got {trit}"),
        ));
    }
    Ok(())
}

pub fn check_digit(digit: u8) -> Dual6Result<()> {
    if digit >= DIGIT_COUNT {
        return Err(Dual6Error::new(
            ErrorCode::InvalidDigit,
            format!("digit must be 0..5, got {digit}"),
        ));
    }
    Ok(())
}

/// Mux one bit and one balanced trit into a 6-state symbol.
pub fn encode_digit(bit: u8, trit: i8) -> Dual6Result<u8> {
    check_bit(bit)?;
    check_trit(trit)?;
    Ok(3 * bit + (trit + 1) as u8)
}

/// Demux one 6-state symbol into `(bit, trit)`.
pub fn decode_digit(digit: u8) -> Dual6Result<(u8, i8)> {
    check_digit(digit)?;
    Ok((digit / 3, (digit % 3) as i8 - 1))
}
