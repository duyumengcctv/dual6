# Measurements

Raw data behind the numbers quoted in the top-level `README.md`. Every
measurement file is a CSV produced by a script; the one exception is
`scenario_weights.csv`, which is the hand-authored policy input for the
scenario model.

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
| `bytes_total` | on-disk payload bytes, frame/header included |
| `bits_per_element` | `bytes_total × 8 / 65536` |
| `encode_ns_per_element` | one full write pass, raw Python timing |
| `decode_ns_per_element` | one full decode pass, raw Python timing |
| `decode_ns_net` | `decode_ns_per_element − py_loop_overhead_ns` (one row clamped, see below) |
| `decode_ns_native` | Rust microbenchmark, or the `memcpy` floor for dense formats |
| `random_ns_per_lookup` | 8000 random single-element lookups, raw |
| `random_ns_net` | `random_ns_per_lookup − py_call_overhead_ns` |
| `sparse_ns_per_element` | gather 5% of elements, raw |
| `sparse_ns_net` | `sparse_ns_per_element − py_call_overhead_ns` |
| `selective_bytes` | bytes that must be read to serve one channel only |
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

### Summary — pure-trit payload (9 rows)

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

† `memcpy_floor`, not a real decode.

### Summary — dual payload (6 rows)

| Encoding | bpw | encode ns | decode ns | native/floor ns | random ns | sparse 5% ns | selective B | CRC | one object |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 dense | 32.00 | 79.1 | 55.8 | 0.035† | 71.8 | 61.3 | 262144 | — | — |
| int8 dense | 16.00 | 55.8 | 11.0 | 0.035† | 26.8 | 12.8 | 131072 | — | ✓ |
| 6-state 3-bit slot | 3.00 | 280.3 | 231.7 | 1.015 | 105.0 | 101.2 | 24576 | — | ✓ |
| Dual6 dual-plane | 2.60 | 163.3 | 125.6 | 0.448 | 232.0 | 178.5 | 8192 | ✓ | ✓ |
| Dual6 interleaved (13 bit) | 2.60 | 167.8 | 112.8 | 1.648 | 330.3 | 319.4 | 21301 | ✓ | ✓ |
| two separate arrays | 2.60 | 165.6 | 135.6 | 0.448 | 245.0 | 190.8 | 8192 | — | — |

Only six encodings can carry a per-element `(bit, trit)` pair, so the dual table
has six rows.

### What the columns say, without spin

- **No column is swept.** Cheapest storage goes to `TQ1_0`, `two separate
  arrays` and the trit-only frame; fastest encode, decode, random access and
  gather all go to `int8`; the only encodings carrying a checksum are the three
  Dual6 ones.
- **The trit-only frame is `TQ1_0` plus a CRC**: 1.60 bpw, 59.2 vs 59.3 ns
  (−0.3%, inside noise), plus a 32-bit checksum and a single-object frame.
- **`int8` decodes 592× faster and stores 5× more** (8.00 vs 1.60 bpw on the
  trit payload). That ratio is the whole trade-off in one line.
- **The second channel costs 1.62×** the storage of the trit-only payload
  (2.60 vs 1.60 bpw).
- **Selective read is the structural difference**: on a dual payload the
  dual-plane frame needs **8192 B** to serve one channel, while `int8` needs
  131072 B and the interleaved layout 21301 B.

## `scenario_weights.csv` — policy, not measurement

Five explicit weight sets over the nine scored metrics. Every row sums to 100.
`payload=both` means the scenario is scored separately for the trit and dual
payloads; scores are never compared across payloads. These weights are the one
hand-authored input in the derived pipeline.

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
| sparse_gather | dual | int8 dense | 73.6 | Dual6 dual-plane | 42.7 |
| dual_channel | dual | Dual6 dual-plane | 65.6 | two separate arrays | 54.1 |
| checkpoint_hot_swap | trit | int8 dense | 68.0 | Dual6 dual-plane (trit-only) | 59.0 |
| checkpoint_hot_swap | dual | int8 dense | 66.9 | Dual6 dual-plane | 58.2 |
| edge_small_model | trit | Dual6 dual-plane (trit-only) | 65.6 | TQ1_0 (5 trit/byte) | 58.7 |
| edge_small_model | dual | Dual6 dual-plane | 66.9 | Dual6 interleaved (13 bit) | 63.3 |

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

All six are generated from the CSVs in this directory:

```bash
pip install matplotlib
python tools/make_scores.py    # regenerate the two derived CSVs first
python tools/make_charts.py    # render all six charts
```

`python tools/make_scores.py --check` fails if the committed derived CSVs do
not match a fresh computation; the test suite also checks them independently.
