//! Real-layout demux micro-benchmark.
//!
//! Compares, for the same 1,000,000 elements:
//!
//!   TQ1_0        : 5 trits / byte           (1.6 bpw)
//!   TQ2_0        : 2 bits / trit            (2.0 bpw)
//!   Dual6 slot3  : 3 bits / symbol          (3.0 bpw)
//!   Dual6 inter13: 5 symbols / 13 bits      (2.6 bpw)
//!   Dual6 plane  : bit plane + trit plane   (2.6 bpw total)
//!
//! For each layout we measure:
//!   - trit view demux -> Vec<i8>
//!   - bit  view demux -> Vec<u8>
//!
//! Run:
//!     cargo run --release -p dual6-core --example bench_layouts

use std::hint::black_box;
use std::time::{Duration, Instant};

const POW3: [u32; 5] = [1, 3, 9, 27, 81];
const POW6: [u32; 5] = [1, 6, 36, 216, 1296];

struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn bit(&mut self) -> u8 {
        (self.next() & 1) as u8
    }
    fn trit(&mut self) -> i8 {
        (self.next() % 3) as i8 - 1
    }
}

// --------------------------------------------------------------------------
// TQ1_0: 5 trits per byte
// --------------------------------------------------------------------------
fn pack_tq1(trits: &[i8]) -> Vec<u8> {
    let mut out = vec![0u8; (trits.len() + 4) / 5];
    for (i, chunk) in trits.chunks(5).enumerate() {
        let mut v = 0u32;
        for (j, &t) in chunk.iter().enumerate() {
            v += ((t + 1) as u32) * POW3[j];
        }
        out[i] = v as u8;
    }
    out
}

fn demux_tq1_into(data: &[u8], out: &mut [i8]) {
    for (i, &byte) in data.iter().enumerate() {
        let mut v = byte as u32;
        let base = i * 5;
        for j in 0..5 {
            if base + j >= out.len() {
                return;
            }
            out[base + j] = (v % 3) as i8 - 1;
            v /= 3;
        }
    }
}

// --------------------------------------------------------------------------
// TQ2_0: 2 bits per trit
// --------------------------------------------------------------------------
fn pack_tq2(trits: &[i8]) -> Vec<u8> {
    let mut out = vec![0u8; (trits.len() + 3) / 4];
    for (i, &t) in trits.iter().enumerate() {
        out[i >> 2] |= ((t + 1) as u8) << (2 * (i & 3));
    }
    out
}

fn demux_tq2_into(data: &[u8], out: &mut [i8]) {
    for i in 0..out.len() {
        out[i] = ((data[i >> 2] >> (2 * (i & 3))) & 3) as i8 - 1;
    }
}

// --------------------------------------------------------------------------
// Dual6 3-bit slot
// --------------------------------------------------------------------------
fn pack_slot3(symbols: &[u8]) -> Vec<u8> {
    let mut out = vec![0u8; (symbols.len() * 3 + 7) / 8];
    let mut bitpos = 0usize;
    for &d in symbols {
        let mut v = (d & 7) as u16;
        let mut pos = bitpos;
        let mut rem = 3usize;
        while rem > 0 {
            let byte = pos >> 3;
            let off = pos & 7;
            let take = (8 - off).min(rem);
            out[byte] |= (((v & ((1u16 << take) - 1)) as u8) << off) as u8;
            v >>= take;
            pos += take;
            rem -= take;
        }
        bitpos += 3;
    }
    out
}

#[inline]
fn read_slot3(data: &[u8], i: usize) -> u8 {
    let bitpos = i * 3;
    let byte = bitpos >> 3;
    let off = bitpos & 7;
    if off <= 5 {
        (data[byte] >> off) & 7
    } else {
        let lo = (data[byte] >> off) as u16;
        let hi = (data[byte + 1] as u16) << (8 - off);
        ((lo | hi) & 7) as u8
    }
}

fn demux_slot3_trit_into(data: &[u8], out: &mut [i8]) {
    for i in 0..out.len() {
        out[i] = (read_slot3(data, i) % 3) as i8 - 1;
    }
}

fn demux_slot3_bit_into(data: &[u8], out: &mut [u8]) {
    for i in 0..out.len() {
        out[i] = read_slot3(data, i) / 3;
    }
}

// --------------------------------------------------------------------------
// Dual6 5 symbols / 13 bits
// --------------------------------------------------------------------------
fn pack_inter13(symbols: &[u8]) -> Vec<u8> {
    let groups = (symbols.len() + 4) / 5;
    let mut out = vec![0u8; (groups * 13 + 7) / 8];
    let mut bitpos = 0usize;
    for chunk in symbols.chunks(5) {
        let mut value = 0u32;
        for (j, &d) in chunk.iter().enumerate() {
            value += (d as u32) * POW6[j];
        }
        let mut v = value;
        let mut pos = bitpos;
        let mut rem = 13usize;
        while rem > 0 {
            let byte = pos >> 3;
            let off = pos & 7;
            let take = (8 - off).min(rem);
            out[byte] |= (((v & ((1u32 << take) - 1)) as u8) << off) as u8;
            v >>= take;
            pos += take;
            rem -= take;
        }
        bitpos += 13;
    }
    out
}

#[inline]
fn read_inter13(data: &[u8], group: usize) -> u32 {
    let mut value = 0u32;
    let mut got = 0usize;
    let mut pos = group * 13;
    while got < 13 {
        let byte = pos >> 3;
        let off = pos & 7;
        let take = (8 - off).min(13 - got);
        let mask = ((1u16 << take) - 1) as u8;
        let bits = (data[byte] >> off) & mask;
        value |= (bits as u32) << got;
        pos += take;
        got += take;
    }
    value
}

fn demux_inter13_trit_into(data: &[u8], out: &mut [i8]) {
    let groups = (out.len() + 4) / 5;
    for g in 0..groups {
        let mut v = read_inter13(data, g);
        let base = g * 5;
        for j in 0..5 {
            let d = (v % 6) as u8;
            v /= 6;
            if base + j < out.len() {
                out[base + j] = (d % 3) as i8 - 1;
            }
        }
    }
}

fn demux_inter13_bit_into(data: &[u8], out: &mut [u8]) {
    let groups = (out.len() + 4) / 5;
    for g in 0..groups {
        let mut v = read_inter13(data, g);
        let base = g * 5;
        for j in 0..5 {
            let d = (v % 6) as u8;
            v /= 6;
            if base + j < out.len() {
                out[base + j] = d / 3;
            }
        }
    }
}

// --------------------------------------------------------------------------
// Dual6 dual-plane: bit plane + trit plane
// --------------------------------------------------------------------------
fn pack_bits(bits: &[u8]) -> Vec<u8> {
    let mut out = vec![0u8; (bits.len() + 7) / 8];
    for (i, &b) in bits.iter().enumerate() {
        if b != 0 {
            out[i >> 3] |= 1 << (i & 7);
        }
    }
    out
}

fn demux_bits_into(data: &[u8], out: &mut [u8]) {
    for i in 0..out.len() {
        out[i] = (data[i >> 3] >> (i & 7)) & 1;
    }
}

// --------------------------------------------------------------------------
// driver
// --------------------------------------------------------------------------
fn bench<F: FnMut() -> usize>(name: &str, elements: usize, bytes_read: usize, mut f: F) {
    let budget = Duration::from_millis(300);
    let start = Instant::now();
    let mut runs: u64 = 0;
    let mut acc: usize = 0;
    while start.elapsed() < budget {
        acc ^= f();
        runs += 1;
    }
    black_box(acc);
    let elapsed = start.elapsed().as_secs_f64();
    let ns = elapsed / (runs as f64 * elements as f64) * 1e9;
    let gbs = (runs as f64 * bytes_read as f64) / elapsed / 1e9;
    println!("{name:<28} {ns:>8.3} ns/elem {gbs:>9.2} GB/s");
}

fn main() {
    let n = 1_000_000usize;
    let mut rng = Rng(0x1234_5678_9abc_def0);

    let bits: Vec<u8> = (0..n).map(|_| rng.bit()).collect();
    let trits: Vec<i8> = (0..n).map(|_| rng.trit()).collect();
    let symbols: Vec<u8> = bits
        .iter()
        .zip(trits.iter())
        .map(|(&b, &t)| 3 * b + ((t + 1) as u8))
        .collect();

    let tq1 = pack_tq1(&trits);
    let tq2 = pack_tq2(&trits);
    let slot = pack_slot3(&symbols);
    let inter = pack_inter13(&symbols);
    let bit_plane = pack_bits(&bits);
    let trit_plane = pack_tq1(&trits);

    let mut out_i8 = vec![0i8; n];
    let mut out_u8 = vec![0u8; n];
    let unpacked_u8: Vec<u8> = trits.iter().map(|&t| (t + 1) as u8).collect();

    // correctness
    demux_tq1_into(&tq1, &mut out_i8);
    assert_eq!(out_i8, trits);
    demux_tq2_into(&tq2, &mut out_i8);
    assert_eq!(out_i8, trits);
    demux_slot3_trit_into(&slot, &mut out_i8);
    assert_eq!(out_i8, trits);
    demux_slot3_bit_into(&slot, &mut out_u8);
    assert_eq!(out_u8, bits);
    demux_inter13_trit_into(&inter, &mut out_i8);
    assert_eq!(out_i8, trits);
    demux_inter13_bit_into(&inter, &mut out_u8);
    assert_eq!(out_u8, bits);
    demux_bits_into(&bit_plane, &mut out_u8);
    assert_eq!(out_u8, bits);
    demux_tq1_into(&trit_plane, &mut out_i8);
    assert_eq!(out_i8, trits);

    println!("layout demux (n={n}, preallocated output)");
    bench("copy u8 (bandwidth floor)", n, n, || {
        out_u8.copy_from_slice(&unpacked_u8);
        black_box(&out_u8);
        out_u8.len()
    });
    bench("TQ1_0 -> trit", n, tq1.len(), || {
        demux_tq1_into(&tq1, &mut out_i8);
        black_box(&out_i8);
        out_i8.len()
    });
    bench("TQ2_0 -> trit", n, tq2.len(), || {
        demux_tq2_into(&tq2, &mut out_i8);
        black_box(&out_i8);
        out_i8.len()
    });
    bench("Dual6 slot3 -> trit", n, slot.len(), || {
        demux_slot3_trit_into(&slot, &mut out_i8);
        black_box(&out_i8);
        out_i8.len()
    });
    bench("Dual6 slot3 -> bit", n, slot.len(), || {
        demux_slot3_bit_into(&slot, &mut out_u8);
        black_box(&out_u8);
        out_u8.len()
    });
    bench("Dual6 inter13 -> trit", n, inter.len(), || {
        demux_inter13_trit_into(&inter, &mut out_i8);
        black_box(&out_i8);
        out_i8.len()
    });
    bench("Dual6 inter13 -> bit", n, inter.len(), || {
        demux_inter13_bit_into(&inter, &mut out_u8);
        black_box(&out_u8);
        out_u8.len()
    });
    bench("Dual6 plane -> trit", n, trit_plane.len(), || {
        demux_tq1_into(&trit_plane, &mut out_i8);
        black_box(&out_i8);
        out_i8.len()
    });
    bench("Dual6 plane -> bit", n, bit_plane.len(), || {
        demux_bits_into(&bit_plane, &mut out_u8);
        black_box(&out_u8);
        out_u8.len()
    });
}
