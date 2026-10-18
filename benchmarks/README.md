# Measurements

Raw data behind the numbers quoted in the top-level `README.md`. Every file is
a CSV produced by a script; nothing here is hand-typed.

The scripts that produced them live in the private working archive, not in this
repository (they pull in a benchmark harness that is out of scope for a storage
container). The CSV headers are self-describing; each table below says what was
measured and on what machine.

**Machine**: Windows 11, NTFS, single SSD, Python 3.11, Rust 1.7x release build.
Absolute numbers do not transfer to other machines; the *ordering* and the
*shape* of the curves do.

---

## `scorecard_raw.csv` — one battery, nine encodings

Same 65,536-element payload encoded nine ways; nine metrics per encoding.
Payload `trit` = one balanced trit per element; `dual` = a `(bit, trit)` pair.

| column | meaning |
|---|---|
| `bits_per_element` | bytes on disk × 8 / n |
| `decode_ns_net` | full decode, ns per element, empty-loop baseline subtracted |
| `decode_ns_native` | ns per element measured in Rust (`kernel_microbench`), or the memcpy floor for dense formats |
| `random_ns_net` | random single-element lookup |
| `sparse_ns_net` | gather 5% of the elements |
| `selective_bytes` | bytes that must be read to serve one channel only |
| `integrity`, `single_object` | does the container carry a checksum / can it be published as one object |

### Summary

Nine encodings, one battery, two payloads (15 rows). Pure-trit payload:

| Encoding | bpw | decode ns | random ns | sparse 5% ns | selective B | CRC | one object |
|---|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 dense | 16.00 | 23.9 | 71.5 | 60.2 | 131072 | — | — |
| int8 dense | 8.00 | **0.1** | **21.3** | **14.1** | 65536 | — | ✓ |
| TQ1_0 | **1.60** | 59.3 | 90.5 | 77.8 | 13108 | — | ✓ |
| TQ2_0 | 2.00 | 48.5 | 62.4 | 57.7 | 16384 | — | ✓ |
| 6-state 3-bit slot | 3.00 | 230.4 | 114.1 | 103.5 | 24576 | — | ✓ |
| **Dual6 dual-plane** | 2.60 | 119.1 | 211.5 | 170.5 | 13108 | **✓** | ✓ |
| **Dual6 dual-plane (trit-only)** | **1.60** | 59.2 | 92.4 | 76.6 | 13108 | **✓** | ✓ |
| **Dual6 interleaved (13 bit)** | 2.60 | 113.6 | 343.6 | 319.9 | 21301 | ✓ | ✓ |
| two separate arrays | **1.60** | 80.0 | 120.1 | 98.8 | 13108 | — | — |

What the columns say, without spin:

- **no column is swept.** Cheapest storage goes to TQ1_0 / two arrays / the
  trit-only frame; fastest decode, fastest random access and fastest gather all
  go to int8; the only encodings carrying a checksum are the three Dual6 ones.
- **the trit-only frame is TQ1_0 plus a CRC**: 1.60 bpw, 59.2 vs 59.3 ns
  (−0.3%, inside noise), plus a 32-bit checksum and a single-object frame.
- **int8 decodes 592× faster and stores 5× more.** That ratio is the whole
  trade-off in one line.
- **the dual payload costs 1.62×** the storage of the trit-only one
  (2.60 vs 1.60 bpw) — that is what the second channel is worth.
- **selective read is the one structural difference**: on a dual payload the
  dual-plane frame needs **8192 B** to serve one channel, while int8 needs
  131072 B and the interleaved layout 21301 B, because those layouts weave the
  channels together.

Full digest: `scorecard_raw.csv` (15 rows × 13 columns).

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

All four are generated from the CSVs in this directory:

```bash
pip install matplotlib
python tools/make_charts.py
```
