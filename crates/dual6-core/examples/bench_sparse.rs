//! Sparse-consumption ablation: does a single frame beat two arrays when only
//! a fraction of the bit channel is consumed?
//!
//! Shape: 512 x 512. `trit` is a ternary weight, `bit` is a consumption mask
//! (1 = consume the weight, 0 = skip). Density is the fraction of 1s.
//!
//! Layouts compared:
//!   B two arrays      : bit plane + trit plane, two allocations
//!   Dual6 dual-plane  : the same bytes in one allocation
//!   Dual6 slot3       : 3 bits / symbol (bit and trit interleaved)
//!   Dual6 inter13     : 5 symbols / 13 bits
//!
//! Run:
//!     cargo run --release -p dual6-core --example bench_sparse -- 0.05
//!     cargo run --release -p dual6-core --example bench_sparse -- 0.01

use std::hint::black_box;
use std::time::{Duration, Instant};

const POW3: [u32; 5] = [1, 3, 9, 27, 81];
const POW6: [u32; 5] = [1, 6, 36, 216, 1296];

const N_ROWS: usize = 512;
const N_COLS: usize = 512;
const STRIDE_TQ1: usize = (N_COLS + 4) / 5;
const STRIDE_SLOT3: usize = (N_COLS * 3 + 7) / 8;
const STRIDE_INTER13: usize = ((N_COLS + 4) / 5 * 13 + 7) / 8;
const STRIDE_BITS: usize = (N_COLS + 7) / 8;

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
    fn act(&mut self) -> i8 {
        ((self.next() % 255) as i32 - 127) as i8
    }
    fn keep(&mut self, density: f64) -> u8 {
        let x = (self.next() % 1_000_000) as f64 / 1_000_000.0;
        if x < density {
            1
        } else {
            0
        }
    }
}

fn build_mask(mode: &str, density: f64, rng: &mut Rng) -> Vec<u8> {
    let mut bits = vec![0u8; N_ROWS * N_COLS];
    let k = ((density * N_COLS as f64).round() as usize)
        .max(1)
        .min(N_COLS);
    match mode {
        "random" => {
            for b in bits.iter_mut() {
                *b = rng.keep(density);
            }
        }
        "column" => {
            // AWQ-style channel outliers: the same contiguous column block
            // is active in every row.
            let start = (rng.next() as usize) % (N_COLS - k + 1);
            for r in 0..N_ROWS {
                for c in start..start + k {
                    bits[r * N_COLS + c] = 1;
                }
            }
        }
        "runs" => {
            // contiguous run per row, random start
            for r in 0..N_ROWS {
                let start = (rng.next() as usize) % (N_COLS - k + 1);
                for c in start..start + k {
                    bits[r * N_COLS + c] = 1;
                }
            }
        }
        "scatter" => {
            // k random columns, same set in every row
            let mut cols: Vec<usize> = (0..N_COLS).collect();
            for i in 0..k {
                let j = i + (rng.next() as usize) % (N_COLS - i);
                cols.swap(i, j);
            }
            for r in 0..N_ROWS {
                for &c in &cols[..k] {
                    bits[r * N_COLS + c] = 1;
                }
            }
        }
        other => panic!("unknown mask mode: {other}"),
    }
    bits
}

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

// --------------------------------------------------------------------------
// sparse kernels: consume trit only where mask bit == 1
// --------------------------------------------------------------------------
fn sparse_plane(bit_plane: &[u8], trit_plane: &[u8], acts: &[i8]) -> Vec<i32> {
    // Process 5 elements per packed trit byte. If all 5 mask bits are zero,
    // skip the trit byte entirely. This is the sparse-consumption advantage
    // that a split-plane layout has and an interleaved symbol stream does not.
    let mut out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let bits = &bit_plane[r * STRIDE_BITS..(r + 1) * STRIDE_BITS];
        let trits = &trit_plane[r * STRIDE_TQ1..(r + 1) * STRIDE_TQ1];
        let mut acc = 0i32;
        for group in 0..((N_COLS + 4) / 5) {
            let base = group * 5;
            let count = (N_COLS - base).min(5);
            let mut mask = 0u32;
            for j in 0..count {
                let i = base + j;
                let b = (bits[i >> 3] >> (i & 7)) & 1;
                mask |= (b as u32) << j;
            }
            if mask == 0 {
                continue;
            }
            let mut v = trits[group] as u32;
            for j in 0..count {
                let t = (v % 3) as i32 - 1;
                v /= 3;
                if (mask >> j) & 1 != 0 {
                    acc += t * acts[base + j] as i32;
                }
            }
        }
        out[r] = acc;
    }
    out
}

fn sparse_slot3(weights: &[u8], acts: &[i8]) -> Vec<i32> {
    let mut out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let row = &weights[r * STRIDE_SLOT3..(r + 1) * STRIDE_SLOT3];
        let mut acc = 0i32;
        for i in 0..N_COLS {
            let d = read_slot3(row, i);
            if d / 3 != 0 {
                let t = (d % 3) as i32 - 1;
                acc += t * acts[i] as i32;
            }
        }
        out[r] = acc;
    }
    out
}

fn sparse_inter13(weights: &[u8], acts: &[i8]) -> Vec<i32> {
    let mut out = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let row = &weights[r * STRIDE_INTER13..(r + 1) * STRIDE_INTER13];
        let mut acc = 0i32;
        let mut idx = 0usize;
        let groups = (N_COLS + 4) / 5;
        for g in 0..groups {
            let mut v = read_inter13(row, g);
            for _ in 0..5 {
                if idx >= N_COLS {
                    break;
                }
                let d = (v % 6) as u8;
                v /= 6;
                if d / 3 != 0 {
                    let t = (d % 3) as i32 - 1;
                    acc += t * acts[idx] as i32;
                }
                idx += 1;
            }
        }
        out[r] = acc;
    }
    out
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
    println!("{name:<34} {ns:>8.3} ns/elem {gbs:>9.2} GB/s");
}

fn main() {
    let density: f64 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0.05);
    let mode = std::env::args()
        .nth(2)
        .unwrap_or_else(|| "random".to_string());

    let mut rng = Rng(0x1234_5678_9abc_def0);
    let total = N_ROWS * N_COLS;
    let bits = build_mask(&mode, density, &mut rng);
    let mut trits = vec![0i8; total];
    let mut symbols = vec![0u8; total];
    for i in 0..total {
        let t = rng.trit();
        trits[i] = t;
        symbols[i] = 3 * bits[i] + ((t + 1) as u8);
    }
    let acts: Vec<i8> = (0..N_COLS).map(|_| rng.act()).collect();

    let mut slot3 = vec![0u8; N_ROWS * STRIDE_SLOT3];
    let mut inter13 = vec![0u8; N_ROWS * STRIDE_INTER13];
    let mut bit_plane = vec![0u8; N_ROWS * STRIDE_BITS];
    let mut trit_plane = vec![0u8; N_ROWS * STRIDE_TQ1];
    for r in 0..N_ROWS {
        let src = r * N_COLS..(r + 1) * N_COLS;
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

    // masked reference
    let mut reference = vec![0i32; N_ROWS];
    for r in 0..N_ROWS {
        let mut acc = 0i32;
        for c in 0..N_COLS {
            let idx = r * N_COLS + c;
            if bits[idx] != 0 {
                acc += trits[idx] as i32 * acts[c] as i32;
            }
        }
        reference[r] = acc;
    }

    let bit_len = bit_plane.len();
    let mut dp_frame = Vec::with_capacity(bit_len + trit_plane.len());
    dp_frame.extend_from_slice(&bit_plane);
    dp_frame.extend_from_slice(&trit_plane);
    let b_bits = bit_plane.clone();
    let b_trits = trit_plane.clone();

    assert_eq!(sparse_plane(&b_bits, &b_trits, &acts), reference);
    assert_eq!(
        sparse_plane(&dp_frame[..bit_len], &dp_frame[bit_len..], &acts),
        reference
    );
    assert_eq!(sparse_slot3(&slot3, &acts), reference);
    assert_eq!(sparse_inter13(&inter13, &acts), reference);

    let kept = bits.iter().filter(|&&b| b != 0).count();
    println!(
        "sparse consumption ({}x{}, mode={}, density={:.2}, kept={} / {})",
        N_ROWS, N_COLS, mode, density, kept, total
    );

    let bytes_plane = bit_len + trit_plane.len();
    bench("B two arrays (bit+trit)", total, bytes_plane, || {
        black_box(sparse_plane(&b_bits, &b_trits, &acts));
        total
    });
    bench("Dual6 one frame (bit+trit)", total, bytes_plane, || {
        black_box(sparse_plane(&dp_frame[..bit_len], &dp_frame[bit_len..], &acts));
        total
    });
    bench("Dual6 slot3", total, slot3.len(), || {
        black_box(sparse_slot3(&slot3, &acts));
        total
    });
    bench("Dual6 inter13", total, inter13.len(), || {
        black_box(sparse_inter13(&inter13, &acts));
        total
    });
}
