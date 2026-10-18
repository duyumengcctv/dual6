<h1 align="center">Dual6 · 二生三</h1>

<p align="center"><b>One 6-state symbol carries a binary bit and a balanced ternary trit.</b><br>
A storage container for the day a binary engine and a ternary engine have to read the same bytes.</p>

<p align="center">
  <b>English</b> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="tests" src="https://img.shields.io/badge/tests-306%20passing-brightgreen.svg">
  <img alt="python" src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg">
  <img alt="rust" src="https://img.shields.io/badge/rust-2021-DEA584.svg">
  <img alt="status" src="https://img.shields.io/badge/status-dormant-lightgrey.svg">
</p>

<p align="center">
  <img alt="Dual6 format" src="docs/dual6-format.svg" width="880">
</p>

```text
d = 3·b + (t + 1)        b = d // 3        t = d % 3 - 1

d ∈ {0..5}   b ∈ {0,1}   t ∈ {-1, 0, +1}
```

> **This is a container, not an accelerator and not a numeric type.**
> `d` is a *symbol*, not a base-6 digit. No arithmetic is defined on it.

---

## Naming

A model stored in this format is **one `.p6` file** — `llama-3-8b.p6`,
`bitnet-2b.p6`, not a directory of shards and sidecars.

`6` is the first perfect number (1 + 2 + 3 = 6), and it is also where the
encoding comes from: **2 states × 3 states = 6 states**.

The Chinese name is **二生三** (*èr shēng sān*), from the *Tao Te Ching*: "the one
gives birth to the two, the two give birth to the three". Two (binary) giving
birth to three (ternary), inside one symbol.

## Where this came from

I wanted to know one thing: **if a machine ever had a binary datapath and a
ternary datapath side by side, how should the weights be stored so that both
can read them?**

Two answers are obvious and neither is good. Store two copies — now you have
two files, two checksums, two versions that can drift apart. Store one copy and
convert on read — now one engine always pays a conversion in its hot loop.

Dual6 is the third answer: put both views *inside* the symbol, so nobody
converts:

```text
d = 3·b + (t + 1)      one symbol, one bit, one trit
```

The bit channel is the quotient, the trit channel is the remainder. A binary
consumer never looks at the ternary digits and vice versa. Writing costs both
expansions once; reading costs neither.

The question that started it was curiosity, not a benchmark. The measurements
below are what I found when I went looking for an answer.

## Why

A ternary model stores 2 bits' worth of information in 1.58 bits of entropy.
A binary model wants plain bits. Today you pick one, or you store two copies
and keep them in sync.

Dual6 stores **one** artifact where:

- a binary consumer reads `d // 3` — a plain bit plane;
- a ternary consumer reads `d % 3 - 1` — 5 trits per byte, byte-identical to the
  existing 5-trit packing;
- neither needs a conversion step, a second read or a second checksum.

The two planes sit in one file, under one CRC, under one version number.

## Layouts

| Layout | Symbols | Bytes | Used bits |
|---|---:|---:|---:|
| interleaved | 5 | 13 | `D = Σ dᵢ·6ⁱ` |
| `D6-64` | 24 | 8 | 63 / 64 |
| `D6-128` | 48 | 16 | 125 / 128 |
| `D6-40` | 40 | 13 | 104 / 104 |

| Dual-plane block | Bit plane | Trit plane | Total |
|---|---:|---:|---:|
| `D6-64-DP` | 3 B | 5 B | 8 B |
| `D6-128-DP` | 6 B | 10 B | 16 B |
| `D6-40-DP` | 5 B | 8 B | 13 B |

## Frames

| Frame | Header | Integrity | Purpose |
|---|---|---|---|
| `D6P0` | 17 B | — | minimal |
| `D6P1` | 20 B | CRC32 | one dual-plane stream |
| `D6P2` | 33 B | CRC32 | dtype, flags, block metadata |

Two `D6P2` options:

| Option | Effect |
|---|---|
| `FLAG_OMIT_BIT_PLANE` | drop the bit plane — pure-ternary payloads at **1.6 bpw** instead of 2.6 |
| `layout = 1` | compacted bit plane — one flag bit per block, bitmaps only for blocks with a set bit |

## Quick start

```bash
pip install -e .                  # from the repository root
python run_tests.py               # 306 tests
python tools/build_native.py      # optional: Rust extension (faster, same bytes)
```

```python
import dual6

bits  = [1, 0, 1, 1]
trits = [1, -1, 0, 1]

symbols = dual6.mux(bits, trits)                  # [5, 0, 4, 5]
assert dual6.demux(symbols) == (bits, trits)      # both views, no conversion

frame = dual6.pack_dual_plane_v2(bits, trits)     # D6P2, header + CRC32
assert dual6.unpack_dual_plane_v2(frame)[:2] == (bits, trits)
```

### Memory-mapped frames

Reading a large frame does not have to copy it:

```python
from dual6 import MappedFrame, pack_dual_plane_v2, write_frame

frame = pack_dual_plane_v2([1, 0, 1, 1], [1, -1, 0, 1])
write_frame("tiny-model.p6", frame)

with MappedFrame("tiny-model.p6") as m:
    version, bits, trits, meta = m.unpack()       # version ∈ {0, 1, 2}
```

### Rust

The core is a normal crate. It is **not** on crates.io, so depend on it by path
or by git:

```toml
[dependencies]
dual6-core = { path = "crates/dual6-core" }
# dual6-core = { git = "https://github.com/duyumengcctv/dual6", package = "dual6-core" }
```

```rust
let symbols = dual6_core::mux(&bits, &trits)?;
let (bits, trits) = dual6_core::demux(&symbols)?;
```

`DUAL6_BACKEND=ref|native|auto` picks the Python implementation; the two are
required to produce byte-identical output.

## The scorecard: why, what, how

The measurement suite is five raw measurement CSVs plus three derived/policy
CSVs, and six charts. This section is the
**scorecard**, the battery that compares encodings; the other four measurements
(sparse plane, mask structure, fault size, fault matrix) are described in
[`benchmarks/README.md`](benchmarks/README.md) and linked at the end.

> Raw data: [`benchmarks/scorecard_raw.csv`](benchmarks/scorecard_raw.csv) (15 rows × 19 columns) ·
> scenario weights: [`benchmarks/scenario_weights.csv`](benchmarks/scenario_weights.csv) ·
> derived tables: [`scenario_scores.csv`](benchmarks/scenario_scores.csv),
> [`bandwidth_sweep.csv`](benchmarks/bandwidth_sweep.csv) ·
> charts and column definitions: [`benchmarks/README.md`](benchmarks/README.md).

### Why this test exists

Earlier comparisons were one-off duels:

| Comparison | Result | What it could not answer |
|---|---|---|
| Dual6 dual-plane vs `TQ1_0` (decode) | 0.448 vs 0.450 → tie | one metric only |
| one frame vs two arrays (load) | 1.00–1.03× | one metric only |
| Dual6 vs `int8` (sparse gather) | Dual6 loses | measured on the opponent's strongest metric |

Each conclusion is true. Together they still do not answer the question a
reader actually has: *which encoding should I use?* Real workloads weigh
storage, decode, random access, sparse gather, selective reads and integrity
differently, and each encoding wins somewhere.

There is a second reason. If the author chooses the metrics **and** the
weights after seeing the results, the author's own format will win. So the
battery and the weights are fixed before the run, and every weight row is in
the repository. Anyone can re-weight the exported sub-scores without rerunning
the experiment.

Finally, "which encoding is better" has no unique answer, because it depends
on where the bytes come from: on a slow link storage dominates; on a fast link
compute dominates. The output is therefore **conditional**, not a leaderboard.

### What was measured

#### Nine encodings

| Category | Encoding | Why it is in the battery |
|---|---|---|
| dense baseline | `fp16` dense | storage upper bound, cheapest possible decode |
| dense baseline | `int8` dense | the common quantized baseline |
| ternary standard | `TQ1_0` (5 trit/byte) | the ecosystem fact standard |
| ternary variant | `TQ2_0` (2 bit/trit) | simple fixed-width control |
| fixed-width slot | `6-state 3-bit slot` | Dual6's `slot3` layout |
| candidate | **Dual6 dual-plane** | the main layout (1.0 bit + 1.6 trit bpw) |
| candidate | **Dual6 trit-only frame** | pure-ternary mode (1.6 bpw, CRC, one object) |
| candidate | **Dual6 interleaved (13 bit/5 sym)** | the most compact Dual6 packing |
| naive baseline | two separate arrays | no frame, no checksum, the fair "do nothing" control |

#### Two payloads

| Payload | Meaning | Who uses it |
|---|---|---|
| `P_trit` | `n` elements, one balanced trit per element | pure-ternary weights |
| `P_dual` | `n` elements, one `(bit, trit)` pair per element | a per-element side channel |

If an encoding cannot carry a payload, it is **N/A**, never a zero. Making a
container pay for a payload it cannot represent is the most common way a
scorecard cheats.

#### Nine scored metrics

| Metric | Definition | Why it is measured |
|---|---|---|
| `bits_per_element` | bytes × 8 / `n` | storage cost, exact |
| `encode_ns_per_element` | one full write pass | model-build cost (paid once, but real) |
| `decode_ns_net` | one full decode, empty-loop baseline subtracted | the main compute cost |
| `random_ns_net` | 8000 random single-element lookups, call baseline subtracted | checkpoints, sparse updates |
| `sparse_ns_net` | gather 5% of the elements, call baseline subtracted | MoE / mask consumers |
| `selective_bytes` | bytes that must be read to serve one channel only | the metric only a dual-view container can offer |
| `integrity` | does the container carry its own checksum? 0/1 | exact, no noise |
| `single_object` | can it be published and swapped as one object? 0/1 | exact, no noise |
| `ops_per_element` | decoder arithmetic/pass count | machine-independent complexity proxy |

The raw CSV also carries the un-subtracted timings, the two Python calibration
columns, the native decode column and a `compute_source` marker; the full
19-column dictionary is in [`benchmarks/README.md`](benchmarks/README.md).

#### Two derived models

**(a) Scenario score.** Five explicit weight sets — pure ternary inference,
5% sparse gather, per-element dual payload, checkpoint / hot swap, edge small
model — turn the nine metrics into a 0–100 score. The weights are in
[`scenario_weights.csv`](benchmarks/scenario_weights.csv); every sub-score is
exported in [`scenario_scores.csv`](benchmarks/scenario_scores.csv), so anyone
can re-weight without touching the measurement code.

**(b) Physical cost model.** No weights at all:

```text
effective_ns = max(decode_compute_ns, bytes_per_element / bandwidth)
```

It is swept over seven bandwidth levels (1, 3, 10, 30, 100, 300, 1000 GB/s).
This is the model that answers "what wins on *this* link", and its output is in
[`bandwidth_sweep.csv`](benchmarks/bandwidth_sweep.csv).

### Method

**Same payload, same machine, same harness.** Every encoding is driven by the
same code over the same 65,536-element payload on the same machine. This is the
only way to make the difference come from the encoding rather than the
environment.

**Timing: minimum of N runs, interpreter baseline subtracted.**

```text
decode_ns_net = min_of_5(full_decode) - py_loop_overhead_ns
random_ns_net = min_of_5(random_lookup) - py_call_overhead_ns
sparse_ns_net = min_of_5(sparse_gather) - py_call_overhead_ns
```

Without the baseline, Python's own `for v in blob: total += v` loop (about
16 ns/element) would look like the cost of `int8` decoding. The raw columns and
both calibration columns are kept in the CSV so the subtraction can be audited.
One row is clamped: `int8 dense / trit` would be negative after subtraction, so
`decode_ns_net` is pinned at 0.1 ns and marked by the raw columns.

**Normalization: ratios, not min-max.**

```text
score = best_value / this_value        (lower is better)
score = this_value                     (binary metrics: 0 or 1)
```

Min-max would make every historical score depend on the worst candidate, so
adding one new encoding would silently change all old scores. A ratio is
absolute: 0.5 means "twice as expensive as the best", and adding a candidate
cannot change it.

**Weights are public; sub-scores are exported.** A weighted score can only
answer "who wins under this weighting". It cannot answer "which encoding is
better". That is why the README publishes the weight table, the nine
`score_*` columns and the rank, and why the physical model exists separately.

**Native cross-check and the memcpy floor.** `decode_ns_native` is either a
Rust microbenchmark or, for dense formats, a `memcpy` floor marked with
`compute_source = memcpy_floor`. The floor is optimistic for dense formats,
which biases the comparison **against** bit-packed formats; the direction of
that bias is written into the data.

### Results

#### Pure-trit payload (9 encodings)

| Encoding | bpw | encode ns | decode ns | native/floor ns | random ns | sparse 5% ns | selective B | CRC | one object |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 dense | 16.00 | 41.5 | 23.9 | 0.035† | 71.5 | 60.2 | 131072 | — | — |
| int8 dense | 8.00 | 35.5 | 0.1 | 0.035† | 21.3 | 14.1 | 65536 | — | ✓ |
| TQ1_0 (5 trit/byte) | 1.60 | 85.9 | 59.3 | 0.450 | 90.5 | 77.8 | 13108 | — | ✓ |
| TQ2_0 (2 bit/trit) | 2.00 | 88.9 | 48.5 | 0.562 | 62.4 | 57.7 | 16384 | — | ✓ |
| 6-state 3-bit slot | 3.00 | 269.6 | 230.4 | 1.015 | 114.1 | 103.5 | 24576 | — | ✓ |
| Dual6 dual-plane | 2.60 | 160.6 | 119.1 | 0.448 | 211.5 | 170.5 | 13108 | ✓ | ✓ |
| Dual6 dual-plane (trit-only) | 1.60 | 160.5 | 59.2 | 0.448 | 92.4 | 76.6 | 13108 | ✓ | ✓ |
| Dual6 interleaved (13 bit) | 2.60 | 156.2 | 113.6 | 1.648 | 343.6 | 319.9 | 21301 | ✓ | ✓ |
| two separate arrays | 1.60 | 87.3 | 80.0 | 0.448 | 120.1 | 98.8 | 13108 | — | — |

† `memcpy_floor`: dense formats are not decoded; the number is the copy floor
used as an optimistic proxy, so the comparison is conservative for Dual6.

The table is the whole trade-off in one screen: the cheapest storage goes to
`TQ1_0`, `two separate arrays` and the **Dual6 trit-only frame** (all 1.60 bpw);
`int8` decodes 592× faster but stores 8.00 bpw. The only encodings carrying a
checksum are the three Dual6 ones.

#### Dual payload (6 encodings)

| Encoding | bpw | encode ns | decode ns | native/floor ns | random ns | sparse 5% ns | selective B | CRC | one object |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 dense | 32.00 | 79.1 | 55.8 | 0.035† | 71.8 | 61.3 | 262144 | — | — |
| int8 dense | 16.00 | 55.8 | 11.0 | 0.035† | 26.8 | 12.8 | 131072 | — | ✓ |
| 6-state 3-bit slot | 3.00 | 280.3 | 231.7 | 1.015 | 105.0 | 101.2 | 24576 | — | ✓ |
| Dual6 dual-plane | 2.60 | 163.3 | 125.6 | 0.448 | 232.0 | 178.5 | 8192 | ✓ | ✓ |
| Dual6 interleaved (13 bit) | 2.60 | 167.8 | 112.8 | 1.648 | 330.3 | 319.4 | 21301 | ✓ | ✓ |
| two separate arrays | 2.60 | 165.6 | 135.6 | 0.448 | 245.0 | 190.8 | 8192 | — | — |

Only six encodings can carry a `(bit, trit)` pair per element, so the dual table
has six rows. The second channel costs **1.62×** the storage of the trit-only
payload (2.60 vs 1.60 bpw). The structural payoff is `selective_bytes`: the
dual-plane frame serves one channel from **8192 B**, while `int8` needs
131072 B and the interleaved layout needs all 21301 B.

<p align="center">
  <img alt="nine encodings: storage against decode cost" src="benchmarks/charts/scorecard.png" width="620"><br>
  <sub>Storage against decode cost for the nine encodings (pure-trit payload). The star is
  the trit-only frame: the same bytes as TQ1_0, plus a CRC.</sub>
</p>

#### Five weight sets

| Scenario | Payload | bpw | encode | decode | random | sparse | selective | CRC | single | ops |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pure_ternary | trit | 30 | 5 | 20 | 5 | 5 | 5 | 15 | 10 | 5 |
| sparse_gather | both | 20 | 5 | 10 | 15 | 30 | 5 | 5 | 5 | 5 |
| dual_channel | dual | 20 | 5 | 15 | 5 | 10 | 25 | 10 | 5 | 5 |
| checkpoint_hot_swap | both | 10 | 10 | 10 | 20 | 5 | 5 | 20 | 15 | 5 |
| edge_small_model | both | 40 | 10 | 15 | 5 | 5 | 5 | 10 | 5 | 5 |

Weights sum to 100 in every row; `both` means the scenario is scored separately
for the trit and dual payloads, never across them.

| Scenario | Payload | Winner | Score | Runner-up | Score |
|---|---|---|---:|---|---:|
| pure_ternary | trit | Dual6 dual-plane (trit-only) | 64.5 | int8 dense | 57.0 |
| sparse_gather | trit | int8 dense | 75.0 | Dual6 dual-plane (trit-only) | 46.3 |
| sparse_gather | dual | int8 dense | 73.6 | Dual6 dual-plane | 42.7 |
| dual_channel | dual | Dual6 dual-plane | 65.6 | two separate arrays | 54.1 |
| checkpoint_hot_swap | trit | int8 dense | 68.0 | Dual6 dual-plane (trit-only) | 59.0 |
| checkpoint_hot_swap | dual | int8 dense | 66.9 | Dual6 dual-plane | 58.2 |
| edge_small_model | trit | Dual6 dual-plane (trit-only) | 65.6 | TQ1_0 (5 trit/byte) | 58.7 |
| edge_small_model | dual | Dual6 dual-plane | 66.9 | Dual6 interleaved (13 bit) | 63.3 |

<p align="center">
  <img alt="scenario scores" src="benchmarks/charts/scenario-scores.png" width="760"><br>
  <sub>Every sub-score is exported in <code>scenario_scores.csv</code>; the heat map is
  only a rendering of that file.</sub>
</p>

What the five weight sets say, honestly:

- **No encoding wins everything.** Under storage + integrity + single-object
  weights the trit-only frame wins; under sparse-gather and hot-swap weights
  `int8` wins; under dual-channel weights the dual-plane frame wins.
- **The dual-plane win is conditional.** It wins the scenario that actually
  consumes both channels. It does not win the pure-latency scenarios.
- **The weights are the argument.** They are published as data, not buried in
  code, so a reader who disagrees can re-weight the exported sub-scores.

#### Physical cost model

| Bandwidth (GB/s) | trit winner(s) | effective ns | dual winner(s) | effective ns |
|---:|---|---:|---|---:|
| 1 | Dual6 dual-plane / Dual6 dual-plane (trit-only) / two separate arrays | 0.448 | Dual6 dual-plane / two separate arrays | 0.448 |
| 3 | int8 dense | 0.333 | Dual6 dual-plane / two separate arrays | 0.448 |
| 10 | int8 dense | 0.100 | int8 dense | 0.200 |
| 30 | int8 dense | 0.035 | int8 dense | 0.067 |
| 100 | fp16 dense / int8 dense | 0.035 | int8 dense | 0.035 |
| 300 | fp16 dense / int8 dense | 0.035 | fp16 dense / int8 dense | 0.035 |
| 1000 | fp16 dense / int8 dense | 0.035 | fp16 dense / int8 dense | 0.035 |

<p align="center">
  <img alt="bandwidth crossover" src="benchmarks/charts/bandwidth-crossover.png" width="760"><br>
  <sub>Effective cost per element against link bandwidth. Left: trit payload;
  right: dual payload. Lower is better.</sub>
</p>

Read this table as a condition, not a ranking:

- **Slow links are storage-bound.** At 1 GB/s the bit-packed layouts win on the
  trit payload (0.448 ns effective) and the dual-plane / two-array layouts win
  on the dual payload (0.448 ns).
- **Mid-range links are memory-bound.** `int8` wins around 3–30 GB/s on trit and
  10–100 GB/s on dual, because one byte per element is cheap enough and its
  compute floor is very low.
- **Fast links are compute-bound.** From roughly 100 GB/s on trit and 300 GB/s
  on dual upward, the dense formats sit on the 0.035 ns `memcpy` floor and tie. The crossover band is roughly
  **2–5 GB/s** on trit and **4–9 GB/s** on dual, depending on which pair you
  compare. The often-quoted "storage wins below 1–3 GB/s, compute above
  30 GB/s" is the safe outer envelope of these curves, not a single cliff.

#### What the battery settled

| Question | Answer |
|---|---|
| Is there an all-win encoding? | **No.** The storage winners (`TQ1_0`, `two separate arrays`, trit-only Dual6) and the latency winners (`int8`) are different encodings. |
| How good is Dual6's pure-ternary mode? | **Parity with `TQ1_0`**: 1.60 bpw / 59.2 ns vs 59.3 ns, plus a CRC32 and a single-object frame. |
| What is the second channel worth? | **1.62× storage** (2.60 vs 1.60 bpw), and only if something actually reads it. |
| When does which encoding win? | On slow links storage dominates and bit-packed layouts win; on fast links compute dominates and dense layouts win. The crossover is a band, not a point. |
| What is Dual6's one structural advantage? | **Selective reads**: on a dual payload, 8192 B serve one channel, against 131072 B for `int8`. |

### Limitations

1. **Python timing amplifies by ~100×.** The ordering is meaningful; the
   absolute nanoseconds are not.
2. **Dense-format compute is a `memcpy` proxy**, marked in `compute_source`.
3. **Single machine.** Absolute numbers do not transfer.
4. **Synthetic payload.** Trits are uniform, not a real BitNet weight
   distribution.
5. **Nine encodings only.** `Q4_0`, `IQ2` and other real quantized formats are
   not in the battery.
6. **No measurement ran on a real model.** The largest payload is 8 MiB.

Conclusions about structure (no all-win encoding, trit-only parity, the 1.62×
second-channel cost, selective reads) follow from the format definitions and do
not depend on those six caveats. The exact nanosecond values do.

### The rest of the suite

The scorecard compares encodings. The other four CSVs answer different
questions: compacted bit planes (`sparse_plane.csv`; clustered masks save
**−25% to −33%** at 5% density), mask structure (`mask_structure.csv`), silent
corruption vs payload size (`fault_size.csv`) and what protects a reader under
faults (`fault_matrix.csv`). Silent corruption starts between 64 KiB and 512 KiB on this machine. The fault-size result is worth keeping next to the
scorecard:

<p align="center">
  <img alt="silent corruption vs payload size" src="benchmarks/charts/fault-size.png" width="560"><br>
  <sub>In-place same-size overwrite of a checksum-less container: nothing below 64 KiB,
  1.5% of reads at 512 KiB, 26.5% at 8 MiB.</sub>
</p>

### Data and reproduction

```bash
python tools/make_scores.py          # rebuild scenario_scores.csv + bandwidth_sweep.csv
python tools/make_scores.py --check  # fail if the committed derived CSVs are stale
python tools/make_charts.py          # rebuild all six charts from the CSVs
python run_tests.py                  # tables in the READMEs are checked against the CSVs
```

The benchmark **harness** that produced the raw timings lives in a private
archive, not in this repository. What is reproducible here is the data pipeline:
raw CSV → derived CSVs → charts → README tables. Absolute timings cannot be
reproduced without the harness and the same machine.


## What came of it

**It is not faster, and the repository should be read that way.**

| Question | Answer |
|---|---|
| Is decoding cheaper? | No. The trit plane is the existing 5-trit packing, so it costs the same: trit-only frame **1.60 bpw / 59.2 ns** vs `TQ1_0` 1.60 bpw / 59.3 ns. |
| Is storage cheaper? | Not for two channels: **2.6 bpw** against 1.6 for pure ternary — a 62.5% premium. Drop the bit plane and it lands back at 1.6. |
| Is a single frame faster to load? | No. Equivalent within ±5% at best, consistently ~2% slower in repeated runs. |
| Does the second channel pay for itself? | Only if something actually reads it. In a fused GEMV that consumes both channels, the cost roughly doubles. |

Three things did survive:

1. **Trit-only frames reach parity with the existing packing** (1.60 bpw, same
   decode cost) while adding a CRC32 and a single-object frame — that is a
   free integrity check for a pure-ternary payload.
2. **A compacted bit plane pays when the bit channel is a clustered mask**
   (−25% to −33% at 5% density), and costs 1.5% when the mask is periodic.
   The rule is empty-block share, not density.
3. **The most useful result was not the encoding.** Injecting faults into four
   containers under three update protocols showed that silent corruption is
   decided by *a checksum and an atomic rename*, not by how the bytes are
   packed — and that it only appears above a size threshold (between 64 KiB and
   512 KiB on this machine). That finding applies to any format, including the
   ones people already use.

So the honest summary: **a container that does one thing nothing else does
(one artefact, two views, one checksum, one version), at a storage cost that
only makes sense when both views are actually consumed.**

## Where it actually fits

Four situations. Each one names the condition that makes it *wrong*, because a
container that claims everything fits nothing.

**1 · A per-element side channel next to ternary weights** — `D6P2`, dual-plane

The case the format was designed for: a ternary value and a per-element flag
mask (outlier, prune, "use the high-precision copy") that the same kernel reads
in the same pass. One stream, no pointer chasing, no second file to fall out of
sync. With a clustered mask, `layout 1` adds **−25% to −33%** on top.

<p align="center">
  <img alt="compacted bit plane vs mask structure" src="benchmarks/charts/mask-structure.png" width="600"><br>
  <sub>Same 5% density, five arrangements, five replicates each. Clustered masks save
  25–33%; a periodic scatter costs 1.5%.</sub>
</p>

*Wrong when* the two channels are not element-aligned. That is most formats
today: AWQ and OWQ keep per-*channel* scales, SpQR and SqueezeLLM keep sparse
indices — both deliberately avoid an aligned second channel, which is exactly
what makes them cheap. **This scenario is currently hypothetical**; the
container is ready for it, not proof that it exists.

**2 · A pure-ternary model that wants one file and one checksum** — `D6P2`,
`FLAG_OMIT_BIT_PLANE`

Lands at **1.60 bpw and 59.2 ns/element**, the same as `TQ1_0` (1.60 / 59.3),
while adding a CRC32 and a single-object frame. Cheap for slow media and small
machines: one `open`, one `mmap`, one checksum.

<p align="center">
  <img alt="compacted bit plane vs mask density" src="benchmarks/charts/sparse-plane.png" width="600"><br>
  <sub>Density sweep for the same option: the saving grows as the mask thins, and
  disappears above ~10%.</sub>
</p>

*Wrong when* the data is already fast. A single frame is **not** faster to load
— measured equivalent at best, ~2% slower in repeated runs — so on an NVMe
drive or a cache-resident model the extra frame is pure overhead.

**3 · Hot-swapping a model while it is being served** — any frame, plus a protocol

Not a property of the container. Fault injection into four unrelated containers
showed that silent corruption is decided by **a checksum and an atomic rename**,
not by how the bytes are packed. A plain GGUF wrapped in a manifest gets the
same protection.

*What the measurements do say*: an in-place same-size overwrite is invisible
below **64 KiB**, starts to tear at **512 KiB** (1.5% of reads), and reaches
**17% at 2 MiB** and **26.5% at 8 MiB**. If you rewrite a model file in place,
you are already exposed — whatever format it is in.

**4 · A loader that must be written in C, C++ or Rust** — `D6P1` / `D6P2`

One fixed header gives plane offsets; the bit plane is directly addressable and
the trit plane is the existing 5-trit/byte packing, so an existing ternary
kernel reads it unchanged. Embedding the container in an engine is a header
parse, not a parser.

*Careful with "zero copy"*: the bit plane is directly usable, the trit plane
still has to be unpacked — the way every 5-trit kernel already does.

**Where it does not fit**, stated plainly:

- pure ternary inference with no per-element metadata → use `TQ1_0`;
- anything that fits in cache → `int8` decodes an order of magnitude faster;
- cross-layer mixed precision, MoE routing tables, KV-cache layouts → the
  channels are not element-aligned, and none of the measurements apply;
- a general compression format → this is a container, not a codec.

The long version, with the measurements behind each row, is in
[`docs/13-use-cases.md`](docs/13-use-cases.md).

One sentence for a README badge: *if your model is pure ternary, use `TQ1_0`;
if you need one artefact that a binary and a ternary engine can both read, or
one file you can checksum and swap atomically, this is what that looks like.*

## Outlook

## Status

**Dormant, not abandoned.** The container works and is tested; nothing new is
being added while the premise is unproven.

The premise is narrow: a binary engine and a ternary engine reading **the same
element** in the same pass. Today that only half-exists — ternary models such as
BitNet store ternary values but compute in FP16, so the bit channel has no
consumer. Two signals would change that:

1. a public model format whose per-element metadata is read alongside the
   weights (not per-tensor scales, not sparse indices);
2. ternary *compute* executing natively, instead of being unpacked to float.

Until then this stays a container with a specification, an implementation and
measurements.

## Scope

**In scope** — the symbol, sequence/layout/block packing, frames, error codes,
single-channel adapters.

**Out of scope** — value interpretation, quantisation, dtype/shape metadata,
tensor operators, and any model-format connector. The container carries bytes;
it does not explain them.

## Documentation

| File | Contents |
|---|---|
| [`docs/00-scope.md`](docs/00-scope.md) | what belongs in the container |
| [`docs/01-symbol.md`](docs/01-symbol.md) | the 6-state symbol |
| [`docs/02-sequence.md`](docs/02-sequence.md) | `mux` / `demux` |
| [`docs/03-layout.md`](docs/03-layout.md) | interleaved, dual-plane, fixed blocks |
| [`docs/04-frame.md`](docs/04-frame.md) | `D6P0` / `D6P1` / `D6P2`, flags, layouts |
| [`docs/05-errors.md`](docs/05-errors.md) | error codes |
| [`docs/08-api.md`](docs/08-api.md) | public API |
| [`docs/09-release.md`](docs/09-release.md) | build, test and release the package |
| [`docs/11-exact-dual.md`](docs/11-exact-dual.md) | optional codec: one integer, two views |
| [`docs/12-arithmetic.md`](docs/12-arithmetic.md) | optional exact-dual arithmetic helper |
| [`docs/13-use-cases.md`](docs/13-use-cases.md) | where it fits, where it does not, what it waits for |
| [`benchmarks/README.md`](benchmarks/README.md) | what each CSV measured, on what machine |
| [`tools/make_scores.py`](tools/make_scores.py) | rebuilds the scenario and bandwidth CSVs |
| [`tools/make_charts.py`](tools/make_charts.py) | regenerates all six charts from the CSVs |

## Repository layout

```text
python/dual6/      reference implementation (+ adapters, CLI, mmap)
crates/            dual6-core (Rust), dual6-py (PyO3), dual6-ffi (C ABI)
docs/              the specification, one topic per file
benchmarks/        5 raw + 3 derived CSVs, 6 charts
tests/             306 tests, including spec-derived ones
examples/          three runnable programs
tools/             check_all.py, coverage.py, verify_package.py, build_native.py, ...
```

## Tests

```bash
python run_tests.py                        # 306
DUAL6_BACKEND=ref python run_tests.py      # reference backend only
cargo test -p dual6-core                   # Rust core
```

[`tests/test_spec_from_scratch.py`](tests/test_spec_from_scratch.py) parses the
tables in `docs/01`–`docs/05` and checks the implementation against them, so a
change to the spec or the code that is not reflected in the other fails the
build. [`tests/test_benchmark_data.py`](tests/test_benchmark_data.py) holds the
CSVs in `benchmarks/` to the numbers quoted above.

**What they cover**: container round-trips, golden vectors, error codes,
backend parity (native and reference must agree byte-for-byte), property and
fuzz tests, and both `D6P2` options.

**What they do not cover**: the benchmark *scripts* are not in this repository,
only their output. An earlier working archive reports a larger count because it
also carries chart, bundle and documentation guards that have no meaning
without those scripts.

## License

MIT — see [`LICENSE`](LICENSE).
