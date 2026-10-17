use crate::error::{Dual6Error, Dual6Result, ErrorCode};
use crate::symbol::{check_bit, check_trit};

pub const TRIT_PER_BYTE: usize = 5;

pub fn pack_bits_bytes(bits: &[u8]) -> Dual6Result<Vec<u8>> {
    let mut out = vec![0u8; (bits.len() + 7) / 8];
    for (i, &b) in bits.iter().enumerate() {
        check_bit(b)?;
        if b != 0 {
            out[i >> 3] |= 1u8 << (i & 7);
        }
    }
    Ok(out)
}

pub fn unpack_bits_bytes(data: &[u8], width: usize) -> Dual6Result<Vec<u8>> {
    let expected = (width + 7) / 8;
    if data.len() != expected {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("bit plane length {} != expected {}", data.len(), expected),
        ));
    }
    let mut bits = Vec::with_capacity(width);
    for i in 0..width {
        bits.push((data[i >> 3] >> (i & 7)) & 1);
    }
    if width % 8 != 0 {
        let mask = 0xFFu8 << (width % 8);
        if data[data.len() - 1] & mask != 0 {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                "non-zero padding bits in bit plane",
            ));
        }
    }
    Ok(bits)
}

fn encode_trit_group(group: &[i8]) -> Dual6Result<u8> {
    let mut value: u16 = 0;
    for (j, &t) in group.iter().enumerate() {
        check_trit(t)?;
        value += ((t + 1) as u16) * 3u16.pow(j as u32);
    }
    if value >= 256 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("trit group does not fit in byte: {value}"),
        ));
    }
    Ok(value as u8)
}

pub fn pack_trits_bytes(trits: &[i8]) -> Dual6Result<Vec<u8>> {
    let mut out = Vec::with_capacity((trits.len() + TRIT_PER_BYTE - 1) / TRIT_PER_BYTE);
    for group in trits.chunks(TRIT_PER_BYTE) {
        out.push(encode_trit_group(group)?);
    }
    Ok(out)
}

pub fn unpack_trits_bytes(data: &[u8], width: usize) -> Dual6Result<Vec<i8>> {
    let expected = (width + TRIT_PER_BYTE - 1) / TRIT_PER_BYTE;
    if data.len() != expected {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("trit plane length {} != expected {}", data.len(), expected),
        ));
    }
    let full_bytes = width / TRIT_PER_BYTE;
    let remainder = width % TRIT_PER_BYTE;
    let mut trits = Vec::with_capacity(width);
    for (i, &byte) in data.iter().enumerate() {
        let used = if i < full_bytes { TRIT_PER_BYTE } else { remainder };
        let limit = 3u16.pow(used as u32);
        if byte as u16 >= limit {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                format!("invalid trit byte {byte} for {used} used trits (limit {limit})"),
            ));
        }
        for j in 0..used {
            let digit = (byte as u16 / 3u16.pow(j as u32)) % 3;
            trits.push(digit as i8 - 1);
        }
    }
    Ok(trits)
}

pub fn bits_bytes_len(width: usize) -> usize {
    (width + 7) / 8
}

pub fn trits_bytes_len(width: usize) -> usize {
    (width + 4) / 5
}
