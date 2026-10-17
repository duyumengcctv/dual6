//! PyO3 bindings for Dual6.
//!
//! These functions mirror the pure-Python reference API.  The Python package
//! layers this module over `dual6._ref`; missing functions fall back to Python.

use pyo3::buffer::{PyBuffer, ReadOnlyCell};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::cell::Cell;

fn map_error(err: dual6_core::Dual6Error) -> PyErr {
    PyValueError::new_err(err.to_string())
}

#[pyfunction]
fn encode_digit(bit: u8, trit: i8) -> PyResult<u8> {
    dual6_core::encode_digit(bit, trit).map_err(map_error)
}

#[pyfunction]
fn decode_digit(digit: u8) -> PyResult<(u8, i8)> {
    dual6_core::decode_digit(digit).map_err(map_error)
}

#[pyfunction]
fn mux(bits: Vec<u8>, trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::mux(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn demux(symbols: Vec<u8>) -> PyResult<(Vec<u8>, Vec<i8>)> {
    dual6_core::demux(&symbols).map_err(map_error)
}

#[pyfunction]
fn pack_digits(digits: Vec<u8>) -> PyResult<u128> {
    dual6_core::pack_digits(&digits).map_err(map_error)
}

#[pyfunction]
fn unpack_digits(value: u128, width: usize) -> PyResult<Vec<u8>> {
    dual6_core::unpack_digits(value, width).map_err(map_error)
}

#[pyfunction]
fn max_interleaved(width: usize) -> PyResult<u128> {
    dual6_core::max_interleaved(width).map_err(map_error)
}

#[pyfunction]
fn fits_unsigned_word(width: usize, word_bits: u32) -> bool {
    dual6_core::fits_unsigned_word(width, word_bits)
}

#[pyfunction]
fn pack_bits_bytes(bits: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_bits_bytes(&bits).map_err(map_error)
}

#[pyfunction]
fn unpack_bits_bytes(data: Vec<u8>, width: usize) -> PyResult<Vec<u8>> {
    dual6_core::unpack_bits_bytes(&data, width).map_err(map_error)
}

#[pyfunction]
fn pack_trits_bytes(trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_trits_bytes(&trits).map_err(map_error)
}

#[pyfunction]
fn unpack_trits_bytes(data: Vec<u8>, width: usize) -> PyResult<Vec<i8>> {
    dual6_core::unpack_trits_bytes(&data, width).map_err(map_error)
}

#[pyfunction]
fn pack_block64_many(symbols: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block64_many(&symbols).map_err(map_error)
}

#[pyfunction]
fn unpack_block64_many(data: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::unpack_block64_many(&data).map_err(map_error)
}

fn write_cells(cells: &[Cell<u8>], offset: usize, bytes: &[u8]) -> PyResult<usize> {
    let end = offset
        .checked_add(bytes.len())
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: offset overflow"))?;
    if end > cells.len() {
        return Err(PyValueError::new_err("InvalidLayout: buffer too small"));
    }
    for (i, &byte) in bytes.iter().enumerate() {
        cells[offset + i].set(byte);
    }
    Ok(bytes.len())
}

#[pyfunction]
#[pyo3(signature = (symbols, buffer, offset=0))]
fn pack_block64_many_into(
    py: Python<'_>,
    symbols: &[u8],
    buffer: &Bound<'_, PyAny>,
    offset: usize,
) -> PyResult<usize> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_mut_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be writable and C-contiguous"))?;
    let packed = dual6_core::pack_block64_many(symbols).map_err(map_error)?;
    write_cells(cells, offset, &packed)
}

#[pyfunction]
#[pyo3(signature = (data, buffer, offset=0))]
fn unpack_block64_many_into(
    py: Python<'_>,
    data: &[u8],
    buffer: &Bound<'_, PyAny>,
    offset: usize,
) -> PyResult<usize> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_mut_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be writable and C-contiguous"))?;
    let symbols = dual6_core::unpack_block64_many(data).map_err(map_error)?;
    write_cells(cells, offset, &symbols)
}

#[pyfunction]
fn pack_block64(symbols: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block64(&symbols).map_err(map_error)
}

#[pyfunction]
fn unpack_block64(data: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::unpack_block64(&data).map_err(map_error)
}

#[pyfunction]
fn pack_block128(symbols: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block128(&symbols).map_err(map_error)
}

#[pyfunction]
fn unpack_block128(data: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::unpack_block128(&data).map_err(map_error)
}

#[pyfunction]
fn pack_block40(symbols: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block40(&symbols).map_err(map_error)
}

#[pyfunction]
fn unpack_block40(data: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::unpack_block40(&data).map_err(map_error)
}

#[pyfunction]
fn pack_block64_dp(bits: Vec<u8>, trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block64_dp(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn unpack_block64_dp(data: Vec<u8>) -> PyResult<(Vec<u8>, Vec<i8>)> {
    dual6_core::unpack_block64_dp(&data).map_err(map_error)
}

#[pyfunction]
fn pack_block128_dp(bits: Vec<u8>, trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block128_dp(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn unpack_block128_dp(data: Vec<u8>) -> PyResult<(Vec<u8>, Vec<i8>)> {
    dual6_core::unpack_block128_dp(&data).map_err(map_error)
}

#[pyfunction]
fn pack_block40_dp(bits: Vec<u8>, trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_block40_dp(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn unpack_block40_dp(data: Vec<u8>) -> PyResult<(Vec<u8>, Vec<i8>)> {
    dual6_core::unpack_block40_dp(&data).map_err(map_error)
}

#[pyfunction]
fn pack_dual_plane(bits: Vec<u8>, trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_dual_plane(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn unpack_dual_plane(data: Vec<u8>) -> PyResult<(Vec<u8>, Vec<i8>)> {
    dual6_core::unpack_dual_plane(&data).map_err(map_error)
}

#[pyfunction]
fn pack_dual_plane_v1(bits: Vec<u8>, trits: Vec<i8>) -> PyResult<Vec<u8>> {
    dual6_core::pack_dual_plane_v1(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn unpack_dual_plane_v1(data: Vec<u8>) -> PyResult<(Vec<u8>, Vec<i8>)> {
    dual6_core::unpack_dual_plane_v1(&data).map_err(map_error)
}

#[pyfunction]
#[pyo3(signature = (bits, trits, dtype=0, block_symbols=0, flags=0, layout=None))]
fn pack_dual_plane_v2(
    bits: Vec<u8>,
    trits: Vec<i8>,
    dtype: u8,
    block_symbols: usize,
    flags: u16,
    layout: Option<u8>,
) -> PyResult<Vec<u8>> {
    dual6_core::pack_dual_plane_v2_layout(
        &bits,
        &trits,
        dtype,
        block_symbols,
        flags,
        layout.unwrap_or(0),
    )
    .map_err(map_error)
}

#[pyfunction]
fn unpack_dual_plane_v2(
    py: Python<'_>,
    data: Vec<u8>,
) -> PyResult<(Vec<u8>, Vec<i8>, Py<PyDict>)> {
    let (bits, trits, meta) = dual6_core::unpack_dual_plane_v2(&data).map_err(map_error)?;
    let dict = PyDict::new(py);
    dict.set_item("layout", meta.layout)?;
    dict.set_item("dtype", meta.dtype)?;
    dict.set_item("flags", meta.flags)?;
    dict.set_item("width", meta.width)?;
    dict.set_item("block_symbols", meta.block_symbols)?;
    dict.set_item("block_bytes", meta.block_bytes)?;
    dict.set_item("block_count", meta.block_count)?;
    dict.set_item("payload_len", meta.payload_len)?;
    dict.set_item("crc32", meta.crc32)?;
    Ok((bits, trits, dict.unbind()))
}

#[pyfunction]
fn frame_version(data: Vec<u8>) -> PyResult<u8> {
    dual6_core::frame_version(&data).map_err(map_error)
}

#[pyfunction]
fn unpack_frame_auto(
    py: Python<'_>,
    data: Vec<u8>,
) -> PyResult<(u8, Vec<u8>, Vec<i8>, Py<PyDict>)> {
    let (version, bits, trits, meta) = dual6_core::unpack_frame_auto(&data).map_err(map_error)?;
    let dict = PyDict::new(py);
    if let dual6_core::FrameMeta::V2(meta) = meta {
        dict.set_item("layout", meta.layout)?;
        dict.set_item("dtype", meta.dtype)?;
        dict.set_item("flags", meta.flags)?;
        dict.set_item("width", meta.width)?;
        dict.set_item("block_symbols", meta.block_symbols)?;
        dict.set_item("block_bytes", meta.block_bytes)?;
        dict.set_item("block_count", meta.block_count)?;
        dict.set_item("payload_len", meta.payload_len)?;
        dict.set_item("crc32", meta.crc32)?;
    }
    Ok((version, bits, trits, dict.unbind()))
}

fn pack_bits_cells(bits: &[u8], cells: &[Cell<u8>], offset: usize) -> PyResult<usize> {
    let length = (bits.len() + 7) / 8;
    if offset + length > cells.len() {
        return Err(PyValueError::new_err("InvalidLayout: buffer too small"));
    }
    for i in 0..length {
        cells[offset + i].set(0);
    }
    for (i, &bit) in bits.iter().enumerate() {
        if bit > 1 {
            return Err(PyValueError::new_err("InvalidBit: bit must be 0 or 1"));
        }
        if bit != 0 {
            let idx = offset + (i >> 3);
            cells[idx].set(cells[idx].get() | (1u8 << (i & 7)));
        }
    }
    Ok(length)
}

fn unpack_bits_cells(cells: &[ReadOnlyCell<u8>], width: usize, offset: usize) -> PyResult<Vec<u8>> {
    let length = (width + 7) / 8;
    if offset + length > cells.len() {
        return Err(PyValueError::new_err("InvalidLayout: buffer too small"));
    }
    let mut bits = Vec::with_capacity(width);
    for i in 0..width {
        bits.push((cells[offset + (i >> 3)].get() >> (i & 7)) & 1);
    }
    if width % 8 != 0 {
        let mask = (0xFFu8 << (width % 8)) & 0xFF;
        if cells[offset + length - 1].get() & mask != 0 {
            return Err(PyValueError::new_err("InvalidLayout: non-zero padding bits"));
        }
    }
    Ok(bits)
}

fn pack_trits_cells(trits: &[i8], cells: &[Cell<u8>], offset: usize) -> PyResult<usize> {
    let length = (trits.len() + 4) / 5;
    if offset + length > cells.len() {
        return Err(PyValueError::new_err("InvalidLayout: buffer too small"));
    }
    for i in 0..length {
        cells[offset + i].set(0);
    }
    for (group_index, group) in trits.chunks(5).enumerate() {
        let mut value: u16 = 0;
        for (j, &trit) in group.iter().enumerate() {
            if !(-1..=1).contains(&trit) {
                return Err(PyValueError::new_err("InvalidTrit: trit must be -1, 0 or 1"));
            }
            value += ((trit + 1) as u16) * 3u16.pow(j as u32);
        }
        cells[offset + group_index].set(value as u8);
    }
    Ok(length)
}

fn unpack_trits_cells(cells: &[ReadOnlyCell<u8>], width: usize, offset: usize) -> PyResult<Vec<i8>> {
    let length = (width + 4) / 5;
    if offset + length > cells.len() {
        return Err(PyValueError::new_err("InvalidLayout: buffer too small"));
    }
    let full_bytes = width / 5;
    let remainder = width % 5;
    let mut trits = Vec::with_capacity(width);
    for i in 0..length {
        let used = if i < full_bytes { 5 } else { remainder };
        let limit = 3u16.pow(used as u32);
        let byte = cells[offset + i].get() as u16;
        if byte >= limit {
            return Err(PyValueError::new_err("InvalidLayout: invalid trit byte"));
        }
        for j in 0..used {
            trits.push(((byte / 3u16.pow(j as u32)) % 3) as i8 - 1);
        }
    }
    Ok(trits)
}

#[pyfunction]
#[pyo3(signature = (bits, buffer, offset=0))]
fn pack_bits_into(
    py: Python<'_>,
    bits: Vec<u8>,
    buffer: &Bound<'_, PyAny>,
    offset: usize,
) -> PyResult<usize> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_mut_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be writable and C-contiguous"))?;
    pack_bits_cells(&bits, cells, offset)
}

#[pyfunction]
#[pyo3(signature = (buffer, width, offset=0))]
fn unpack_bits_from(
    py: Python<'_>,
    buffer: &Bound<'_, PyAny>,
    width: usize,
    offset: usize,
) -> PyResult<Vec<u8>> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be C-contiguous"))?;
    unpack_bits_cells(cells, width, offset)
}

#[pyfunction]
#[pyo3(signature = (trits, buffer, offset=0))]
fn pack_trits_into(
    py: Python<'_>,
    trits: Vec<i8>,
    buffer: &Bound<'_, PyAny>,
    offset: usize,
) -> PyResult<usize> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_mut_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be writable and C-contiguous"))?;
    pack_trits_cells(&trits, cells, offset)
}

#[pyfunction]
#[pyo3(signature = (buffer, width, offset=0))]
fn unpack_trits_from(
    py: Python<'_>,
    buffer: &Bound<'_, PyAny>,
    width: usize,
    offset: usize,
) -> PyResult<Vec<i8>> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be C-contiguous"))?;
    unpack_trits_cells(cells, width, offset)
}

#[pyfunction]
#[pyo3(signature = (bits, trits, buffer, offset=0))]
fn pack_dual_plane_into(
    py: Python<'_>,
    bits: Vec<u8>,
    trits: Vec<i8>,
    buffer: &Bound<'_, PyAny>,
    offset: usize,
) -> PyResult<usize> {
    if bits.len() != trits.len() {
        return Err(PyValueError::new_err("WidthMismatch: bits length != trits length"));
    }
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_mut_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be writable and C-contiguous"))?;
    let bit_len = pack_bits_cells(&bits, cells, offset)?;
    let trit_len = pack_trits_cells(&trits, cells, offset + bit_len)?;
    Ok(bit_len + trit_len)
}

#[pyfunction]
#[pyo3(signature = (buffer, width, offset=0))]
fn unpack_dual_plane_from(
    py: Python<'_>,
    buffer: &Bound<'_, PyAny>,
    width: usize,
    offset: usize,
) -> PyResult<(Vec<u8>, Vec<i8>)> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be C-contiguous"))?;
    let bit_len = (width + 7) / 8;
    let bits = unpack_bits_cells(cells, width, offset)?;
    let trits = unpack_trits_cells(cells, width, offset + bit_len)?;
    Ok((bits, trits))
}

#[pyfunction]
#[pyo3(signature = (trits, fill_bit=0))]
fn trits_to_symbols(trits: Vec<i8>, fill_bit: u8) -> PyResult<Vec<u8>> {
    if fill_bit > 1 {
        return Err(PyValueError::new_err("InvalidBit: fill_bit must be 0 or 1"));
    }
    let bits = vec![fill_bit; trits.len()];
    dual6_core::mux(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn symbols_to_trits(symbols: Vec<u8>) -> PyResult<Vec<i8>> {
    dual6_core::demux(&symbols).map(|(_, trits)| trits).map_err(map_error)
}

#[pyfunction]
#[pyo3(signature = (bits, fill_trit=0))]
fn bits_to_symbols(bits: Vec<u8>, fill_trit: i8) -> PyResult<Vec<u8>> {
    if !(-1..=1).contains(&fill_trit) {
        return Err(PyValueError::new_err("InvalidTrit: fill_trit must be -1, 0 or 1"));
    }
    let trits = vec![fill_trit; bits.len()];
    dual6_core::mux(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn symbols_to_bits(symbols: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::demux(&symbols).map(|(bits, _)| bits).map_err(map_error)
}

#[pyfunction]
#[pyo3(signature = (trits, fill_bit=0))]
fn trits_to_dual6_block64(trits: Vec<i8>, fill_bit: u8) -> PyResult<Vec<u8>> {
    if fill_bit > 1 {
        return Err(PyValueError::new_err("InvalidBit: fill_bit must be 0 or 1"));
    }
    if trits.len() != 24 {
        return Err(PyValueError::new_err("WidthMismatch: D6-64-DP requires 24 trits"));
    }
    let bits = vec![fill_bit; 24];
    dual6_core::pack_block64_dp(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn dual6_block64_to_trits(data: Vec<u8>) -> PyResult<Vec<i8>> {
    dual6_core::unpack_block64_dp(&data)
        .map(|(_, trits)| trits)
        .map_err(map_error)
}

#[pyfunction]
#[pyo3(signature = (bits, fill_trit=0))]
fn bits_to_dual6_block64(bits: Vec<u8>, fill_trit: i8) -> PyResult<Vec<u8>> {
    if !(-1..=1).contains(&fill_trit) {
        return Err(PyValueError::new_err("InvalidTrit: fill_trit must be -1, 0 or 1"));
    }
    if bits.len() != 24 {
        return Err(PyValueError::new_err("WidthMismatch: D6-64-DP requires 24 bits"));
    }
    let trits = vec![fill_trit; 24];
    dual6_core::pack_block64_dp(&bits, &trits).map_err(map_error)
}

#[pyfunction]
fn dual6_block64_to_bits(data: Vec<u8>) -> PyResult<Vec<u8>> {
    dual6_core::unpack_block64_dp(&data)
        .map(|(bits, _)| bits)
        .map_err(map_error)
}

fn cells_u16(cells: &[ReadOnlyCell<u8>], offset: usize) -> u16 {
    u16::from(cells[offset].get()) | (u16::from(cells[offset + 1].get()) << 8)
}

fn cells_u32(cells: &[ReadOnlyCell<u8>], offset: usize) -> u32 {
    u32::from(cells[offset].get())
        | (u32::from(cells[offset + 1].get()) << 8)
        | (u32::from(cells[offset + 2].get()) << 16)
        | (u32::from(cells[offset + 3].get()) << 24)
}

fn crc32_cells(cells: &[ReadOnlyCell<u8>], crc_range: (usize, usize)) -> u32 {
    let mut crc: u32 = 0xFFFF_FFFF;
    for i in 0..cells.len() {
        let byte = if i >= crc_range.0 && i < crc_range.1 {
            0
        } else {
            cells[i].get()
        };
        crc ^= u32::from(byte);
        for _ in 0..8 {
            if crc & 1 != 0 {
                crc = (crc >> 1) ^ 0xEDB8_8320;
            } else {
                crc >>= 1;
            }
        }
    }
    !crc
}

fn unpack_frame_auto_cells(
    py: Python<'_>,
    cells: &[ReadOnlyCell<u8>],
) -> PyResult<(u8, Vec<u8>, Vec<i8>, Py<PyDict>)> {
    if cells.len() < 4 {
        return Err(PyValueError::new_err("InvalidLayout: frame shorter than magic"));
    }
    let magic = [
        cells[0].get(),
        cells[1].get(),
        cells[2].get(),
        cells[3].get(),
    ];
    let dict = PyDict::new(py);
    if magic == *b"D6P0" {
        if cells.len() < 17 {
            return Err(PyValueError::new_err("InvalidLayout: frame shorter than header"));
        }
        let version = cells[4].get();
        if version != 1 {
            return Err(PyValueError::new_err("UnsupportedVersion: unsupported version"));
        }
        let width = cells_u32(cells, 5) as usize;
        let bit_len = cells_u32(cells, 9) as usize;
        let trit_len = cells_u32(cells, 13) as usize;
        if bit_len != (width + 7) / 8 || trit_len != (width + 4) / 5 {
            return Err(PyValueError::new_err("InvalidLayout: length fields mismatch"));
        }
        if cells.len() != 17 + bit_len + trit_len {
            return Err(PyValueError::new_err("InvalidLayout: frame length mismatch"));
        }
        let bits = unpack_bits_cells(cells, width, 17)?;
        let trits = unpack_trits_cells(cells, width, 17 + bit_len)?;
        return Ok((0, bits, trits, dict.unbind()));
    }
    if magic == *b"D6P1" {
        if cells.len() < 20 {
            return Err(PyValueError::new_err("InvalidLayout: frame shorter than D6P1 header"));
        }
        let version = cells[4].get();
        if version != 1 {
            return Err(PyValueError::new_err("UnsupportedVersion: unsupported version"));
        }
        if cells[5].get() != 0 {
            return Err(PyValueError::new_err("InvalidLayout: unsupported layout"));
        }
        if cells_u16(cells, 6) != 0 {
            return Err(PyValueError::new_err("InvalidLayout: reserved must be 0"));
        }
        let width = cells_u32(cells, 8) as usize;
        let payload_len = cells_u32(cells, 12) as usize;
        let stored_crc = cells_u32(cells, 16);
        let expected_payload_len = (width + 7) / 8 + (width + 4) / 5;
        if payload_len != expected_payload_len {
            return Err(PyValueError::new_err("InvalidLayout: payload length mismatch"));
        }
        if cells.len() != 20 + payload_len {
            return Err(PyValueError::new_err("InvalidLayout: frame length mismatch"));
        }
        let calculated_crc = crc32_cells(cells, (16, 20));
        if calculated_crc != stored_crc {
            return Err(PyValueError::new_err("CrcMismatch: CRC32 mismatch"));
        }
        let bit_len = (width + 7) / 8;
        let bits = unpack_bits_cells(cells, width, 20)?;
        let trits = unpack_trits_cells(cells, width, 20 + bit_len)?;
        return Ok((1, bits, trits, dict.unbind()));
    }
    if magic == *b"D6P2" {
        if cells.len() < 33 {
            return Err(PyValueError::new_err("InvalidLayout: frame shorter than D6P2 header"));
        }
        let version = cells[4].get();
        if version != 1 {
            return Err(PyValueError::new_err("UnsupportedVersion: unsupported version"));
        }
        if cells[5].get() != 0 {
            return Err(PyValueError::new_err("InvalidLayout: unsupported layout"));
        }
        let dtype = cells[6].get();
        if dtype > 3 {
            return Err(PyValueError::new_err("InvalidLayout: unsupported dtype"));
        }
        let flags = cells_u16(cells, 7);
        let width = cells_u32(cells, 9) as usize;
        let block_symbols = cells_u32(cells, 13) as usize;
        let block_bytes = cells_u32(cells, 17) as usize;
        let block_count = cells_u32(cells, 21) as usize;
        let payload_len = cells_u32(cells, 25) as usize;
        let stored_crc = cells_u32(cells, 29);
        let expected_payload_len = if block_symbols == 0 {
            if block_bytes != 0 || block_count != 0 {
                return Err(PyValueError::new_err("InvalidLayout: block metadata must be zero"));
            }
            (width + 7) / 8 + (width + 4) / 5
        } else {
            let expected_block_bytes = (block_symbols + 7) / 8 + (block_symbols + 4) / 5;
            if block_bytes != expected_block_bytes {
                return Err(PyValueError::new_err("InvalidLayout: block_bytes mismatch"));
            }
            if block_count * block_symbols != width {
                return Err(PyValueError::new_err("InvalidLayout: block_count mismatch"));
            }
            block_count * block_bytes
        };
        if payload_len != expected_payload_len {
            return Err(PyValueError::new_err("InvalidLayout: payload length mismatch"));
        }
        if cells.len() != 33 + payload_len {
            return Err(PyValueError::new_err("InvalidLayout: frame length mismatch"));
        }
        let calculated_crc = crc32_cells(cells, (29, 33));
        if calculated_crc != stored_crc {
            return Err(PyValueError::new_err("CrcMismatch: CRC32 mismatch"));
        }
        let mut bits = Vec::with_capacity(width);
        let mut trits = Vec::with_capacity(width);
        if block_symbols == 0 {
            let bit_len = (width + 7) / 8;
            bits.extend(unpack_bits_cells(cells, width, 33)?);
            trits.extend(unpack_trits_cells(cells, width, 33 + bit_len)?);
        } else {
            let bit_len = (block_symbols + 7) / 8;
            for i in 0..block_count {
                let base = 33 + i * block_bytes;
                bits.extend(unpack_bits_cells(cells, block_symbols, base)?);
                trits.extend(unpack_trits_cells(cells, block_symbols, base + bit_len)?);
            }
        }
        dict.set_item("layout", 0u8)?;
        dict.set_item("dtype", dtype)?;
        dict.set_item("flags", flags)?;
        dict.set_item("width", width)?;
        dict.set_item("block_symbols", block_symbols)?;
        dict.set_item("block_bytes", block_bytes)?;
        dict.set_item("block_count", block_count)?;
        dict.set_item("payload_len", payload_len)?;
        dict.set_item("crc32", stored_crc)?;
        return Ok((2, bits, trits, dict.unbind()));
    }
    Err(PyValueError::new_err("InvalidLayout: unknown frame magic"))
}

#[pyfunction]
fn unpack_frame_auto_buffer(
    py: Python<'_>,
    buffer: &Bound<'_, PyAny>,
) -> PyResult<(u8, Vec<u8>, Vec<i8>, Py<PyDict>)> {
    let buf = PyBuffer::<u8>::get(buffer)?;
    let cells = buf
        .as_slice(py)
        .ok_or_else(|| PyValueError::new_err("InvalidLayout: buffer must be C-contiguous"))?;
    unpack_frame_auto_cells(py, cells)
}

#[pyfunction]
fn bits_bytes_len(width: usize) -> usize {
    dual6_core::bits_bytes_len(width)
}

#[pyfunction]
fn trits_bytes_len(width: usize) -> usize {
    dual6_core::trits_bytes_len(width)
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_digit, m)?)?;
    m.add_function(wrap_pyfunction!(decode_digit, m)?)?;
    m.add_function(wrap_pyfunction!(mux, m)?)?;
    m.add_function(wrap_pyfunction!(demux, m)?)?;
    m.add_function(wrap_pyfunction!(pack_digits, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_digits, m)?)?;
    m.add_function(wrap_pyfunction!(max_interleaved, m)?)?;
    m.add_function(wrap_pyfunction!(fits_unsigned_word, m)?)?;
    m.add_function(wrap_pyfunction!(pack_bits_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_bits_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(pack_trits_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_trits_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block64_many, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block64_many, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block64_many_into, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block64_many_into, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block64, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block64, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block128, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block128, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block40, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block40, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block64_dp, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block64_dp, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block128_dp, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block128_dp, m)?)?;
    m.add_function(wrap_pyfunction!(pack_block40_dp, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block40_dp, m)?)?;
    m.add_function(wrap_pyfunction!(pack_dual_plane, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_dual_plane, m)?)?;
    m.add_function(wrap_pyfunction!(pack_dual_plane_v1, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_dual_plane_v1, m)?)?;
    m.add_function(wrap_pyfunction!(pack_dual_plane_v2, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_dual_plane_v2, m)?)?;
    m.add_function(wrap_pyfunction!(frame_version, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_frame_auto, m)?)?;
    m.add_function(wrap_pyfunction!(pack_bits_into, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_bits_from, m)?)?;
    m.add_function(wrap_pyfunction!(pack_trits_into, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_trits_from, m)?)?;
    m.add_function(wrap_pyfunction!(pack_dual_plane_into, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_dual_plane_from, m)?)?;
    m.add_function(wrap_pyfunction!(trits_to_symbols, m)?)?;
    m.add_function(wrap_pyfunction!(symbols_to_trits, m)?)?;
    m.add_function(wrap_pyfunction!(bits_to_symbols, m)?)?;
    m.add_function(wrap_pyfunction!(symbols_to_bits, m)?)?;
    m.add_function(wrap_pyfunction!(trits_to_dual6_block64, m)?)?;
    m.add_function(wrap_pyfunction!(dual6_block64_to_trits, m)?)?;
    m.add_function(wrap_pyfunction!(bits_to_dual6_block64, m)?)?;
    m.add_function(wrap_pyfunction!(dual6_block64_to_bits, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_frame_auto_buffer, m)?)?;
    m.add_function(wrap_pyfunction!(bits_bytes_len, m)?)?;
    m.add_function(wrap_pyfunction!(trits_bytes_len, m)?)?;
    Ok(())
}
