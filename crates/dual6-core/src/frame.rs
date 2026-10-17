use crate::dual_plane::{
    pack_bits_bytes, pack_trits_bytes, unpack_bits_bytes, unpack_trits_bytes, TRIT_PER_BYTE,
};
use crate::error::{Dual6Error, Dual6Result, ErrorCode};

pub const MAGIC: [u8; 4] = *b"D6P0";
pub const VERSION: u8 = 1;
const HEADER_SIZE: usize = 4 + 1 + 4 + 4 + 4;

fn read_u32_le(data: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]])
}

pub fn pack_dual_plane(bits: &[u8], trits: &[i8]) -> Dual6Result<Vec<u8>> {
    if bits.len() != trits.len() {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!("bits length {} != trits length {}", bits.len(), trits.len()),
        ));
    }
    let width = bits.len();
    let bit_data = pack_bits_bytes(bits)?;
    let trit_data = pack_trits_bytes(trits)?;
    let mut out = Vec::with_capacity(HEADER_SIZE + bit_data.len() + trit_data.len());
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.extend_from_slice(&(width as u32).to_le_bytes());
    out.extend_from_slice(&(bit_data.len() as u32).to_le_bytes());
    out.extend_from_slice(&(trit_data.len() as u32).to_le_bytes());
    out.extend_from_slice(&bit_data);
    out.extend_from_slice(&trit_data);
    Ok(out)
}

pub fn unpack_dual_plane(data: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    if data.len() < HEADER_SIZE {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "frame shorter than header",
        ));
    }
    if data[0..4] != MAGIC[..] {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "bad magic",
        ));
    }
    let version = data[4];
    if version != VERSION {
        return Err(Dual6Error::new(
            ErrorCode::UnsupportedVersion,
            format!("unsupported version {version}"),
        ));
    }
    let width = read_u32_le(data, 5) as usize;
    let bit_len = read_u32_le(data, 9) as usize;
    let trit_len = read_u32_le(data, 13) as usize;
    let expected_bit_len = (width + 7) / 8;
    let expected_trit_len = (width + TRIT_PER_BYTE - 1) / TRIT_PER_BYTE;
    if bit_len != expected_bit_len || trit_len != expected_trit_len {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "length fields bit={bit_len}/{expected_bit_len}, trit={trit_len}/{expected_trit_len}"
            ),
        ));
    }
    if data.len() != HEADER_SIZE + bit_len + trit_len {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "frame length {} != header + payload {}",
                data.len(),
                HEADER_SIZE + bit_len + trit_len
            ),
        ));
    }
    let bit_start = HEADER_SIZE;
    let trit_start = bit_start + bit_len;
    let bits = unpack_bits_bytes(&data[bit_start..trit_start], width)?;
    let trits = unpack_trits_bytes(&data[trit_start..trit_start + trit_len], width)?;
    Ok((bits, trits))
}

// ---------------------------------------------------------------------------
// D6P1
// ---------------------------------------------------------------------------

pub const MAGIC_V1: [u8; 4] = *b"D6P1";
pub const VERSION_V1: u8 = 1;
pub const LAYOUT_DUAL_PLANE: u8 = 0;
const HEADER_SIZE_V1: usize = 4 + 1 + 1 + 2 + 4 + 4 + 4;
const CRC_OFFSET_V1: usize = 16;

fn crc32(data: &[u8]) -> u32 {
    let mut crc: u32 = 0xFFFF_FFFF;
    for &byte in data {
        crc ^= byte as u32;
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

pub fn pack_dual_plane_v1(bits: &[u8], trits: &[i8]) -> Dual6Result<Vec<u8>> {
    if bits.len() != trits.len() {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!("bits length {} != trits length {}", bits.len(), trits.len()),
        ));
    }
    let width = bits.len();
    let bit_data = pack_bits_bytes(bits)?;
    let trit_data = pack_trits_bytes(trits)?;
    let mut payload = Vec::with_capacity(bit_data.len() + trit_data.len());
    payload.extend_from_slice(&bit_data);
    payload.extend_from_slice(&trit_data);

    let mut header = Vec::with_capacity(HEADER_SIZE_V1);
    header.extend_from_slice(&MAGIC_V1);
    header.push(VERSION_V1);
    header.push(LAYOUT_DUAL_PLANE);
    header.extend_from_slice(&0u16.to_le_bytes());
    header.extend_from_slice(&(width as u32).to_le_bytes());
    header.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    header.extend_from_slice(&0u32.to_le_bytes());

    let mut crc_input = Vec::with_capacity(header.len() + payload.len());
    crc_input.extend_from_slice(&header);
    crc_input.extend_from_slice(&payload);
    let crc = crc32(&crc_input);
    header[CRC_OFFSET_V1..CRC_OFFSET_V1 + 4].copy_from_slice(&crc.to_le_bytes());

    header.extend_from_slice(&payload);
    Ok(header)
}

pub fn unpack_dual_plane_v1(data: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>)> {
    if data.len() < HEADER_SIZE_V1 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "frame shorter than D6P1 header",
        ));
    }
    if data[0..4] != MAGIC_V1[..] {
        return Err(Dual6Error::new(ErrorCode::InvalidLayout, "bad D6P1 magic"));
    }
    let version = data[4];
    if version != VERSION_V1 {
        return Err(Dual6Error::new(
            ErrorCode::UnsupportedVersion,
            format!("unsupported version {version}"),
        ));
    }
    let layout = data[5];
    if layout != LAYOUT_DUAL_PLANE {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("unsupported layout {layout}"),
        ));
    }
    let reserved = u16::from_le_bytes([data[6], data[7]]);
    if reserved != 0 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("reserved field must be 0, got {reserved}"),
        ));
    }
    let width = read_u32_le(data, 8) as usize;
    let payload_len = read_u32_le(data, 12) as usize;
    let stored_crc = read_u32_le(data, 16);
    let expected_payload_len = (width + 7) / 8 + (width + TRIT_PER_BYTE - 1) / TRIT_PER_BYTE;
    if expected_payload_len != usize::MAX && payload_len != expected_payload_len {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("payload length {payload_len} != expected {expected_payload_len}"),
        ));
    }
    if data.len() != HEADER_SIZE_V1 + payload_len {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "frame length {} != header + payload {}",
                data.len(),
                HEADER_SIZE_V1 + payload_len
            ),
        ));
    }

    let mut crc_input = Vec::with_capacity(data.len());
    crc_input.extend_from_slice(&data[..HEADER_SIZE_V1]);
    crc_input[CRC_OFFSET_V1..CRC_OFFSET_V1 + 4].copy_from_slice(&0u32.to_le_bytes());
    crc_input.extend_from_slice(&data[HEADER_SIZE_V1..]);
    let calculated_crc = crc32(&crc_input);
    if calculated_crc != stored_crc {
        return Err(Dual6Error::new(
            ErrorCode::CrcMismatch,
            format!(
                "CRC32 mismatch: stored {stored_crc:#010x}, calculated {calculated_crc:#010x}"
            ),
        ));
    }

    let payload = &data[HEADER_SIZE_V1..];
    let bit_len = (width + 7) / 8;
    let bits = unpack_bits_bytes(&payload[..bit_len], width)?;
    let trits = unpack_trits_bytes(&payload[bit_len..], width)?;
    Ok((bits, trits))
}

// ---------------------------------------------------------------------------
// D6P2: dual-plane payload, dtype, optional fixed-size block metadata
// ---------------------------------------------------------------------------

pub const MAGIC_V2: [u8; 4] = *b"D6P2";
pub const VERSION_V2: u8 = 1;
pub const LAYOUT_DUAL_PLANE_V2: u8 = 0;
pub const DTYPE_RAW: u8 = 0;
pub const DTYPE_BINARY: u8 = 1;
pub const DTYPE_TERNARY: u8 = 2;
pub const DTYPE_MIXED: u8 = 3;

/// D6P2 layout 1: block-compacted bit plane ("sparse bit plane").
pub const LAYOUT_DUAL_PLANE_SPARSE: u8 = 1;

/// D6P2 flags bit 0: the bit plane is absent (trit-only payload).
pub const FLAG_OMIT_BIT_PLANE: u16 = 0x0001;

const HEADER_SIZE_V2: usize = 33;
const CRC_OFFSET_V2: usize = 29;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FrameMetaV2 {
    pub layout: u8,
    pub dtype: u8,
    pub flags: u16,
    pub width: usize,
    pub block_symbols: usize,
    pub block_bytes: usize,
    pub block_count: usize,
    pub payload_len: usize,
    pub crc32: u32,
}

fn dp_block_bytes(symbols: usize, omit_bit_plane: bool) -> usize {
    let trits = (symbols + 4) / 5;
    if omit_bit_plane {
        trits
    } else {
        (symbols + 7) / 8 + trits
    }
}

fn check_dtype_v2(dtype: u8) -> Dual6Result<()> {
    if matches!(dtype, DTYPE_RAW | DTYPE_BINARY | DTYPE_TERNARY | DTYPE_MIXED) {
        Ok(())
    } else {
        Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("unsupported dtype {dtype}"),
        ))
    }
}

pub fn pack_dual_plane_v2(
    bits: &[u8],
    trits: &[i8],
    dtype: u8,
    block_symbols: usize,
    flags: u16,
) -> Dual6Result<Vec<u8>> {
    pack_dual_plane_v2_layout(bits, trits, dtype, block_symbols, flags, LAYOUT_DUAL_PLANE_V2)
}

pub fn pack_dual_plane_v2_layout(
    bits: &[u8],
    trits: &[i8],
    dtype: u8,
    block_symbols: usize,
    flags: u16,
    layout: u8,
) -> Dual6Result<Vec<u8>> {
    if bits.len() != trits.len() {
        return Err(Dual6Error::new(
            ErrorCode::WidthMismatch,
            format!("bits length {} != trits length {}", bits.len(), trits.len()),
        ));
    }
    check_dtype_v2(dtype)?;
    if layout != LAYOUT_DUAL_PLANE_V2 && layout != LAYOUT_DUAL_PLANE_SPARSE {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("unsupported layout {layout}"),
        ));
    }
    if layout == LAYOUT_DUAL_PLANE_SPARSE && block_symbols == 0 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "sparse layout requires block_symbols > 0".to_string(),
        ));
    }
    let omit_bit_plane = flags & FLAG_OMIT_BIT_PLANE != 0;
    if omit_bit_plane && bits.iter().any(|&b| b != 0) {
        return Err(Dual6Error::new(
            ErrorCode::InvalidBit,
            "FLAG_OMIT_BIT_PLANE requires every bit to be 0".to_string(),
        ));
    }
    let width = bits.len();

    let (block_bytes, block_count, payload) = if block_symbols == 0 {
        let mut payload = Vec::new();
        if !omit_bit_plane {
            payload.extend_from_slice(&pack_bits_bytes(bits)?);
        }
        payload.extend_from_slice(&pack_trits_bytes(trits)?);
        (0usize, 0usize, payload)
    } else {
        if width % block_symbols != 0 {
            return Err(Dual6Error::new(
                ErrorCode::WidthMismatch,
                format!(
                    "width {width} is not a multiple of block_symbols {block_symbols}"
                ),
            ));
        }
        let block_count = width / block_symbols;
        if layout == LAYOUT_DUAL_PLANE_SPARSE {
            let block_bytes = (block_symbols + 4) / 5;
            let flag_bytes = (block_count + 7) / 8;
            let mut block_flags = vec![0u8; flag_bytes];
            let mut bitmaps: Vec<u8> = Vec::new();
            let mut trit_area: Vec<u8> = Vec::new();
            for i in 0..block_count {
                let start = i * block_symbols;
                let stop = start + block_symbols;
                let block_bits = &bits[start..stop];
                trit_area.extend_from_slice(&pack_trits_bytes(&trits[start..stop])?);
                if block_bits.iter().any(|&b| b != 0) {
                    block_flags[i / 8] |= 1 << (i % 8);
                    bitmaps.extend_from_slice(&pack_bits_bytes(block_bits)?);
                }
            }
            let mut payload = Vec::with_capacity(flag_bytes + bitmaps.len() + trit_area.len());
            payload.extend_from_slice(&block_flags);
            payload.extend_from_slice(&bitmaps);
            payload.extend_from_slice(&trit_area);
            (block_bytes, block_count, payload)
        } else {
            let block_bytes = dp_block_bytes(block_symbols, omit_bit_plane);
            let mut payload = Vec::with_capacity(block_count * block_bytes);
            for i in 0..block_count {
                let start = i * block_symbols;
                let stop = start + block_symbols;
                if !omit_bit_plane {
                    payload.extend_from_slice(&pack_bits_bytes(&bits[start..stop])?);
                }
                payload.extend_from_slice(&pack_trits_bytes(&trits[start..stop])?);
            }
            (block_bytes, block_count, payload)
        }
    };

    let mut header = Vec::with_capacity(HEADER_SIZE_V2);
    header.extend_from_slice(&MAGIC_V2);
    header.push(VERSION_V2);
    header.push(layout);
    header.push(dtype);
    header.extend_from_slice(&flags.to_le_bytes());
    header.extend_from_slice(&(width as u32).to_le_bytes());
    header.extend_from_slice(&(block_symbols as u32).to_le_bytes());
    header.extend_from_slice(&(block_bytes as u32).to_le_bytes());
    header.extend_from_slice(&(block_count as u32).to_le_bytes());
    header.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    header.extend_from_slice(&0u32.to_le_bytes());

    let mut crc_input = Vec::with_capacity(header.len() + payload.len());
    crc_input.extend_from_slice(&header);
    crc_input.extend_from_slice(&payload);
    let crc = crc32(&crc_input);
    header[CRC_OFFSET_V2..CRC_OFFSET_V2 + 4].copy_from_slice(&crc.to_le_bytes());
    header.extend_from_slice(&payload);
    Ok(header)
}

pub fn unpack_dual_plane_v2(data: &[u8]) -> Dual6Result<(Vec<u8>, Vec<i8>, FrameMetaV2)> {
    if data.len() < HEADER_SIZE_V2 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "frame shorter than D6P2 header",
        ));
    }
    if data[0..4] != MAGIC_V2[..] {
        return Err(Dual6Error::new(ErrorCode::InvalidLayout, "bad D6P2 magic"));
    }
    let version = data[4];
    if version != VERSION_V2 {
        return Err(Dual6Error::new(
            ErrorCode::UnsupportedVersion,
            format!("unsupported version {version}"),
        ));
    }
    let layout = data[5];
    if layout != LAYOUT_DUAL_PLANE_V2 && layout != LAYOUT_DUAL_PLANE_SPARSE {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("unsupported layout {layout}"),
        ));
    }
    let sparse = layout == LAYOUT_DUAL_PLANE_SPARSE;
    let dtype = data[6];
    check_dtype_v2(dtype)?;
    let flags = u16::from_le_bytes([data[7], data[8]]);
    let width = read_u32_le(data, 9) as usize;
    let block_symbols = read_u32_le(data, 13) as usize;
    let block_bytes = read_u32_le(data, 17) as usize;
    let block_count = read_u32_le(data, 21) as usize;
    let payload_len = read_u32_le(data, 25) as usize;
    let stored_crc = read_u32_le(data, 29);

    if layout != LAYOUT_DUAL_PLANE_V2 && layout != LAYOUT_DUAL_PLANE_SPARSE {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("unsupported layout {layout}"),
        ));
    }
    if layout == LAYOUT_DUAL_PLANE_SPARSE && block_symbols == 0 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "sparse layout requires block_symbols > 0".to_string(),
        ));
    }
    if sparse && block_symbols == 0 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "sparse layout requires block_symbols > 0".to_string(),
        ));
    }
    let omit_bit_plane = flags & FLAG_OMIT_BIT_PLANE != 0;
    let expected_payload_len = if block_symbols == 0 {
        if block_bytes != 0 || block_count != 0 {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                "block metadata must be zero when block_symbols=0",
            ));
        }
        dp_block_bytes(width, omit_bit_plane)
    } else if sparse {
        let expected_block_bytes = (block_symbols + 4) / 5;
        if block_bytes != expected_block_bytes {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                format!("block_bytes {block_bytes} != expected trit bytes {expected_block_bytes}"),
            ));
        }
        if block_count * block_symbols != width {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                format!(
                    "block_count {block_count} * block_symbols {block_symbols} != width {width}"
                ),
            ));
        }
        usize::MAX // validated after the block flags are known
    } else {
        let expected_block_bytes = dp_block_bytes(block_symbols, omit_bit_plane);
        if block_bytes != expected_block_bytes {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                format!("block_bytes {block_bytes} != expected {expected_block_bytes}"),
            ));
        }
        if block_count * block_symbols != width {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                format!(
                    "block_count {block_count} * block_symbols {block_symbols} != width {width}"
                ),
            ));
        }
        block_count * block_bytes
    };

    if expected_payload_len != usize::MAX && payload_len != expected_payload_len {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!("payload length {payload_len} != expected {expected_payload_len}"),
        ));
    }
    if data.len() != HEADER_SIZE_V2 + payload_len {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            format!(
                "frame length {} != header + payload {}",
                data.len(),
                HEADER_SIZE_V2 + payload_len
            ),
        ));
    }

    let mut crc_input = Vec::with_capacity(data.len());
    crc_input.extend_from_slice(&data[..HEADER_SIZE_V2]);
    crc_input[CRC_OFFSET_V2..CRC_OFFSET_V2 + 4].copy_from_slice(&0u32.to_le_bytes());
    crc_input.extend_from_slice(&data[HEADER_SIZE_V2..]);
    let calculated_crc = crc32(&crc_input);
    if calculated_crc != stored_crc {
        return Err(Dual6Error::new(
            ErrorCode::CrcMismatch,
            format!(
                "CRC32 mismatch: stored {stored_crc:#010x}, calculated {calculated_crc:#010x}"
            ),
        ));
    }

    let payload = &data[HEADER_SIZE_V2..];
    let mut bits = Vec::with_capacity(width);
    let mut trits = Vec::with_capacity(width);
    if sparse {
        let flag_bytes = (block_count + 7) / 8;
        if payload_len < flag_bytes {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                "payload shorter than block flags".to_string(),
            ));
        }
        let block_flags = &payload[..flag_bytes];
        let bitmap_bytes = (block_symbols + 7) / 8;
        let present: usize = (0..block_count)
            .filter(|i| (block_flags[i / 8] >> (i % 8)) & 1 == 1)
            .count();
        let expected = flag_bytes + present * bitmap_bytes + block_count * block_bytes;
        if payload_len != expected {
            return Err(Dual6Error::new(
                ErrorCode::InvalidLayout,
                format!("sparse payload length {payload_len} != expected {expected}"),
            ));
        }
        let mut cursor = flag_bytes;
        let trit_base = flag_bytes + present * bitmap_bytes;
        for i in 0..block_count {
            let has_bitmap = (block_flags[i / 8] >> (i % 8)) & 1 == 1;
            if has_bitmap {
                let part = &payload[cursor..cursor + bitmap_bytes];
                bits.extend(unpack_bits_bytes(part, block_symbols)?);
                cursor += bitmap_bytes;
            } else {
                bits.extend(std::iter::repeat(0u8).take(block_symbols));
            }
            let start = trit_base + i * block_bytes;
            let part = &payload[start..start + block_bytes];
            trits.extend(unpack_trits_bytes(part, block_symbols)?);
        }
    } else if block_symbols == 0 {
        if omit_bit_plane {
            bits = vec![0u8; width];
            trits = unpack_trits_bytes(payload, width)?;
        } else {
            let bit_bytes = (width + 7) / 8;
            bits = unpack_bits_bytes(&payload[..bit_bytes], width)?;
            trits = unpack_trits_bytes(&payload[bit_bytes..], width)?;
        }
    } else {
        let bit_bytes = if omit_bit_plane {
            0
        } else {
            (block_symbols + 7) / 8
        };
        for i in 0..block_count {
            let start = i * block_bytes;
            let stop = start + block_bytes;
            let block = &payload[start..stop];
            if omit_bit_plane {
                bits.extend(std::iter::repeat(0u8).take(block_symbols));
            } else {
                bits.extend(unpack_bits_bytes(&block[..bit_bytes], block_symbols)?);
            }
            trits.extend(unpack_trits_bytes(&block[bit_bytes..], block_symbols)?);
        }
    }

    let meta = FrameMetaV2 {
        layout,
        dtype,
        flags,
        width,
        block_symbols,
        block_bytes,
        block_count,
        payload_len,
        crc32: stored_crc,
    };
    Ok((bits, trits, meta))
}

// ---------------------------------------------------------------------------
// Auto-detection
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameMeta {
    None,
    V2(FrameMetaV2),
}

pub fn frame_version(data: &[u8]) -> Dual6Result<u8> {
    if data.len() < 4 {
        return Err(Dual6Error::new(
            ErrorCode::InvalidLayout,
            "frame shorter than magic",
        ));
    }
    if data[0..4] == MAGIC[..] {
        return Ok(0);
    }
    if data[0..4] == MAGIC_V1[..] {
        return Ok(1);
    }
    if data[0..4] == MAGIC_V2[..] {
        return Ok(2);
    }
    Err(Dual6Error::new(
        ErrorCode::InvalidLayout,
        "unknown frame magic",
    ))
}

pub fn unpack_frame_auto(data: &[u8]) -> Dual6Result<(u8, Vec<u8>, Vec<i8>, FrameMeta)> {
    match frame_version(data)? {
        0 => {
            let (bits, trits) = unpack_dual_plane(data)?;
            Ok((0, bits, trits, FrameMeta::None))
        }
        1 => {
            let (bits, trits) = unpack_dual_plane_v1(data)?;
            Ok((1, bits, trits, FrameMeta::None))
        }
        2 => {
            let (bits, trits, meta) = unpack_dual_plane_v2(data)?;
            Ok((2, bits, trits, FrameMeta::V2(meta)))
        }
        _ => unreachable!(),
    }
}
