use crate::error::{Dual6Error, Dual6Result, ErrorCode};
use crate::symbol::{decode_digit, encode_digit};

pub fn mux(bits: &[u8], trits: &[i8]) -> Dual6Result<Vec<u8>> {
    if bits.len() != trits.len() {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!("bits length {} != trits length {}", bits.len(), trits.len()),
        ));
    }
    bits.iter()
        .copied()
        .zip(trits.iter().copied())
        .map(|(b, t)| encode_digit(b, t))
        .collect()
}

pub fn demux(symbols: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    let mut bits = Vec::with_capacity(symbols.len());
    let mut trits = Vec::with_capacity(symbols.len());
    for &d in symbols {
        let (b, t) = decode_digit(d)?;
        bits.push(b);
        trits.push(t);
    }
    Ok((bits, trits))
}
