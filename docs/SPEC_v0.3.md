> **历史文档**：本文件描述 v0.3 早期容器规范。当前实现已包含 D6P1、D6P2、CLI、适配层、双平面固定块；以 `README.md` 和 `docs/00` ~ `docs/13` 为准。

# Dual6 v0.3 — 纯存储容器规范

> 6 态容器不是计算进制，而是 `(bit, trit)` 的联合存储容器。  
> 计算分别交给二进制引擎和三进制引擎，容器本身不做算术。

> 术语：本文称 `d` 为 **Dual6 码元 / 6 态码元**；`digit` 是参考实现里的 API 名。
> 只有底层按 6 的幂次打包时，才使用 **base-6 打包** 这个说法；这不是普通 base-6 数值算术。

---

## 0. 定位

Dual6 v0.3 只负责：

- 单码元 `(bit, trit) -> d` 的 mux / demux；
- 把 `n` 个 Dual6 码元打包成字节流或整型容器；
- 定义位序、端序、宽度、边界和错误码；
- 让二进制引擎只读 bit 平面，三进制引擎只读 trit 平面。

Dual6 v0.3 不负责：

- 普通 base-6 整数算术；
- `d` 上的加减乘除；
- 二进制 / 三进制之间的数值进制转换；
- 浮点、张量或推理语义。

需要数值翻译时，使用独立的 CRT 数值桥，不要混入容器层。

---

## 1. 基础编码

### 1.1 mux

```text
d = bit * 3 + (trit + 1)
```

### 1.2 demux

```text
bit  = d // 3
trit = d % 3 - 1
```

### 1.3 编码表

| d | bit | trit | 含义 |
|---:|---:|---:|---|
| 0 | 0 | -1 | 0T |
| 1 | 0 | 0 | 0 |
| 2 | 0 | +1 | 0P |
| 3 | 1 | -1 | 1T |
| 4 | 1 | 0 | 1 |
| 5 | 1 | +1 | 1P |

### 1.4 性质

- 6 种状态全部用满；
- mux / demux 均为 O(1)；
- `d` 是 6 态码元，是容器索引，不是数值大小；
- `d` 上不定义算术。

注意：Dual6 的零是 `(bit=0, trit=0)`，对应每个码元 `d=1`。  
因此宽度为 `n` 的 Dual6 字的零是：

```text
[1, 1, 1, ..., 1]
```

而不是全 0。

---

## 2. 数据模型

一个宽度为 `n` 的 Dual6 字：

```text
bits  = [b_0, b_1, ..., b_{n-1}]     b_i ∈ {0, 1}
trits = [t_0, t_1, ..., t_{n-1}]     t_i ∈ {-1, 0, +1}

digits[i]（码元） = d_i = 3*b_i + (t_i + 1)
```

默认 **LSB 在前**。

两个通道的值：

```text
B = Σ b_i * 2^i
T = Σ t_i * 3^i
```

`T` 是平衡三进制整数，范围：

```text
-(3^n - 1) / 2  ≤  T  ≤  +(3^n - 1) / 2
```

再次强调：

```text
D = Σ d_i * 6^i 是容器数值，不是普通 base-6 数值。
```

---

## 3. 存储布局

Dual6 v0.3 提供两种布局。

### 3.1 交错布局 Interleaved

直接把码元序列按 base-6 打包：

```text
D = Σ d_i * 6^i
```

特性：

| 项 | 值 |
|---|---|
| 5 个码元占用 | 13 bit |
| 6^5 | 7776 ≤ 8192 = 2^13 |
| 有效码空间 | 7776 / 8192 = 94.92% |
| 信息密度 | log2(7776) / 13 = 99.42% |

24 个码元可以放进一个 64-bit word：

```text
6^24 - 1 < 2^63
6^25 - 1 > 2^64
```

非法码点：

```text
D ≥ 6^n  →  INVALID_PACKING
```

### 3.2 双平面布局 Dual-Plane

两个通道分开连续存储。

#### bit 平面

- `n` 个 bit；
- LSB first；
- 按字节小端打包；
- 最后一个字节未用高位必须为 0。

#### trit 平面

- 每 5 个 trit 装进 1 byte；
- trit `t` 先映射为 base-3 digit `t+1 ∈ {0,1,2}`；
- 组内顺序 LSB first：
  ```text
  v = Σ (t_j + 1) * 3^j,  j = 0..4
  ```
- 最后一个不完整组，未用位置为 0；
- 合法字节值必须小于 `3^used`，否则 `INVALID_LAYOUT`。

#### 帧格式

双平面序列化帧：

```text
offset  size  field
0       4     magic = "D6P0"
4       1     version = 1
5       4     width n          (little-endian u32)
9       4     bit_bytes_len    (little-endian u32)
13      4     trit_bytes_len   (little-endian u32)
17      ...   bit plane bytes
...     ...   trit plane bytes
```

字段约束：

```text
bit_bytes_len  == ceil(n / 8)
trit_bytes_len == ceil(n / 5)
```

### 3.3 固定块布局 Fixed Blocks

推荐用固定块做跨引擎共享内存。当前定义三种：

| 名称 | 码元数 | 字节数 | 实际使用 | 信息密度 |
|---|---:|---:|---:|---:|
| `D6-64` | 24 | 8 | 63 bit | 96.94% |
| `D6-128` | 48 | 16 | 125 bit | 96.94% |
| `D6-40` | 40 | 13 | 104 bit | 99.42% |

规则：

- 块内是 `D = Σ d_i * 6^i` 的小端字节表示；
- `D6-64` 使用 24 个码元，`6^24 < 2^63`，最高位恒为 0；
- `D6-128` 使用 48 个码元，`6^48 < 2^125`，最高 3 位恒为 0；
- `D6-40` 使用 40 个码元，占 13 byte，即 104 bit；
- 反序列化时若 `D ≥ 6^码元数`，返回 `INVALID_PACKING`；
- 块长度不匹配返回 `INVALID_LAYOUT`。

API：

```python
pack_block(symbols, layout) -> bytes
unpack_block(data, layout) -> list[int]

pack_block64(symbols) -> bytes
unpack_block64(data) -> list[int]

pack_block128(symbols) -> bytes
unpack_block128(data) -> list[int]

pack_block40(symbols) -> bytes
unpack_block40(data) -> list[int]
```

---

## 4. 位序与端序

| 项 | 规则 |
|---|---|
| 码元顺序 | LSB first |
| bit 顺序 | LSB first |
| trit 顺序 | LSB first |
| trit 组内顺序 | `t_0` 对应 `3^0` |
| 帧头整数 | little-endian |
| 交错布局 | `D` 的低位对应 `d_0` |

---

## 5. 宽度与边界

- 所有容器操作必须显式带宽度 `n`；
- `n = 0` 合法，表示空字；
- 交错布局：`0 ≤ D < 6^n`；
- bit 平面：`0 ≤ B < 2^n`；
- trit 平面：规范平衡三进制，范围 `[-(3^n-1)/2, +(3^n-1)/2]`；
- 不做隐式截断；越界返回错误；
- 两通道宽度不一致时返回 `WIDTH_MISMATCH`。

---

## 6. 错误码

| 错误码 | 含义 |
|---|---|
| `OK` | 成功 |
| `INVALID_DIGIT` | 码元不在 `0..5` |
| `INVALID_PACKING` | 整型容器值超出 `6^n` |
| `WIDTH_MISMATCH` | bit / trit 宽度不一致 |
| `INVALID_BIT` | bit 不在 `{0,1}` |
| `INVALID_TRIT` | trit 不在 `{-1,0,1}` |
| `INVALID_LAYOUT` | 字节流长度、magic 或填充位非法 |
| `UNSUPPORTED_VERSION` | 帧版本不支持 |

Python 参考实现中，错误以 `Dual6Error` 抛出，`error.code` 保存错误码。

---

## 7. API

### 7.1 单码元

```python
encode_digit(bit, trit) -> int
decode_digit(d) -> (bit, trit)
```

### 7.2 序列

```python
mux(bits, trits) -> list[int]
demux(digits) -> (list[int], list[int])
```

### 7.3 交错布局

```python
pack_digits(digits) -> int
unpack_digits(x, width) -> list[int]
max_interleaved(width) -> int
fits_unsigned_word(width, word_bits) -> bool
```

### 7.4 双平面字节

```python
pack_bits_bytes(bits) -> bytes
unpack_bits_bytes(data, width) -> list[int]

pack_trits_bytes(trits) -> bytes
unpack_trits_bytes(data, width) -> list[int]

pack_dual_plane(bits, trits) -> bytes
unpack_dual_plane(data) -> (list[int], list[int])
```

---

## 8. 跨引擎共享规则

1. 写入方只负责生成 Dual6 容器；
2. 二进制引擎只读 bit 平面；
3. 三进制引擎只读 trit 平面；
4. 两个引擎不需要理解对方通道的语义；
5. 双方必须使用相同版本和布局；
6. 长度、magic、填充位必须校验；
7. 建议按 64/128-bit 块对齐；
8. 纯三进制数据没有免费的二进制通道，纯二进制数据也没有免费的三进制通道。

---

## 9. 测试

参考测试覆盖：

- 单码元 6 种组合编解码；
- mux / demux 往返；
- 5 个码元交错布局全部 7776 种往返；
- n=4..24 随机交错布局往返；
- bit 平面字节往返；
- trit 平面 5-trit/byte 往返；
- 双平面帧往返；
- 非法码元、非法 packing、宽度不匹配、非法填充位；
- 24 个码元 / 64-bit word 容量；
- 固定块 `D6-64`、`D6-128`、`D6-40` 往返和边界。

运行：

```bash
python -m unittest -v
```

---

## 10. 版本

```text
Dual6 Container Spec v0.3.0
```
