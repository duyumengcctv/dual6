# 11 · Exact-Dual 编解码（同一数值，双视图无损读取）

> **状态：已实现，作为可选子模块 `dual6.exact_dual`，不属于核心容器 API。**
> 核心容器仍是"两条独立通道的共享存储"（`docs/00`）；本编解码建在同一个
> 6 态码元 `d = 3b + (t+1)` 之上。

## 1. 目标

一个非负整数 `N`，只存一份码元序列，满足：

- 二进制引擎只做 `d // 3`，能还原 `N`；
- 三进制引擎只做 `d % 3 - 1`，也能还原 `N`；
- 读取时**不做任何跨进制转换**；
- 两个视图都**无损**。

## 2. 编码

```text
b_i = N 的第 i 位 base-2 数字           (0/1)
t_i = N 的第 i 位 balanced-base-3 数字  (-1/0/+1)
d_i = 3*b_i + (t_i + 1)                (0..5)
```

长度：

```text
L = max(len(base2_digits(N)), len(balanced3_digits(N)))
```

较短的展开用 0 补齐。因为 `len(balanced3) ≈ 0.631 * len(base2)`，通常
`L == len(base2_digits(N))`。

## 3. 读取

```text
二进制视图：b_i = d_i // 3   →   N = Σ b_i · 2^i
三进制视图：t_i = d_i % 3 - 1 →   N = Σ t_i · 3^i
```

两个式子都只依赖 `d_i` 和各自的幂次，**不需要知道对方的进制**。

## 4. 长度与填充

- 必须记录码元数 `L`（帧里的 `width`，或 `len(symbols)`）。
- 补零必须补 **`d = 1`**（Dual6 的零：`b=0, t=0`），不能补 `d = 0`
  （那是 `b=0, t=-1`）。
- 截断码元会改变数值；补 `d=1` 不改变数值。

## 5. 三种"双通道"模式要区分

| 模式 | 两通道内容 | 能否互相还原 | 状态 |
|---|---|---|---|
| **independent-dual**（核心） | 两条**不同**的真实数据（如三值权重 + 路由位） | 否，各读各的 | 已实现 |
| **exact-dual**（本文） | 同一个 `N` 的两种展开 | **是，都无损** | 已实现（可选模块） |
| **shadow-projection** | 主值 + 派生位（如 `b_i = (t_i != 0)`） | 否，影子有损 | 未定义 |

`exact-dual` 不能同时把 bit 通道拿去放独立路由位——那是另一种模式。

## 6. 代价

以 `N = 2^64 + 12345`（`L = 65`）为例：

| 存法 | 字节 |
|---|---:|
| 只存二进制 | 9 |
| 只存平衡三进制（41 trit，5/byte） | 9 |
| **exact-dual 交错**（`Σ d_i·6^i`） | **21** |
| exact-dual 双平面 | 22 |
| exact-dual 3-bit slot | 25 |

- 相对单通道约 **2.3–2.8x**；相对纯三值约 **2.3x**。
- 信息利用率约 `1 / log2(6) ≈ 38.7%`：码元空间能装 `2.585L` bit，
  但只用来表示 `N < 2^L`：每个码元的两个分量都在描述同一个 `N`，冗余
  发生在**码元内部**，不是两份拷贝。
- 时间：写入时**编码器内部**算出两个分量并压进同一串码元（调用方只给
  一个表示）；读取是 `O(L)` 的逐位取值 + 加权求和。

所以它是**用冗余存储换"读时零转换 + 双视图无损"**，不是压缩格式。

### 6.1 存的是"一个值"，不是"两份数据"

写入后只留下一串码元（或一个容器整数 `D`）。"两个展开"指的是每个码元
同时承载 `b_i` 和 `t_i` 两个分量，是**单个码元内部**的结构，不是两份拷贝。

```text
N = 42
  -> symbols [1, 3, 0, 3, 2, 4]
  -> D = 34363 (一个整数, 0x863B)

D -> 同一串码元 -> d // 3   -> 42
D -> 同一串码元 -> d % 3-1  -> 42
```

## 7. 浮点 / 字节

浮点和字节按**位模式**编码，而不是按数值语义：

```python
N = int.from_bytes(struct.pack("<d", value), "little")   # f64
N = int.from_bytes(data, "little")                        # bytes
```

两个视图都能还原出**完全相同的字节**，因此 `float` / `bytes` 也是无损的。
但注意：三进制视图拿到的是"IEEE-754 位模式的平衡三进制展开"，不是
"三进制浮点数"。要三进制浮点，需要另外定义浮点编解码。

## 8. 负数

v1 只接受非负整数。平衡三进制天然支持负数，但二进制需要额外的宽度/符号
约定（二补码或符号位），因此负数留给后续版本显式定义。

## 9. API

### 9.1 推荐用法：一边转换，另一边自动解码

调用方只给**一个**表示；编码结果是一串码元（一个容器整数），不是两份数据：

```python
from dual6.exact_dual import from_bits, to_trits, from_trits, to_bits, to_int

# 二进制引擎 -> 三进制引擎
symbols = from_bits([0, 1, 0, 1, 0, 1])   # 只给 bits
to_trits(symbols)                          # 自动解码出 trits
to_int(symbols)                            # 42

# 三进制引擎 -> 二进制引擎
symbols = from_trits([0, -1, -1, -1, 1])   # 只给 trits
to_bits(symbols)                           # 自动解码出 bits
to_int(symbols)                            # 42
```

`from_bits` / `from_trits` 内部会展开成两个视图并配对；调用方不用关心
另一个通道。

### 9.2 底层 API

```python
from dual6.exact_dual import (
    encode_number, read_binary, read_ternary,
    to_binary_digits, to_balanced_ternary, from_balanced_ternary,
    encode_f64, decode_f64, encode_bytes, decode_bytes,
)

symbols = encode_number(42)      # [1, 3, 0, 3, 2, 4]
read_binary(symbols)             # 42
read_ternary(symbols)            # 42
```

错误：

- 负数 / 非整数 → `Dual6Error(INVALID_PACKING)`
- 非法码元 → `Dual6Error(INVALID_DIGIT)`
- 非法 trit → `Dual6Error(INVALID_TRIT)`
- 字节长度不够 → `Dual6Error(INVALID_LAYOUT)`

## 10. 示例 N = 42

```text
N = 42
  二进制展开    : 101010
  平衡三进制展开: +---0
  码元 (LSB first): [1, 3, 0, 3, 2, 4]
  二进制视图读回: 42
  三进制视图读回: 42
```

## 11. 非目标

- 不做有损影子投影（另立规范）；
- 不做三进制浮点；
- 不把负数 / 定点数纳入 v1；
- 不进入核心容器的冻结 API（`docs/08`）。
