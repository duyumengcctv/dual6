//! Dual6 storage container core.
//!
//! This crate is storage-only.  It defines the 6-state symbol mux/demux,
//! interleaved and dual-plane layouts, fixed blocks, and the D6P0 frame.
//! It does not define arithmetic on `d`.

pub mod blocks;
pub mod dual_plane;
pub mod error;
pub mod frame;
pub mod interleaved;
pub mod sequence;
pub mod symbol;
pub mod views;

pub use blocks::{
    pack_block, pack_block128, pack_block128_dp, pack_block40, pack_block40_dp, pack_block64,
    pack_block64_dp, pack_block64_many, pack_block_dp, unpack_block, unpack_block128,
    unpack_block128_dp, unpack_block40, unpack_block40_dp, unpack_block64, unpack_block64_dp,
    unpack_block64_many, unpack_block_dp,
    BlockLayout, DualPlaneBlockLayout, BLOCK128, BLOCK128_DP, BLOCK40, BLOCK40_DP, BLOCK64,
    BLOCK64_DP,
};
pub use dual_plane::{
    bits_bytes_len, pack_bits_bytes, pack_trits_bytes, trits_bytes_len, unpack_bits_bytes,
    unpack_trits_bytes, TRIT_PER_BYTE,
};
pub use error::{Dual6Error, Dual6Result, ErrorCode};
pub use frame::{
    frame_version, pack_dual_plane, pack_dual_plane_v1, pack_dual_plane_v2,
    pack_dual_plane_v2_layout, unpack_dual_plane, unpack_dual_plane_v1, unpack_dual_plane_v2,
    unpack_frame_auto, FrameMeta, FrameMetaV2, DTYPE_BINARY, DTYPE_MIXED, DTYPE_RAW,
    DTYPE_TERNARY, FLAG_OMIT_BIT_PLANE, LAYOUT_DUAL_PLANE, LAYOUT_DUAL_PLANE_SPARSE,
    LAYOUT_DUAL_PLANE_V2, MAGIC, MAGIC_V1, MAGIC_V2, VERSION, VERSION_V1, VERSION_V2,
};
pub use interleaved::{
    fits_unsigned_word, max_interleaved, pack_digits, unpack_digits, MAX_INTERLEAVED_SYMBOLS,
};
pub use sequence::{demux, mux};
pub use symbol::{
    check_bit, check_digit, check_trit, decode_digit, encode_digit, DIGIT_BASE, DIGIT_COUNT,
};
pub use views::{bits, trits};
