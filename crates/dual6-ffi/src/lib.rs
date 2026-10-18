//! C ABI for the Dual6 storage container.
//!
//! Status codes (negative return values):
//!
//! ```text
//! DUAL6_ERR_INVALID_ARG      -1
//! DUAL6_ERR_WIDTH_MISMATCH   -2
//! DUAL6_ERR_INVALID_LAYOUT   -3
//! DUAL6_ERR_BUFFER_TOO_SMALL -4
//! ```
//!
//! `dual6_encode_digit` returns 0..5 on success, or a negative status.
//! Batch functions return the number of **bytes written** on success
//! (pack) or the number of **symbols written** (unpack).

use std::ptr;
use std::slice;

use dual6_core::ErrorCode;

pub const DUAL6_ERR_INVALID_ARG: i32 = -1;
pub const DUAL6_ERR_WIDTH_MISMATCH: i32 = -2;
pub const DUAL6_ERR_INVALID_LAYOUT: i32 = -3;
pub const DUAL6_ERR_BUFFER_TOO_SMALL: i32 = -4;

fn status_for(code: ErrorCode) -> i32 {
    match code {
        ErrorCode::WidthMismatch => DUAL6_ERR_WIDTH_MISMATCH,
        ErrorCode::InvalidLayout => DUAL6_ERR_INVALID_LAYOUT,
        _ => DUAL6_ERR_INVALID_ARG,
    }
}

/// Build a slice from a raw pointer, allowing (null, 0) for an empty input.
unsafe fn input_slice<'a>(ptr: *const u8, len: usize) -> Option<&'a [u8]> {
    if len == 0 {
        Some(&[])
    } else if ptr.is_null() {
        None
    } else {
        Some(slice::from_raw_parts(ptr, len))
    }
}

fn copy_out(bytes: &[u8], out: *mut u8, capacity: usize) -> i32 {
    if bytes.len() > capacity {
        return DUAL6_ERR_BUFFER_TOO_SMALL;
    }
    // The C ABI reports the count as i32; refuse inputs larger than that
    // instead of silently wrapping the return value.
    if bytes.len() > i32::MAX as usize {
        return DUAL6_ERR_INVALID_ARG;
    }
    if !bytes.is_empty() {
        if out.is_null() {
            return DUAL6_ERR_INVALID_ARG;
        }
        // SAFETY: caller guarantees `out` has `capacity` writable bytes and
        // `bytes.len() <= capacity` was checked above.
        unsafe { ptr::copy_nonoverlapping(bytes.as_ptr(), out, bytes.len()) };
    }
    bytes.len() as i32
}

#[no_mangle]
pub extern "C" fn dual6_encode_digit(bit: u8, trit: i8) -> i32 {
    match dual6_core::encode_digit(bit, trit) {
        Ok(d) => d as i32,
        Err(_) => DUAL6_ERR_INVALID_ARG,
    }
}

#[no_mangle]
pub extern "C" fn dual6_decode_digit(digit: u8, out_bit: *mut u8, out_trit: *mut i8) -> i32 {
    if out_bit.is_null() || out_trit.is_null() {
        return DUAL6_ERR_INVALID_ARG;
    }
    match dual6_core::decode_digit(digit) {
        Ok((b, t)) => {
            unsafe {
                ptr::write(out_bit, b);
                ptr::write(out_trit, t);
            }
            0
        }
        Err(_) => DUAL6_ERR_INVALID_ARG,
    }
}

/// Pack `n_symbols / 24` D6-64 blocks from a flat symbol stream.
///
/// Returns the number of bytes written (`8 * n_symbols / 24`) or a negative status.
#[no_mangle]
pub unsafe extern "C" fn dual6_pack_block64_many(
    symbols: *const u8,
    n_symbols: usize,
    out: *mut u8,
    out_capacity: usize,
) -> i32 {
    let Some(input) = input_slice(symbols, n_symbols) else {
        return DUAL6_ERR_INVALID_ARG;
    };
    match dual6_core::pack_block64_many(input) {
        Ok(bytes) => copy_out(&bytes, out, out_capacity),
        Err(err) => status_for(err.code),
    }
}

/// Unpack many D6-64 blocks into one flat symbol stream.
///
/// Returns the number of symbols written (`24 * n_bytes / 8`) or a negative status.
#[no_mangle]
pub unsafe extern "C" fn dual6_unpack_block64_many(
    data: *const u8,
    n_bytes: usize,
    out: *mut u8,
    out_capacity: usize,
) -> i32 {
    let Some(input) = input_slice(data, n_bytes) else {
        return DUAL6_ERR_INVALID_ARG;
    };
    match dual6_core::unpack_block64_many(input) {
        Ok(symbols) => copy_out(&symbols, out, out_capacity),
        Err(err) => status_for(err.code),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_symbols(blocks: usize) -> Vec<u8> {
        (0..blocks * 24).map(|i| (i % 6) as u8).collect()
    }

    #[test]
    fn batch_roundtrip() {
        let input = sample_symbols(4);
        let mut packed = vec![0u8; input.len() / 3];
        let written = unsafe {
            dual6_pack_block64_many(
                input.as_ptr(),
                input.len(),
                packed.as_mut_ptr(),
                packed.len(),
            )
        };
        assert_eq!(written, (input.len() / 3) as i32);

        let mut out = vec![0u8; input.len()];
        let symbols_written = unsafe {
            dual6_unpack_block64_many(
                packed.as_ptr(),
                packed.len(),
                out.as_mut_ptr(),
                out.len(),
            )
        };
        assert_eq!(symbols_written, input.len() as i32);
        assert_eq!(out, input);
    }

    #[test]
    fn rejects_bad_symbol_count() {
        let input = vec![0u8; 23];
        let mut out = vec![0u8; 8];
        let status = unsafe {
            dual6_pack_block64_many(input.as_ptr(), input.len(), out.as_mut_ptr(), out.len())
        };
        assert_eq!(status, DUAL6_ERR_WIDTH_MISMATCH);
    }

    #[test]
    fn rejects_bad_byte_count() {
        let input = vec![0u8; 7];
        let mut out = vec![0u8; 24];
        let status = unsafe {
            dual6_unpack_block64_many(input.as_ptr(), input.len(), out.as_mut_ptr(), out.len())
        };
        assert_eq!(status, DUAL6_ERR_INVALID_LAYOUT);
    }

    #[test]
    fn rejects_small_output_buffer() {
        let input = sample_symbols(4);
        let mut out = vec![0u8; 8];
        let status = unsafe {
            dual6_pack_block64_many(input.as_ptr(), input.len(), out.as_mut_ptr(), out.len())
        };
        assert_eq!(status, DUAL6_ERR_BUFFER_TOO_SMALL);
    }

    #[test]
    fn empty_batch_is_ok() {
        let status = unsafe {
            dual6_pack_block64_many(ptr::null(), 0, ptr::null_mut(), 0)
        };
        assert_eq!(status, 0);
    }
}
