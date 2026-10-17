//! Copy vs demux micro-benchmark (scalar Rust; the compiler may auto-vectorize).
//!
//! Run with:
//!     cargo run --release -p dual6-core --example bench_read
//!
//! B: copy a pre-split trit array (memcpy-style read).
//! C: read a symbol stream and demux `d % 3 - 1` per element.

use std::hint::black_box;
use std::time::{Duration, Instant};

fn bench<F: FnMut() -> usize>(name: &str, elements: usize, mut f: F) {
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
    let melems = runs as f64 * elements as f64 / elapsed / 1e6;
    println!("{name:<30} {ns:>9.3} ns/elem {melems:>12.0} Melem/s");
}

fn main() {
    let n = 1_000_000usize;
    let mut state: u64 = 0x1234_5678_9abc_def0;
    let mut next = || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state
    };
    let trit_source: Vec<u8> = (0..n).map(|_| (next() % 3) as u8).collect();
    let symbols: Vec<u8> = (0..n).map(|_| (next() % 6) as u8).collect();

    let mut out_u8 = vec![0u8; n];
    let mut out_i8 = vec![0i8; n];
    let mut out_pair: Vec<(u8, i8)> = vec![(0, 0); n];

    println!("copy vs demux (scalar Rust, n={n})");

    bench("B copy trit (alloc)", n, || {
        let out = trit_source.clone();
        black_box(&out);
        out.len()
    });
    bench("B copy trit (prealloc)", n, || {
        out_u8.copy_from_slice(&trit_source);
        black_box(&out_u8);
        out_u8.len()
    });
    bench("C demux %3 (alloc)", n, || {
        let out: Vec<i8> = symbols.iter().map(|&d| (d % 3) as i8 - 1).collect();
        black_box(&out);
        out.len()
    });
    bench("C demux %3 (prealloc)", n, || {
        for (o, &d) in out_i8.iter_mut().zip(symbols.iter()) {
            *o = (d % 3) as i8 - 1;
        }
        black_box(&out_i8);
        out_i8.len()
    });
    bench("C demux both (prealloc)", n, || {
        for (o, &d) in out_pair.iter_mut().zip(symbols.iter()) {
            *o = (d / 3, (d % 3) as i8 - 1);
        }
        black_box(&out_pair);
        out_pair.len()
    });
}
