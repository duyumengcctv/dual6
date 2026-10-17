# 04 · 帧

## D6P0

```text
offset  size  field
0       4     magic = "D6P0"
4       1     version = 1
5       4     width n          (u32 LE)
9       4     bit_bytes_len    (u32 LE)
13      4     trit_bytes_len   (u32 LE)
17      ...   bit plane bytes
...     ...   trit plane bytes
```

约束：

```text
bit_bytes_len  == ceil(n / 8)
trit_bytes_len == ceil(n / 5)
```

D6P0 无 CRC，保留用于兼容。

## D6P1

```text
offset  size  field
0       4     magic = "D6P1"
4       1     version = 1
5       1     layout = 0      (dual-plane)
6       2     reserved = 0
8       4     width n          (u32 LE)
12      4     payload_len      (u32 LE)
16      4     crc32            (u32 LE)
20      ...   payload
```

CRC32 计算：

- 先把 CRC 字段置 0；
- 对 `header + payload` 计算标准 CRC32；
- 将结果写回 CRC 字段。

错误：

- CRC 不匹配返回 `CRC_MISMATCH`；
- magic / layout / reserved / length 非法返回 `INVALID_LAYOUT`；
- 版本不支持返回 `UNSUPPORTED_VERSION`。

## D6P2

```text
offset  size  field
0       4     magic = "D6P2"
4       1     version = 1
5       1     layout = 0      (dual-plane)
6       1     dtype           (0 raw, 1 binary, 2 ternary, 3 mixed)
7       2     flags
9       4     width n          (u32 LE)
13      4     block_symbols    (0 = no block split)
17      4     block_bytes
21      4     block_count
25      4     payload_len
29      4     crc32
33      ...   payload
```

`flags` 字段：

| bit | 名称 | 含义 |
|---:|---|---|
| 0 | `FLAG_OMIT_BIT_PLANE` | **payload 不含 bit 平面**（纯三值帧） |

当 bit 0 置位时：

- 所有 bit 必须为 0，否则返回 `INVALID_BIT`（避免静默丢失数据）；
- payload 只有 trit 平面，长度 `ceil(n/5)`（块模式为 `ceil(block_symbols/5)`）；
- 读回时 `bits = [0] * n`；
- 存储从 **2.6 bpw 降到 1.6 bpw**，与 `TQ1_0` 持平。

未置位时行为与 v0.3 完全一致（向后兼容）。

规则：

- `block_symbols = 0` 时，payload 是一个完整双平面流；
- `block_symbols > 0` 时，payload 是固定大小的双平面块；
- `block_count * block_symbols == width`；
- `block_bytes == ceil(block_symbols/8) + ceil(block_symbols/5)`；
- CRC32 规则同 D6P1。

## D6P2 layout 1：压缩 bit 平面

`layout = 1` 只允许 `block_symbols > 0`，payload 顺序为：

```text
block flags    ceil(block_count / 8) 字节   第 i 位 = 第 i 块带位图
bitmaps        ceil(block_symbols / 8) 字节 × 带 flag 的块数
trit plane     ceil(block_symbols / 5) 字节 × block_count，连续存放
```

规则：

- flag 为 0 的块，其 bit 通道全为 0，不占 bitmap 字节；
- `block_bytes` 字段此时等于 **trit 平面每块的字节数** `ceil(bs/5)`；
- `payload_len` 必须等于 `flags + 有 bitmap 的块数 × ceil(bs/8) + block_count × block_bytes`；
- trit 平面的字节与 layout 0 **完全相同且连续**；
- 多字节字段一律 **little-endian**。

掩码越稀疏、越聚集，收益越大；当每个块都含有置位时反而略大。

## 模块

```text
python/dual6/_ref/frame.py
crates/dual6-core/src/frame.rs
```

## D6P3（草案）

带 `element_type` / `shape` 的张量帧目前只是提案，未实现，也不在 v0.3
API 中。
