use crate::dual_plane::{pack_bits_bytes, pack_trits_bytes, unpack_bits_bytes, unpack_trits_bytes};
use crate::error::{Dual6Error, Dual6Result, ErrorCode};
use crate::interleaved::{pack_digits, unpack_digits};
use crate::symbol::DIGIT_BASE;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BlockLayout {
    pub name: &'static str,
    pub symbols: usize,
    pub byte_length: usize,
    pub bit_length: usize,
}

impl BlockLayout {
    pub fn max_value(&self) -> u128 {
        (DIGIT_BASE as u128).pow(self.symbols as u32) - 1
    }
}

pub const BLOCK64: BlockLayout = BlockLayout {
    name: "D6-64",
    symbols: 24,
    byte_length: 8,
    bit_length: 64,
};

pub const BLOCK128: BlockLayout = BlockLayout {
    name: "D6-128",
    symbols: 48,
    byte_length: 16,
    bit_length: 128,
};

pub const BLOCK40: BlockLayout = BlockLayout {
    name: "D6-40",
    symbols: 40,
    byte_length: 13,
    bit_length: 104,
};

fn u128_from_le_slice(data: &[u8]) -> u128 {
    let mut buf = [0u8; 16];
    buf[..data.len()].copy_from_slice(data);
    u128::from_le_bytes(buf)
}

pub fn pack_block(symbols: &[u8], layout: &BlockLayout) -> Dual6Result<Vec<u8>> {
    if symbols.len() != layout.symbols {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!(
                "{} requires {} symbols, got {}",
                layout.name,
                layout.symbols,
                symbols.len()
            ),
        ));
    }
    let value = pack_digits(symbols)?;
    if value > layout.max_value() {
        return Err(Dual6Error::new(
            ErrorCode::InvalidPacking,
            format!("value {value} exceeds {} maximum {}", layout.name, layout.max_value()),
        ));
    }
    let bytes = value.to_le_bytes();
    Ok(bytes[..layout.byte_length].to_vec())
}

pub fn unpack_block(data: &[u8], layout: &BlockLayout) -> Dual6Result<Vec<u8>> {
    if data.len() != layout.byte_length {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "{} requires {} bytes, got {}",
                layout.name,
                layout.byte_length,
                data.len()
            ),
        ));
    }
    let value = u128_from_le_slice(data);
    if value > layout.max_value() {
        return Err(Dual6Error::new(
            ErrorCode::InvalidPacking,
            format!("value {value} exceeds {} maximum {}", layout.name, layout.max_value()),
        ));
    }
    unpack_digits(value, layout.symbols)
}

pub fn pack_block64(symbols: &[u8]) -> Dual6Result<Vec<u8>> {
    pack_block(symbols, &BLOCK64)
}

pub fn unpack_block64(data: &[u8]) -> Dual6Result<Vec<u8>> {
    unpack_block(data, &BLOCK64)
}

/// Pack a flat stream of symbols into many D6-64 blocks in one call.
///
/// This amortises the FFI / Python boundary over the whole batch.
pub fn pack_block64_many(symbols: &[u8]) -> Dual6Result<Vec<u8>> {
    if symbols.len() % BLOCK64.symbols != 0 {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!(
                "D6-64 batch requires a multiple of {} symbols, got {}",
                BLOCK64.symbols,
                symbols.len()
            ),
        ));
    }
    let mut out = Vec::with_capacity(symbols.len() / BLOCK64.symbols * BLOCK64.byte_length);
    for chunk in symbols.chunks_exact(BLOCK64.symbols) {
        out.extend_from_slice(&pack_block64(chunk)?);
    }
    Ok(out)
}

/// Unpack many D6-64 blocks into one flat symbol stream in one call.
pub fn unpack_block64_many(data: &[u8]) -> Dual6Result<Vec<u8>> {
    if data.len() % BLOCK64.byte_length != 0 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "D6-64 batch requires a multiple of {} bytes, got {}",
                BLOCK64.byte_length,
                data.len()
            ),
        ));
    }
    let mut out = Vec::with_capacity(data.len() / BLOCK64.byte_length * BLOCK64.symbols);
    for chunk in data.chunks_exact(BLOCK64.byte_length) {
        out.extend_from_slice(&unpack_block64(chunk)?);
    }
    Ok(out)
}

pub fn pack_block128(symbols: &[u8]) -> Dual6Result<Vec<u8>> {
    pack_block(symbols, &BLOCK128)
}

pub fn unpack_block128(data: &[u8]) -> Dual6Result<Vec<u8>> {
    unpack_block(data, &BLOCK128)
}

pub fn pack_block40(symbols: &[u8]) -> Dual6Result<Vec<u8>> {
    pack_block(symbols, &BLOCK40)
}

pub fn unpack_block40(data: &[u8]) -> Dual6Result<Vec<u8>> {
    unpack_block(data, &BLOCK40)
}

// ---------------------------------------------------------------------------
// Dual-plane fixed blocks
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DualPlaneBlockLayout {
    pub name: &'static str,
    pub symbols: usize,
    pub byte_length: usize,
    pub bit_bytes: usize,
    pub trit_bytes: usize,
    pub bit_length: usize,
}

pub const BLOCK64_DP: DualPlaneBlockLayout = DualPlaneBlockLayout {
    name: "D6-64-DP",
    symbols: 24,
    byte_length: 8,
    bit_bytes: 3,
    trit_bytes: 5,
    bit_length: 64,
};

pub const BLOCK128_DP: DualPlaneBlockLayout = DualPlaneBlockLayout {
    name: "D6-128-DP",
    symbols: 48,
    byte_length: 16,
    bit_bytes: 6,
    trit_bytes: 10,
    bit_length: 128,
};

pub const BLOCK40_DP: DualPlaneBlockLayout = DualPlaneBlockLayout {
    name: "D6-40-DP",
    symbols: 40,
    byte_length: 13,
    bit_bytes: 5,
    trit_bytes: 8,
    bit_length: 104,
};

pub fn pack_block_dp(
    bits: &[u8],
    trits: &[i8],
    layout: &DualPlaneBlockLayout,
) -> Dual6Result<Vec<u8>> {
    if bits.len() != trits.len() || bits.len() != layout.symbols {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!(
                "{} requires {} bits and trits, got {} and {}",
                layout.name,
                layout.symbols,
                bits.len(),
                trits.len()
            ),
        ));
    }
    let bit_data = pack_bits_bytes(bits)?;
    let trit_data = pack_trits_bytes(trits)?;
    if bit_data.len() != layout.bit_bytes || trit_data.len() != layout.trit_bytes {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "{} internal length mismatch: bits {}/{}, trits {}/{}",
                layout.name,
                bit_data.len(),
                layout.bit_bytes,
                trit_data.len(),
                layout.trit_bytes
            ),
        ));
    }
    let mut out = Vec::with_capacity(layout.byte_length);
    out.extend_from_slice(&bit_data);
    out.extend_from_slice(&trit_data);
    Ok(out)
}

pub fn unpack_block_dp(
    data: &[u8],
    layout: &DualPlaneBlockLayout,
) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    if data.len() != layout.byte_length {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "{} requires {} bytes, got {}",
                layout.name,
                layout.byte_length,
                data.len()
            ),
        ));
    }
    let bit_data = &data[..layout.bit_bytes];
    let trit_data = &data[layout.bit_bytes..];
    let bits = unpack_bits_bytes(bit_data, layout.symbols)?;
    let trits = unpack_trits_bytes(trit_data, layout.symbols)?;
    Ok((bits, trits))
}

pub fn pack_block64_dp(bits: &[u8], trits: &[i8]) -> Dual6Result<Vec<u8>> {
    pack_block_dp(bits, trits, &BLOCK64_DP)
}

pub fn unpack_block64_dp(data: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    unpack_block_dp(data, &BLOCK64_DP)
}

pub fn pack_block128_dp(bits: &[u8], trits: &[i8]) -> Dual6Result<Vec<u8>> {
    pack_block_dp(bits, trits, &BLOCK128_DP)
}

pub fn unpack_block128_dp(data: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    unpack_block_dp(data, &BLOCK128_DP)
}

pub fn pack_block40_dp(bits: &[u8], trits: &[i8]) -> Dual6Result<Vec<u8>> {
    pack_block_dp(bits, trits, &BLOCK40_DP)
}

pub fn unpack_block40_dp(data: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    unpack_block_dp(data, &BLOCK40_DP)
}
