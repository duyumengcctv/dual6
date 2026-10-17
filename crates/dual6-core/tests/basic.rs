use dual6_core::{
    decode_digit, demux, encode_digit, frame_version, mux, pack_block64, pack_block64_dp,
    pack_dual_plane, pack_dual_plane_v1, pack_dual_plane_v2, unpack_block64, unpack_block64_dp,
    unpack_dual_plane, unpack_dual_plane_v1, unpack_dual_plane_v2, unpack_frame_auto,
};

#[test]
fn symbol_roundtrip() {
    for b in 0..=1u8 {
        for t in -1..=1i8 {
            let d = encode_digit(b, t).unwrap();
            assert_eq!(decode_digit(d).unwrap(), (b, t));
        }
    }
}

#[test]
fn mux_demux_roundtrip() {
    let bits = vec![1, 0, 1];
    let trits = vec![1, -1, 0];
    let symbols = mux(&bits, &trits).unwrap();
    let (got_bits, got_trits) = demux(&symbols).unwrap();
    assert_eq!(got_bits, bits);
    assert_eq!(got_trits, trits);
}

#[test]
fn block64_roundtrip() {
    let symbols: Vec<u8> = (0..24).map(|i| (i % 6) as u8).collect();
    let data = pack_block64(&symbols).unwrap();
    assert_eq!(data.len(), 8);
    assert_eq!(unpack_block64(&data).unwrap(), symbols);
}

#[test]
fn frame_roundtrip() {
    let bits = vec![1, 0, 1, 0];
    let trits = vec![1, -1, 0, 0];
    let frame = pack_dual_plane(&bits, &trits).unwrap();
    assert_eq!(unpack_dual_plane(&frame).unwrap(), (bits, trits));
}

#[test]
fn frame_v1_roundtrip() {
    let bits = vec![1, 0, 1, 0, 1];
    let trits = vec![1, -1, 0, 0, 1];
    let frame = pack_dual_plane_v1(&bits, &trits).unwrap();
    assert_eq!(unpack_dual_plane_v1(&frame).unwrap(), (bits, trits));
}

#[test]
fn frame_v1_crc_detects_corruption() {
    let bits = vec![1, 0, 1];
    let trits = vec![1, -1, 0];
    let mut frame = pack_dual_plane_v1(&bits, &trits).unwrap();
    let last = frame.len() - 1;
    frame[last] ^= 1;
    assert!(unpack_dual_plane_v1(&frame).is_err());
}

#[test]
fn block64_dp_roundtrip() {
    let bits: Vec<u8> = (0..24).map(|i| (i % 2) as u8).collect();
    let trits: Vec<i8> = (0..24).map(|i| (i % 3) as i8 - 1).collect();
    let data = pack_block64_dp(&bits, &trits).unwrap();
    assert_eq!(data.len(), 8);
    assert_eq!(unpack_block64_dp(&data).unwrap(), (bits, trits));
}

#[test]
fn frame_v2_blocked_roundtrip() {
    let bits: Vec<u8> = (0..48).map(|i| (i % 2) as u8).collect();
    let trits: Vec<i8> = (0..48).map(|i| (i % 3) as i8 - 1).collect();
    let frame = pack_dual_plane_v2(&bits, &trits, dual6_core::DTYPE_TERNARY, 24, 0).unwrap();
    let (got_bits, got_trits, meta) = unpack_dual_plane_v2(&frame).unwrap();
    assert_eq!(got_bits, bits);
    assert_eq!(got_trits, trits);
    assert_eq!(meta.block_symbols, 24);
    assert_eq!(meta.block_count, 2);
}

#[test]
fn frame_auto_detect() {
    let bits = vec![1u8, 0, 1];
    let trits = vec![1i8, -1, 0];

    let f0 = pack_dual_plane(&bits, &trits).unwrap();
    assert_eq!(frame_version(&f0).unwrap(), 0);
    let (v0, b0, t0, _) = unpack_frame_auto(&f0).unwrap();
    assert_eq!((v0, b0, t0), (0, bits.clone(), trits.clone()));

    let f1 = pack_dual_plane_v1(&bits, &trits).unwrap();
    assert_eq!(frame_version(&f1).unwrap(), 1);
    let (v1, b1, t1, _) = unpack_frame_auto(&f1).unwrap();
    assert_eq!((v1, b1, t1), (1, bits.clone(), trits.clone()));

    let f2 = pack_dual_plane_v2(&bits, &trits, dual6_core::DTYPE_RAW, 0, 0).unwrap();
    assert_eq!(frame_version(&f2).unwrap(), 2);
    let (v2, b2, t2, _) = unpack_frame_auto(&f2).unwrap();
    assert_eq!((v2, b2, t2), (2, bits, trits));
}
