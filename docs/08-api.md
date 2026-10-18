# 08 · API 冻结与版本

## 稳定层

以下接口视为 Dual6 工具本身的核心 API。

### Python

```python
encode_digit / decode_digit
mux / demux

pack_digits / unpack_digits
max_interleaved / fits_unsigned_word

pack_bits_bytes / unpack_bits_bytes
pack_trits_bytes / unpack_trits_bytes
pack_bits_into / pack_trits_into
pack_dual_plane_into / unpack_dual_plane_from

pack_block64 / unpack_block64
pack_block64_many / unpack_block64_many
pack_block64_many_into / unpack_block64_many_into
pack_block128 / unpack_block128
pack_block40 / unpack_block40

pack_block64_dp / unpack_block64_dp
pack_block128_dp / unpack_block128_dp
pack_block40_dp / unpack_block40_dp

pack_dual_plane / unpack_dual_plane
pack_dual_plane_v1 / unpack_dual_plane_v1
pack_dual_plane_v2 / unpack_dual_plane_v2

frame_version / unpack_frame_auto
unpack_frame_auto_buffer

# 单通道桥接（规范路径是 dual6.adapters，顶层同名再导出）
bits_to_symbols / symbols_to_bits
trits_to_symbols / symbols_to_trits
bits_to_dual6_block64 / dual6_block64_to_bits
trits_to_dual6_block64 / dual6_block64_to_trits
```

### Rust

```rust
dual6_core::encode_digit / decode_digit
dual6_core::mux / demux
dual6_core::pack_digits / unpack_digits
dual6_core::pack_block64 / unpack_block64
dual6_core::pack_block128 / unpack_block128
dual6_core::pack_block40 / unpack_block40
dual6_core::pack_block64_dp / unpack_block64_dp
dual6_core::pack_block128_dp / unpack_block128_dp
dual6_core::pack_block40_dp / unpack_block40_dp
dual6_core::pack_dual_plane / unpack_dual_plane
dual6_core::pack_dual_plane_v1 / unpack_dual_plane_v1
dual6_core::pack_dual_plane_v2 / unpack_dual_plane_v2
dual6_core::frame_version / unpack_frame_auto
```

### CLI

```text
--version
info
encode
decode
pack-block64 / unpack-block64
pack-block64-dp / unpack-block64-dp
pack-frame
unpack-frame
inspect-frame
```

### C ABI（batch）

```c
int32_t dual6_pack_block64_many(const uint8_t *symbols, size_t n_symbols,
                                uint8_t *out, size_t out_capacity);
int32_t dual6_unpack_block64_many(const uint8_t *data, size_t n_bytes,
                                  uint8_t *out, size_t out_capacity);
```

返回写入的字节数 / 符号数，或负的状态码（`DUAL6_ERR_*`）。头文件：
`crates/dual6-ffi/include/dual6.h`。

## 可选编解码（非冻结核心）

`dual6.exact_dual` 提供"同一个数 N 的双展开"编解码，属于容器之上的可选层，
不改变核心容器"`d` 上无算术"的边界：

```python
from dual6.exact_dual import (
    encode_number, read_binary, read_ternary,
    to_binary_digits, to_balanced_ternary, from_balanced_ternary,
    encode_f64, decode_f64, encode_bytes, decode_bytes,
)
```

详见 `docs/11-exact-dual.md`。

`dual6.arithmetic` 是**验证辅助**，不是工具功能：它只用于核对 exact-dual
两个视图是否同步（算术本身属于两端引擎）。

```python
from dual6.arithmetic import add, sub, mul, divmod, add_digits
```

详见 `docs/12-arithmetic.md`。

## 提案（未实现，不在本 API）

- **D6P3 张量帧**（提案，未实现）：只定义 `element_type` /
  `shape` / `flags` / opaque payload 的承载格式。没有对应 Python / Rust
  API，`frame_version()` 也还不返回 3。

## 范围外（本版本不做）

Dual6 v0.3 只交付存储工具本身。以下内容**不属于**本仓库的 API，也不提供实现：

```text
外部系统 / 模型运行时连接
TQ1_0 / TQ2_0 等 GGML block 适配
GGUF 头 / metadata / tensor info 解析
GGUF ↔ Dual6 互操作
量化 / 反量化与 AI / 大模型对接
```

需要这些能力的下游项目，请在冻结的 core API（容器层 + 二进制 / 三进制单通道
桥接）之上自行构建。

## 输入校验

- bit 必须是整数 `0` / `1`，trit 必须是整数 `-1` / `0` / `1`，码元必须是整数
  `0..5`；越界返回对应的 `INVALID_BIT` / `INVALID_TRIT` / `INVALID_DIGIT`。
- `bool` 是 `int` 的子类，两个后端都按 `0` / `1` 接受。
- 浮点（例如 `1.0`）、字符串等非整数一律拒绝，不会因为 `1.0 == 1` 被静默接受。
- 参考实现和 native 扩展对同一非法输入必须抛出**相同错误码**；该约束由
  `python/dual6/_conformance.py` 和 `tests/test_input_validation.py` 覆盖。
- `unpack_digits` / `max_interleaved` 的宽度上限为 1,000,000 个码元；
  超限返回 `INVALID_PACKING`，不会尝试物化 `6 ** width`。
- `fits_unsigned_word` 对超大 `word_bits` 走 log2 比较，不会物化
  `1 << word_bits`。

## 版本规则

```text
version 唯一来源：Cargo.toml [workspace.package].version
Python __version__ 必须一致
pyproject.toml 必须一致
dual6-py Cargo.toml 必须一致
```

检查：

```bash
python tools/check_version.py
```
