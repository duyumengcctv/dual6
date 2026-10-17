//! Stage 2: fused GEMV micro-benchmark (packed weights, no full dequant).
//!
//! Shape: 512 x 512 ternary weights, batch = 1, int8 activations.
//! The kernel reads **packed** weights and decodes trits inside the row loop;
//! it never materialises a full i8 weight matrix.
//!
//! Layouts:
//!   TQ1_0            : 5 trits / byte
//!   Dual6 slot3      : 3 bits / symbol
//!   Dual6 inter13    : 5 symbols / 13 bits
//!   Dual6 dual-plane : bit plane + trit plane (trit plane == TQ1_0)
//!   B two arrays     : same bytes as dual-plane, two allocations
//!
//! Run:
//!     cargo run --release -p dual6-core --example bench_gemv

use std::hint::black_box;
use std::time::{Duration, Instant};

const POW3: [u32; 5] = [1, 3, 9, 27, 81];
const POW6: [u32; 5] = [1, 6, 36, 216, 1296];

const N_ROWS: usize = 512;
const N_COLS: usize = 512;
const STRIDE_TQ1: usize = (N_COLS + 4) / 5; // 103
const STRIDE_SLOT3: usize = (N_COLS * 3 + 7) / 8; // 192
const STRIDE_INTER13: usize = ((N_COLS + 4) / 5 * 13 + 7) / 8; // 168
const STRIDE_BITS: usize = (N_COLS + 7) / 8; // 64

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn trit(&mut self) -> i8 {
        (self.next() % 3) as i8 - 1
    }
    fn bit(&mut self) -> u8 {
        (self.next() & 1) as u8
    }
    fn act(&mut self) -> i8 {
        ((self.next() % 255) as i32 - 127) as i8
    }
}

// --------------------------------------------------------------------------
// packing (row-wise)
// --------------------------------------------------------------------------
fn pack_tq1_row(trits: &[i8], out: &mut [u8]) {
    for (i, chunk) in trits.chunks(5).enumerate() {
        let mut v = 0u32;
        for (j, &t) in chunk.iter().enumerate() {
            v += ((t + 1) as u32) * POW3[j];
        }
        out[i] = v as u8;
    }
}

fn pack_bits_row(bits: &[u8], out: &mut [u8]) {
    for (i, &b) in bits.iter().enumerate() {
        if b != 0 {
            out[i >> 3] |= 1 << (i & 7);
        }
    }
}

fn pack_slot3_row(symbols: &[u8], out: &mut [u8]) {
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
}

fn pack_inter13_row(symbols: &[u8], out: &mut [u8]) {
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
}

// --------------------------------------------------------------------------
// fused GEMV kernels (packed weights -> int32 dot products)
// --------------------------------------------------------------------------
fn gemv_tq1(weights: &[u8], acts: &[i8]) -> Vec<i32> {
    let mut out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let row = &weights[r * STRIDE_TQ1..(r + 1) * STRIDE_TQ1];
        let mut acc = 0i32;
        let mut idx = 0usize;
        for &byte in row {
            let mut v = byte as u32;
            for _ in 0..5 {
                if idx >= N_COLS {
                    break;
                }
                let t = (v % 3) as i32 - 1;
                v /= 3;
                acc += t * acts[idx] as i32;
                idx += 1;
            }
        }
        out[r] = acc;
    }
    out
}

fn gemv_slot3(weights: &[u8], acts: &[i8]) -> Vec<i32> {
    let mut out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let row = &weights[r * STRIDE_SLOT3..(r + 1) * STRIDE_SLOT3];
        let mut acc = 0i32;
        for i in 0..N_COLS {
            let bitpos = i * 3;
            let byte = bitpos >> 3;
            let off = bitpos & 7;
            let d = if off <= 5 {
                (row[byte] >> off) & 7
            } else {
                let lo = (row[byte] >> off) as u16;
                let hi = (row[byte + 1] as u16) << (8 - off);
                ((lo | hi) & 7) as u8
            };
            let t = (d % 3) as i32 - 1;
            acc += t * acts[i] as i32;
        }
        out[r] = acc;
    }
    out
}

fn gemv_inter13(weights: &[u8], acts: &[i8]) -> Vec<i32> {
    let mut out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let row = &weights[r * STRIDE_INTER13..(r + 1) * STRIDE_INTER13];
        let mut acc = 0i32;
        let mut idx = 0usize;
        let groups = (N_COLS + 4) / 5;
        for g in 0..groups {
            let mut value = 0u32;
            let mut got = 0usize;
            let mut pos = g * 13;
            while got < 13 {
                let byte = pos >> 3;
                let off = pos & 7;
                let take = (8 - off).min(13 - got);
                let mask = ((1u16 << take) - 1) as u8;
                let bits = (row[byte] >> off) & mask;
                value |= (bits as u32) << got;
                pos += take;
                got += take;
            }
            let mut v = value;
            for _ in 0..5 {
                if idx >= N_COLS {
                    break;
                }
                let d = (v % 6) as u8;
                v /= 6;
                let t = (d % 3) as i32 - 1;
                acc += t * acts[idx] as i32;
                idx += 1;
            }
        }
        out[r] = acc;
    }
    out
}

fn gemv_both(bit_plane: &[u8], trit_plane: &[u8], acts: &[i8]) -> (Vec<i32>, Vec<i32>) {
    let trit_out = gemv_tq1(trit_plane, acts);
    let mut bit_out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let row = &bit_plane[r * STRIDE_BITS..(r + 1) * STRIDE_BITS];
        let mut acc = 0i32;
        for i in 0..N_COLS {
            let b = ((row[i >> 3] >> (i & 7)) & 1) as i32;
            acc += b * acts[i] as i32;
        }
        bit_out[r] = acc;
    }
    (trit_out, bit_out)
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
    println!("{name:<30} {ns:>8.3} ns/elem {gbs:>9.2} GB/s");
}

fn main() {
    let mut rng = Rng(0x1234_5678_9abc_def0);
    let total = N_ROWS * N_COLS;
    let mut trits = vec![0i8; total];
    let mut bits = vec![0u8; total];
    let mut symbols = vec![0u8; total];
    for i in 0..total {
        let t = rng.trit();
        let b = rng.bit();
        trits[i] = t;
        bits[i] = b;
        symbols[i] = 3 * b + ((t + 1) as u8);
    }
    let acts: Vec<i8> = (0..N_COLS).map(|_| rng.act()).collect();

    let mut tq1 = vec![0u8; N_ROWS * STRIDE_TQ1];
    let mut slot3 = vec![0u8; N_ROWS * STRIDE_SLOT3];
    let mut inter13 = vec![0u8; N_ROWS * STRIDE_INTER13];
    let mut bit_plane = vec![0u8; N_ROWS * STRIDE_BITS];
    let mut trit_plane = vec![0u8; N_ROWS * STRIDE_TQ1];
    for r in 0..N_ROWS {
        let src = r * N_COLS..(r + 1) * N_COLS;
        pack_tq1_row(&trits[src.clone()], &mut tq1[r * STRIDE_TQ1..(r + 1) * STRIDE_TQ1]);
        pack_tq1_row(
            &trits[src.clone()],
            &mut trit_plane[r * STRIDE_TQ1..(r + 1) * STRIDE_TQ1],
        );
        pack_bits_row(
            &bits[src.clone()],
            &mut bit_plane[r * STRIDE_BITS..(r + 1) * STRIDE_BITS],
        );
        pack_slot3_row(
            &symbols[src.clone()],
            &mut slot3[r * STRIDE_SLOT3..(r + 1) * STRIDE_SLOT3],
        );
        pack_inter13_row(
            &symbols[src.clone()],
            &mut inter13[r * STRIDE_INTER13..(r + 1) * STRIDE_INTER13],
        );
    }

    // reference dots (unpacked)
    let mut reference = vec![0i32; N_ROWS];
    let mut bit_reference = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let mut acc = 0i32;
        let mut bit_acc = 0i32;
        for c in 0..N_COLS {
            let idx = r * N_COLS + c;
            acc += trits[idx] as i32 * acts[c] as i32;
            bit_acc += bits[idx] as i32 * acts[c] as i32;
        }
        reference[r] = acc;
        bit_reference[r] = bit_acc;
    }

    // correctness
    assert_eq!(gemv_tq1(&tq1, &acts), reference);
    assert_eq!(gemv_tq1(&trit_plane, &acts), reference);
    assert_eq!(gemv_slot3(&slot3, &acts), reference);
    assert_eq!(gemv_inter13(&inter13, &acts), reference);
    let (t, b) = gemv_both(&bit_plane, &trit_plane, &acts);
    assert_eq!(t, reference);
    assert_eq!(b, bit_reference);

    // one frame: bit plane then trit plane in one allocation
    let bit_len = bit_plane.len();
    let mut dp_frame = Vec::with_capacity(bit_len + trit_plane.len());
    dp_frame.extend_from_slice(&bit_plane);
    dp_frame.extend_from_slice(&trit_plane);
    let (t2, b2) = gemv_both(&dp_frame[..bit_len], &dp_frame[bit_len..], &acts);
    assert_eq!(t2, reference);
    assert_eq!(b2, bit_reference);

    // two separate allocations
    let b_bits = bit_plane.clone();
    let b_trits = trit_plane.clone();

    println!("fused GEMV ({}x{}, batch=1, int8 acts)", N_ROWS, N_COLS);
    bench("TQ1_0 trit only", total, tq1.len(), || {
        black_box(gemv_tq1(&tq1, &acts));
        total
    });
    bench("Dual6 plane trit only", total, trit_plane.len(), || {
        black_box(gemv_tq1(&trit_plane, &acts));
        total
    });
    bench("Dual6 slot3 trit", total, slot3.len(), || {
        black_box(gemv_slot3(&slot3, &acts));
        total
    });
    bench("Dual6 inter13 trit", total, inter13.len(), || {
        black_box(gemv_inter13(&inter13, &acts));
        total
    });
    bench("B two arrays (trit+bit)", total, b_bits.len() + b_trits.len(), || {
        let (t, b) = gemv_both(&b_bits, &b_trits, &acts);
        black_box((&t, &b));
        total
    });
    bench("Dual6 one frame (trit+bit)", total, dp_frame.len(), || {
        let (t, b) = gemv_both(&dp_frame[..bit_len], &dp_frame[bit_len..], &acts);
        black_box((&t, &b));
        total
    });
}
