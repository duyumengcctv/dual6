# 03 · 布局

## 交错布局

```text
D = Σ d_i * 6^i
```

- LSB first；
- 5 个码元 -> 13 bit；
- 24 个码元可放进 64-bit word；
- `D >= 6^n` 返回 `INVALID_PACKING`。

## 双平面布局

```text
bit 平面：n bit，LSB first
trit 平面：5 trits / byte，LSB first
```

优点：

- 二进制引擎只读 bit 平面；
- 三进制引擎只读 trit 平面。

## 固定块

| 布局 | 码元 | 字节 | 实际使用 |
|---|---:|---:|---:|
| `D6-64` | 24 | 8 | 63 bit |
| `D6-128` | 48 | 16 | 125 bit |
| `D6-40` | 40 | 13 | 104 bit |

## 双平面固定块

三个块刚好整除：

| 布局 | 码元 | bit 平面 | trit 平面 | 总计 |
|---|---:|---:|---:|---:|
| `D6-64-DP` | 24 | 3 byte | 5 byte | 8 byte |
| `D6-128-DP` | 48 | 6 byte | 10 byte | 16 byte |
| `D6-40-DP` | 40 | 5 byte | 8 byte | 13 byte |

二进制引擎只读前段 bit 平面；三进制引擎只读后段 trit 平面。

纯三值负载可以用 `FLAG_OMIT_BIT_PLANE` 省略 bit 平面（见 `docs/04`），
此时存储为 1.6 bpw，与 `TQ1_0` 相同。

## 模块

```text
python/dual6/_ref/interleaved.py
python/dual6/_ref/dual_plane.py
python/dual6/_ref/blocks.py
```
