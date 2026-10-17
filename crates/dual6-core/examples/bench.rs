//! Raw Rust-core benchmark (no Python / PyO3 overhead).
//!
//! Run with:
//!     cargo run --release -p dual6-core --example bench

use std::hint::black_box;
use std::time::{Duration, Instant};

use dual6_core as d6;

struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.0
    }
    fn bit(&mut self) -> u8 {
        ((self.next() >> 33) & 1) as u8
    }
    fn trit(&mut self) -> i8 {
        (((self.next() >> 33) % 3) as i8) - 1
    }
    fn symbol(&mut self) -> u8 {
        ((self.next() >> 33) % 6) as u8
    }
}

fn bench<F: FnMut()>(name: &str, elements: usize, mut f: F) {
    let budget = Duration::from_millis(200);
    let start = Instant::now();
    let mut runs: u64 = 0;
    while start.elapsed() < budget {
        f();
        runs += 1;
    }
    let elapsed = start.elapsed().as_secs_f64();
    let ops = runs as f64 / elapsed;
    let ns_per_elem = elapsed / (runs as f64 * elements as f64) * 1e9;
    println!("{name:<28} {ops:>14.0} ops/s  {ns_per_elem:>8.3} ns/elem");
}

fn main() {
    let mut rng = Rng(7);
    let n = 4096usize;
    let bits: Vec<u8> = (0..n).map(|_| rng.bit()).collect();
    let trits: Vec<i8> = (0..n).map(|_| rng.trit()).collect();
    let symbols24: Vec<u8> = (0..24).map(|_| rng.symbol()).collect();
    let bits24: Vec<u8> = (0..24).map(|_| rng.bit()).collect();
    let trits24: Vec<i8> = (0..24).map(|_| rng.trit()).collect();

    let block64 = d6::pack_block64(&symbols24).unwrap();
    let block64_dp = d6::pack_block64_dp(&bits24, &trits24).unwrap();
    let bit_bytes = d6::pack_bits_bytes(&bits).unwrap();
    let trit_bytes = d6::pack_trits_bytes(&trits).unwrap();
    let frame = d6::pack_dual_plane(&bits, &trits).unwrap();

    println!("dual6-core raw Rust benchmark (n={n})");
    bench("pack_block64", 24, || {
        black_box(d6::pack_block64(black_box(&symbols24)).unwrap());
    });
    bench("unpack_block64", 24, || {
        black_box(d6::unpack_block64(black_box(&block64)).unwrap());
    });
    bench("pack_block64_dp", 24, || {
        black_box(d6::pack_block64_dp(black_box(&bits24), black_box(&trits24)).unwrap());
    });
    bench("unpack_block64_dp", 24, || {
        black_box(d6::unpack_block64_dp(black_box(&block64_dp)).unwrap());
    });
    bench("pack_bits_bytes", n, || {
        black_box(d6::pack_bits_bytes(black_box(&bits)).unwrap());
    });
    bench("unpack_bits_bytes", n, || {
        black_box(d6::unpack_bits_bytes(black_box(&bit_bytes), n).unwrap());
    });
    bench("pack_trits_bytes", n, || {
        black_box(d6::pack_trits_bytes(black_box(&trits)).unwrap());
    });
    bench("unpack_trits_bytes", n, || {
        black_box(d6::unpack_trits_bytes(black_box(&trit_bytes), n).unwrap());
    });
    bench("pack_dual_plane(D6P0)", n, || {
        black_box(d6::pack_dual_plane(black_box(&bits), black_box(&trits)).unwrap());
    });
    bench("unpack_dual_plane(D6P0)", n, || {
        black_box(d6::unpack_dual_plane(black_box(&frame)).unwrap());
    });
    bench("mux", n, || {
        black_box(d6::mux(black_box(&bits), black_box(&trits)).unwrap());
    });
    let symbols: Vec<u8> = d6::mux(&bits, &trits).unwrap();
    bench("demux", n, || {
        black_box(d6::demux(black_box(&symbols)).unwrap());
    });
}
