use dual6_core::{
    decode_digit, encode_digit, pack_block64, pack_block64_dp, pack_digits, pack_dual_plane,
    pack_dual_plane_v1, pack_dual_plane_v2, unpack_block64, unpack_block64_dp, unpack_dual_plane,
    unpack_dual_plane_v1, unpack_dual_plane_v2,
};

fn unhex(text: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(text.len() / 2);
    let bytes = text.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let hi = (bytes[i] as char).to_digit(16).unwrap() as u8;
        let lo = (bytes[i + 1] as char).to_digit(16).unwrap() as u8;
        out.push((hi << 4) | lo);
        i += 2;
    }
    out
}

#[test]
fn digit_vectors() {
    let cases = [
        (0u8, -1i8, 0u8),
        (0, 0, 1),
        (0, 1, 2),
        (1, -1, 3),
        (1, 0, 4),
        (1, 1, 5),
    ];
    for (bit, trit, digit) in cases {
        assert_eq!(encode_digit(bit, trit).unwrap(), digit);
        assert_eq!(decode_digit(digit).unwrap(), (bit, trit));
    }
}

#[test]
fn pack5_vectors() {
    assert_eq!(pack_digits(&[0, 1, 2, 3, 4]).unwrap(), 5910);
    assert_eq!(pack_digits(&[5, 5, 5, 5, 5]).unwrap(), 7775);
    assert_eq!(pack_digits(&[1, 1, 1, 1, 1]).unwrap(), 1555);
}

#[test]
fn block64_vectors() {
    let symbols = [0u8, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5];
    let data = pack_block64(&symbols).unwrap();
    assert_eq!(data, unhex("76b0a0ef412e213f"));
    assert_eq!(unpack_block64(&data).unwrap(), symbols.to_vec());
}

#[test]
fn block64_dp_vectors() {
    let bits: Vec<u8> = [1u8, 0].iter().cycle().take(24).copied().collect();
    let trits: Vec<i8> = [1i8, -1].iter().cycle().take(24).copied().collect();
    let data = pack_block64_dp(&bits, &trits).unwrap();
    assert_eq!(data, unhex("555555b63cb63c14"));
    assert_eq!(unpack_block64_dp(&data).unwrap(), (bits, trits));
}

#[test]
fn d6p0_vector() {
    let bits = vec![1u8, 0, 1];
    let trits = vec![1i8, -1, 0];
    let data = pack_dual_plane(&bits, &trits).unwrap();
    assert_eq!(data, unhex("4436503001030000000100000001000000050b"));
    assert_eq!(unpack_dual_plane(&data).unwrap(), (bits, trits));
}

#[test]
fn d6p1_vector() {
    let bits = vec![1u8, 0, 1];
    let trits = vec![1i8, -1, 0];
    let data = pack_dual_plane_v1(&bits, &trits).unwrap();
    assert_eq!(data, unhex("443650310100000003000000020000006a9bae5e050b"));
    assert_eq!(unpack_dual_plane_v1(&data).unwrap(), (bits, trits));
}

#[test]
fn d6p2_vector() {
    let bits: Vec<u8> = [1u8, 0].iter().cycle().take(48).copied().collect();
    let trits: Vec<i8> = [1i8, -1].iter().cycle().take(48).copied().collect();
    let data = pack_dual_plane_v2(&bits, &trits, dual6_core::DTYPE_TERNARY, 24, 0).unwrap();
    assert_eq!(
        data,
        unhex("4436503201000200003000000018000000080000000200000010000000cae956d2555555b63cb63c14555555b63cb63c14")
    );
    let (got_bits, got_trits, meta) = unpack_dual_plane_v2(&data).unwrap();
    assert_eq!((got_bits, got_trits), (bits, trits));
    assert_eq!(meta.block_symbols, 24);
}
