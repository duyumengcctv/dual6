# Measurements

Raw data behind the numbers quoted in the top-level `README.md`. Every
measurement file is a CSV produced by a script. Four files are hand-authored
policy/layout inputs: `scenario_weights.csv` (scenario weights),
`encoding_layout.csv` (per-channel plane sizes), `data_models.csv` (T/I/X/S
semantics) and `encoding_taxonomy.csv` (which measured row belongs to which
model).

The harness that produced the raw timings lives in the private working archive,
not in this repository (it pulls in a benchmark setup that is out of scope for a
storage container). The derived pipeline *is* in the repository:
`tools/make_scores.py` and `tools/make_charts.py`. The CSV headers are
self-describing; each table below says what was measured and on what machine.

**Machine**: Windows 11, NTFS, single SSD, Python 3.11, Rust 1.7x release build.
Absolute numbers do not transfer to other machines; the *ordering* and the
*shape* of the curves do.

---

## `scorecard_raw.csv` — one battery, nine encodings

Same 65,536-element payload encoded nine ways; nine scored metrics, nineteen
columns in the raw file. Payload `trit` = one balanced trit per element;
`dual` = a `(bit, trit)` pair per element.

### Column dictionary

| column | meaning |
|---|---|
| `encoding` | display name of the encoding |
| `payload` | `trit` or `dual` |
| `bytes_total` | payload bytes only; frame headers are in `encoding_layout.csv` |
| `bits_per_element` | `bytes_total × 8 / 65536` |
| `encode_ns_per_element` | one full write pass, raw Python timing |
| `decode_ns_per_element` | one full decode pass, raw Python timing |
| `decode_ns_net` | `decode_ns_per_element − py_loop_overhead_ns` (one row clamped, see below) |
| `decode_ns_native` | Rust microbenchmark, or the `memcpy` floor for dense formats |
| `random_ns_per_lookup` | 8000 random single-element lookups, raw |
| `random_ns_net` | `random_ns_per_lookup − py_call_overhead_ns` |
| `sparse_ns_per_element` | gather 5% of elements, raw |
| `sparse_ns_net` | `sparse_ns_per_element − py_call_overhead_ns` |
| `selective_bytes` | legacy one-channel minimum from the original harness; scoring uses `selective_bytes_worst` from `encoding_layout.csv` |
| `integrity` | 1 if the container carries a checksum, else 0 |
| `single_object` | 1 if it can be published as one object, else 0 |
| `ops_per_element` | decoder arithmetic/pass count, a machine-independent proxy |
| `py_call_overhead_ns` | calibration: empty Python call |
| `py_loop_overhead_ns` | calibration: empty Python loop |
| `compute_source` | `measured_native` or `memcpy_floor` |

`int8 dense / trit` is clamped: `16.0797 − 19.6823 = −3.60`, so
`decode_ns_net` is pinned at `0.1` and the raw columns show why. Dense rows
marked `memcpy_floor` are an optimistic proxy and therefore bias the comparison
**against** bit-packed formats.

### `data_models.csv` — T / I / X / S

`T` is trit-only; `I` is two independent channels; `X` is one integer with two
projections; `S` is a trit plus a derived bit. Only `I` makes the 6-state symbol
information-optimal.

| Model | Name | Info bits | Dual6 storage | Utilization | Interconvertible | Write semantics |
|---|---|---:|---:|---:|:-:|---|
| T | trit-only | 1.585 | 1.6 bpw | 99.1% | no | update one trit (local) |
| I | independent-dual | 2.585 | 2.6 bpw | 99.4% | no | update bit or trit independently (local) |
| X | exact-dual | 1.000 | 2.6 bpw | 38.5% | yes | recompute the middle symbol block for N |
| S | shadow-projection | 1.585 | 2.6 bpw | 61.0% | no | update trit, recompute derived bit |

`X` is redundant by design: it stores 2.6 bpw to carry at most one bit per
symbol. `S` adds no information in the second channel and is not recommended.

### `encoding_taxonomy.csv` — measured rows mapped to a model

Every row in `scorecard_raw.csv` is tagged with `data_model`: the nine `trit`
rows are `T`, the six `dual` rows are `I`. The table also records the
information bits, storage bits, utilization and write semantics for that row.

### `encoding_layout.csv` — per-channel layout facts

This hand-authored table is the authority for selective reads. `payload_bytes`
must equal `scorecard_raw.csv:bytes_total`; `selective_bytes_worst` is
`max(bit, trit)`, and the scoring model uses that conservative value.

| column | meaning |
|---|---|
| `layout` | `dense_fp16`, `dense_int8`, `packed_5trit`, `packed_2bit`, `slot3`, `dual_plane`, `dual_plane_omit_bit`, `interleaved`, `separate_arrays` |
| `payload_bytes` | payload bytes, excluding the frame header |
| `frame_header_bytes` | 33 for D6P2 frames, 0 for raw arrays/streams |
| `bit_plane_bytes` / `trit_plane_bytes` | bytes in each channel; equal for inseparable layouts |
| `objects` | number of files/objects a consumer must open |
| `selective_bytes_bit` / `selective_bytes_trit` | payload bytes needed by a bit-only / trit-only consumer |
| `selective_bytes_worst` | `max(bit, trit)`, used by the scenario score |
| `notes` | layout caveats |

### Summary — pure-trit payload (9 rows)

| Encoding | bpw | encode ns | decode ns | native/floor ns | random ns | sparse 5% ns | sel bit B | sel trit B | CRC | one object |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 dense | 16.00 | 41.5 | 23.9 | 0.035† | 71.5 | 60.2 | 131072 | 131072 | — | — |
| int8 dense | 8.00 | 35.5 | 0.1 | 0.035† | 21.3 | 14.1 | 65536 | 65536 | — | ✓ |
| TQ1_0 (5 trit/byte) | 1.60 | 85.9 | 59.3 | 0.450 | 90.5 | 77.8 | 13108 | 13108 | — | ✓ |
| TQ2_0 (2 bit/trit) | 2.00 | 88.9 | 48.5 | 0.562 | 62.4 | 57.7 | 16384 | 16384 | — | ✓ |
| 6-state 3-bit slot | 3.00 | 269.6 | 230.4 | 1.015 | 114.1 | 103.5 | 24576 | 24576 | — | ✓ |
| Dual6 dual-plane | 2.60 | 160.6 | 119.1 | 0.448 | 211.5 | 170.5 | 8192 | 13108 | ✓ | ✓ |
| Dual6 dual-plane (trit-only) | 1.60 | 160.5 | 59.2 | 0.448 | 92.4 | 76.6 | 0 | 13108 | ✓ | ✓ |
| Dual6 interleaved (13 bit) | 2.60 | 156.2 | 113.6 | 1.648 | 343.6 | 319.9 | 21301 | 21301 | ✓ | ✓ |
| two separate arrays | 1.60 | 87.3 | 80.0 | 0.448 | 120.1 | 98.8 | 0 | 13108 | — | — |

† `memcpy_floor`, not a real decode.

### Summary — dual payload (6 rows)

| Encoding | bpw | encode ns | decode ns | native/floor ns | random ns | sparse 5% ns | sel bit B | sel trit B | CRC | one object |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 dense | 32.00 | 79.1 | 55.8 | 0.035† | 71.8 | 61.3 | 262144 | 262144 | — | — |
| int8 dense | 16.00 | 55.8 | 11.0 | 0.035† | 26.8 | 12.8 | 131072 | 131072 | — | ✓ |
| 6-state 3-bit slot | 3.00 | 280.3 | 231.7 | 1.015 | 105.0 | 101.2 | 24576 | 24576 | — | ✓ |
| Dual6 dual-plane | 2.60 | 163.3 | 125.6 | 0.448 | 232.0 | 178.5 | 8192 | 13108 | ✓ | ✓ |
| Dual6 interleaved (13 bit) | 2.60 | 167.8 | 112.8 | 1.648 | 330.3 | 319.4 | 21301 | 21301 | ✓ | ✓ |
| two separate arrays | 2.60 | 165.6 | 135.6 | 0.448 | 245.0 | 190.8 | 8192 | 13108 | — | — |

Only six encodings can carry a per-element `(bit, trit)` pair, so the dual table
has six rows.

### What the columns say, without spin

- **Read the table as a trade-off, not a ranking.** The compact layouts
  (`TQ1_0`, `two separate arrays`, trit-only Dual6) sit at 1.60 bpw; `int8`
  trades 5× storage for latency; only the three Dual6 encodings carry a
  checksum.
- **The trit-only frame is `TQ1_0` plus a CRC**: 1.60 bpw, 59.2 vs 59.3 ns
  (−0.3%, inside noise), plus a 32-bit checksum and a single-object frame.
- **`int8` stores 5× more and is 4.87× faster on the raw Python decode**
  (8.00 vs 1.60 bpw; 16.08 vs 78.34 ns/element). The 592× figure is the
  clamped-net upper bound, not a raw measurement.
- **The second channel costs 1.62×** the storage of the trit-only payload
  (2.60 vs 1.60 bpw).
- **Selective read is the structural difference**: on a dual payload the
  dual-plane frame needs **8192 B** for the bit channel and **13108 B** for the
  trit channel. Even the worse channel is far below `int8` (131072 B) and the
  interleaved layout (21301 B, which must read the whole stream).

## `scenario_weights.csv` — policy, not measurement

Five explicit weight sets over the nine scored metrics. Every row sums to 100.
`payload=both` means the scenario is scored separately for the trit and dual
payloads; scores are never compared across payloads. These weights are one of
the two hand-authored inputs in the derived pipeline (the other is
`encoding_layout.csv`).

| Scenario | Payload | bpw | encode | decode | random | sparse | selective | CRC | single | ops |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pure_ternary | trit | 30 | 5 | 20 | 5 | 5 | 5 | 15 | 10 | 5 |
| sparse_gather | both | 20 | 5 | 10 | 15 | 30 | 5 | 5 | 5 | 5 |
| dual_channel | dual | 20 | 5 | 15 | 5 | 10 | 25 | 10 | 5 | 5 |
| checkpoint_hot_swap | both | 10 | 10 | 10 | 20 | 5 | 5 | 20 | 15 | 5 |
| edge_small_model | both | 40 | 10 | 15 | 5 | 5 | 5 | 10 | 5 | 5 |

## `scenario_scores.csv` — generated

For every `(scenario, payload)` group, the nine sub-scores are

```text
score = best_value / this_value      (lower is better)
score = this_value                   (binary metrics: 0 or 1)
weighted_score = 100 × Σ (weight_i / 100) × score_i   (0..100)
```

Every `score_*` column is exported so the weights can be changed without
rerunning the battery. Rank uses standard competition ranking, so ties share a
rank.

| Scenario | Payload | Winner | Score | Runner-up | Score |
|---|---|---|---:|---|---:|
| pure_ternary | trit | Dual6 dual-plane (trit-only) | 64.5 | int8 dense | 57.0 |
| sparse_gather | trit | int8 dense | 75.0 | Dual6 dual-plane (trit-only) | 46.3 |
| sparse_gather | dual | int8 dense | 73.8 | Dual6 dual-plane | 42.7 |
| dual_channel | dual | Dual6 dual-plane | 65.6 | Dual6 interleaved (13 bit) | 55.3 |
| checkpoint_hot_swap | trit | int8 dense | 68.0 | Dual6 dual-plane (trit-only) | 59.0 |
| checkpoint_hot_swap | dual | int8 dense | 67.1 | Dual6 dual-plane | 58.2 |
| edge_small_model | trit | Dual6 dual-plane (trit-only) | 65.6 | TQ1_0 (5 trit/byte) | 58.7 |
| edge_small_model | dual | Dual6 dual-plane | 66.9 | Dual6 interleaved (13 bit) | 64.5 |

## `bandwidth_sweep.csv` — generated

The weight-free model:

```text
bytes_per_element = bits_per_element / 8
memory_ns         = bytes_per_element / bandwidth_gbps   # GB/s -> ns/element
effective_ns      = max(decode_compute_ns, memory_ns)
```

`decode_compute_ns` is `decode_ns_native`; dense formats therefore use their
optimistic `memcpy` floor. Seven bandwidth levels: 1, 3, 10, 30, 100, 300, 1000
GB/s. Ties share rank 1.

| Bandwidth (GB/s) | trit winner(s) | effective ns | dual winner(s) | effective ns |
|---:|---|---:|---|---:|
| 1 | Dual6 dual-plane / Dual6 dual-plane (trit-only) / two separate arrays | 0.448 | Dual6 dual-plane / two separate arrays | 0.448 |
| 3 | int8 dense | 0.333 | Dual6 dual-plane / two separate arrays | 0.448 |
| 10 | int8 dense | 0.100 | int8 dense | 0.200 |
| 30 | int8 dense | 0.035 | int8 dense | 0.067 |
| 100 | fp16 dense / int8 dense | 0.035 | int8 dense | 0.035 |
| 300 | fp16 dense / int8 dense | 0.035 | fp16 dense / int8 dense | 0.035 |
| 1000 | fp16 dense / int8 dense | 0.035 | fp16 dense / int8 dense | 0.035 |

The crossover is a band, not a point: roughly 2–5 GB/s on the trit payload and
4–9 GB/s on the dual payload, depending on which pair is compared. “Storage wins
below 1–3 GB/s, compute wins above 30 GB/s” is the safe outer envelope of these
curves.

## `composite_scores.csv` — generated

Equal weight over the nine measured metrics **plus information utilization**
(10 metrics). `best/value` for lower-is-better metrics, 0/1 for the binary
flags, `utilization/100` for the efficiency metric; the composite is the mean ×
100. This is a descriptive aggregate, not a universal ranking.

| Payload | Rank | Encoding | Util. | Composite |
|---|---:|---|---:|---:|
| trit | 1 | int8 dense | 19.8% | 66.0 |
| trit | 2 | Dual6 dual-plane (trit-only frame) | 99.1% | 58.8 |
| trit | 3 | TQ1_0 (5 trit/byte) | 99.1% | 53.2 |
| trit | 4 | Dual6 dual-plane | 61.0% | 48.8 |
| trit | 5 | TQ2_0 (2 bit/trit) | 79.2% | 48.8 |
| trit | 6 | two separate arrays | 99.1% | 47.2 |
| trit | 7 | Dual6 interleaved (13 bit/5 sym) | 61.0% | 43.7 |
| trit | 8 | 6-state 3-bit slot | 52.8% | 33.8 |
| trit | 9 | fp16 dense | 9.9% | 21.9 |
| dual | 1 | int8 dense | 16.2% | 64.2 |
| dual | 2 | Dual6 dual-plane | 99.4% | 58.6 |
| dual | 3 | Dual6 interleaved (13 bit/5 sym) | 99.4% | 53.6 |
| dual | 4 | two separate arrays | 99.4% | 45.9 |
| dual | 5 | 6-state 3-bit slot | 86.2% | 42.2 |
| dual | 6 | fp16 dense | 8.1% | 22.0 |

## `xs_scores.csv` — generated

X/S have no full measured scorecard. Their decode path is measured in
`xs_decode.csv`; the score uses the **native batch** value (`X_demux` for X;
for S, native trit unpack plus the Python derived-bit pass) and borrows Dual6
dual-plane for encode/random/sparse. `evidence` is `mixed_native_decode`.

| Rank | Encoding | Model | Util. | Composite | Evidence |
|---:|---|---:|---:|---:|---|
| 1 | Dual6/S (shadow-projection) | S | 61.0% | 57.5 | mixed_native_decode |
| 2 | Dual6/X (exact-dual) | X | 38.5% | 56.3 | mixed_native_decode |

## `xs_decode.csv` — measured microbenchmark

Min-of-5 batches, raw ns/element, no loop-baseline subtraction. The native
`X_demux` is the Rust batch demux of the exact-dual symbol stream; the Python
`exact_dual.read_binary/read_ternary` rows are shown for comparison.

| Case | Model | View | ref ns | native ns |
|---|---|---|---:|---:|
| digit_decode | T | symbol | 118.84 | 317.16 |
| I_bit_channel | I | bit | 10.37 | 5.11 |
| I_trit_channel | I | trit | 15.19 | 5.94 |
| I_dual_plane_full | I | both | 28.99 | 18.97 |
| X_demux | X | both | 137.36 | 23.83 |
| X_binary_view | X | bit | 117.98 | 117.45 |
| X_ternary_view | X | trit | 110.39 | 110.84 |
| S_trit_plus_bit | S | trit+derived bit | 39.75 | 30.79 |

`X_demux` native is ~24 ns/element versus ~118 ns for the Python
`exact_dual` view; the Rust batch path is the relevant one for X.
`digit_decode` is a single-symbol call, so native per-call overhead dominates;
compare the batch rows, not that one. `X_binary_view` / `X_ternary_view` are
Python `exact_dual` functions in both backends.

## `information_budget.csv` — generated

Rebuilt from `data_models.csv`; `utilization = info_bits / storage_bits × 100`
and `redundancy_ratio = storage_bits / info_bits`.

| Model | Name | Info bits | Dual6 storage | Utilization | Interconvertible | Write semantics |
|---|---|---:|---:|---:|:-:|---|
| T | trit-only | 1.585 | 1.6 bpw | 99.1% | no | update one trit (local) |
| I | independent-dual | 2.585 | 2.6 bpw | 99.4% | no | update bit or trit independently (local) |
| X | exact-dual | 1.000 | 2.6 bpw | 38.5% | yes | recompute the middle symbol block for N |
| S | shadow-projection | 1.585 | 2.6 bpw | 61.0% | no | update trit, recompute derived bit |

## `decode_ratios.csv` — generated

Ratios against a payload-specific reference (`Dual6 trit-only` for trit,
`Dual6 dual-plane` for dual). `decode_net_clamped` marks rows whose raw decode
is below the Python loop baseline; `int8 dense / trit` is the only such row.

```text
ratio_raw_vs_reference    = reference.decode_ns_per_element / row.decode_ns_per_element
ratio_net_vs_reference    = reference.decode_ns_net / row.decode_ns_net
ratio_native_vs_reference = reference.decode_ns_native / row.decode_ns_native
```

For the trit payload: `int8` is **4.87×** faster raw, **591.75×** faster on the
clamped net value, and **12.80×** faster on the native/floor proxy. The net
ratio is an upper bound; the native ratio uses the dense `memcpy` floor.

## `weight_sensitivity.csv` — generated

Deterministic pseudo-random integer weight vectors over the nine metrics
(5,000 per scheme and payload; three schemes: s1, s2, s3). The generator is
SplitMix64 plus integer normalization; no transcendental functions are used, so
the file is stable across operating systems and Python versions. `wins` and
`share` count how often each encoding has the highest weighted score.

Across the three schemes: `int8` wins 85.6–86.0% of trit draws and 83.5–83.9%
of dual draws; the trit-only frame wins 13.1–13.6%, the dual-plane frame
15.6–16.1%.

## `weight_sweeps.csv` — generated

One-dimensional sweeps that hold the other metrics equal and vary one weight:

- `structural`: `integrity + single_object` weight from 0–100%;
- `storage`: `bits_per_element` weight from 0–100%;
- `selective`: `selective_bytes` weight from 0–100% (dual only).

The winner flips at: trit-only vs `int8` at **45%** structural weight or **30%**
storage weight; dual-plane vs `int8` at **25%** selective weight.

## `model_roundtrip.csv` — real 0.1B model losslessness

One optional artifact experiment: encode a real checkpoint's weights through
Dual6 and compare the decoded model against the **ternary baseline**. The model
weights are not in the repository; only the result row is.

- model: `AI-ModelScope/gpt2` (GPT-2 small, 124,439,808 parameters);
- 65,536 trits per D6P2 trit-only frame;
- `linears`: the 48 transformer linear weights are ternarized; embeddings,
  LayerNorm and biases stay fp16;
- `all_2d`: every 2D weight is ternarized (a format-losslessness stress test).

| Scope | Encoded elements | Dual6 encoded | Dual6 overall | TQ1_0 overall | 2-bit overall | int8 overall | logits exact | top-1 |
|---|---:|---:|---:|---:|---:|---:|:-:|---:|
| all 2D weights | 124,318,464 | 24.9 MB | 1.618 bpw | 1.614 bpw | 2.014 bpw | 8.008 bpw | ✓ | 100% |
| linear layers only | 84,934,656 | 17.0 MB | 6.174 bpw | 6.171 bpw | 6.445 bpw | 10.540 bpw | ✓ | 100% |

Both scopes round-trip every encoded tensor bit-exactly; the decoded model's
logits are bit-identical to the ternary baseline (`max |Δlogit| = 0`,
top-1 = 100%). This validates **storage losslessness only**. It does not
validate model quality: naive absmean ternarization of GPT-2 destroys the
original model (top-1 agreement with fp16 is 3.1% for the linear-only scope and
0% for all-2D). That is a quantization result, not a storage result.

Reproduce (optional; requires `torch`, `transformers`, `modelscope`):

```bash
python -m pip install -e ".[model]"
python tools/model_roundtrip.py --download --scope linears
python tools/model_roundtrip.py --download --scope all_2d
python tools/model_roundtrip.py --check-csv   # offline validation, used in CI
```

## `sparse_plane.csv` — does a compacted bit plane pay off?

`layout 0` (fixed 1.0 bpw bit plane) vs `layout 1` (one flag bit per block,
bitmaps only for blocks that contain a set bit), swept over mask density and
block size.

## `mask_structure.csv` — structure, not density

Five arrangements at exactly the same density (K = 240 of 4800 elements), five
replicates each. `empty_blocks_pct` is the share of 24-symbol blocks with no set
bit.

Headline: clustered masks save **25–33%**; a periodic scatter *costs* 1.5%,
because every block then holds a set bit.

## `fault_size.csv` — why small files do not tear

The same in-place same-size overwrite of a `safetensors`-shaped container,
read 200 times per size. Silent corruption (loader returned data that is not any
published version) appears only once the payload is large enough for the write
to stop being a single atomic-looking operation.

| payload | silent reads |
|---:|---:|
| 4 KiB | 0 |
| 64 KiB | 0 |
| 512 KiB | 3 |
| 2 MiB | 34 |
| 8 MiB | 53 |

## `fault_matrix.csv` — what protects a reader

4 containers × 3 update protocols × 3 loader levels × 5 faults. The only column
that matters is `silent`: the loader returned data that is not any published
version. Measured over 200 concurrent reads per cell.

Containers: `dual6-P0-no-crc`, `dual6-P2-crc`, `safetensors-like`, `gguf-like`.
Protocols: in-place truncating write, in-place same-size overwrite, tmp+rename.
Loaders: bare parse, length check, sha256 check.

---

## Charts

| file | shows |
|---|---|
| `charts/scorecard.png` | storage against decode cost for all nine encodings |
| `charts/sparse-plane.png` | size change vs mask density, three block sizes |
| `charts/mask-structure.png` | size change vs mask structure, 5 replicates with ranges |
| `charts/fault-size.png` | silent corrupt reads vs payload size |
| `charts/scenario-scores.png` | five weight sets × encodings, one panel per payload |
| `charts/bandwidth-crossover.png` | effective ns vs link bandwidth, one panel per payload |
| `charts/weight-sensitivity.png` | win shares and one-dimensional flip sweeps |
| `charts/composite-scores.png` | ten-metric score: T/I measured, X/S measured-decode |
| `charts/information-budget.png` | information vs storage for T / I / X / S |

All nine are generated from the CSVs in this directory:

```bash
pip install matplotlib
python tools/make_scores.py    # regenerate the two derived CSVs first
python tools/make_charts.py    # render all seven charts
```

`python tools/make_scores.py --check` fails if the committed derived CSVs do
not match a fresh computation; the test suite also checks them independently.