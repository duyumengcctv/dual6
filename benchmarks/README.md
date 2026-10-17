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

Headline: `Dual6 dual-plane (trit-only frame)` stores **1.60 bpw** and decodes at
**59.2 ns/element**, versus TQ1_0 at 1.60 bpw / 59.3 ns — the same byte layout,
plus a CRC and a frame header.

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
| `charts/16-sparse-plane.png` | size change vs mask density, three block sizes |
| `charts/18-fault-size.png` | silent corrupt reads vs payload size |
| `charts/19-mask-structure.png` | size change vs mask structure, 5 replicates with ranges |

All three can be reproduced from the CSVs in this directory with any plotting
library; the axes and the underlying numbers are the CSV columns.
