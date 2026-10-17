# 12 · 可选算术层（exact-dual）——验证辅助，不是工具功能

> **状态：验证辅助，不属于工具功能。**
> 这个工具是"两端引擎各算各的、通过 Dual6 交换、读取无损"的交换层。
> 算术属于两端引擎（二进制 ALU / 三进制引擎）；`dual6.arithmetic`
> 只用于在测试和演示里核对"两个视图是否仍然同步"，不应被当成容器
> 提供的计算能力。
>
> 核心容器仍不对单个码元 `d` 定义算术；本层只作用于 **exact-dual 序列**
> （两个视图解码到同一个整数 `N`）。

## 1. 为什么需要限定

两种模式必须分清：

| 模式 | 两通道内容 | 能否做同一个数的算术 |
|---|---|---|
| independent-dual | 两路不同数据 | ❌ 两个视图不是同一个值 |
| **exact-dual** | 同一个 `N` 的两种展开 | ✅ 两个视图始终同步 |

`dual6.arithmetic` 只接受 exact-dual 序列：解码后两个视图必须相等，否则
抛 `INVALID_LAYOUT`。

## 2. API

```python
from dual6.arithmetic import add, sub, mul, divmod, add_digits
from dual6.exact_dual import encode_number, read_binary, read_ternary

a = encode_number(42)
b = encode_number(7)

add(a, b)        # 49 的 exact-dual 序列
sub(a, b)        # 35
mul(a, b)        # 294
divmod(a, b)     # (encode(6), encode(0))
add_digits(a, b) # 逐位进位版本，结果与 add 相同
```

## 3. 两种实现

### 3.1 值级（`add` / `sub` / `mul` / `divmod`）

```text
1. 解出两个操作数的 N（并校验两个视图一致）
2. 用 Python 整数计算
3. 重新编码成 exact-dual 序列
```

优点：简单、正确。缺点：没有利用"双通道并行"。

### 3.2 逐位进位（`add_digits`）

```text
二进制通道：0/1 相加，二进制进位
三进制通道：-1/0/+1 相加，平衡三进制进位
              t > 1  -> t-3, carry +1
              t < -1 -> t+3, carry -1
两个通道各自进位后重新配对
```

两个视图必须仍然相等，否则抛 `INVALID_LAYOUT`。

实测：`add_digits` 与 `add` 在 `0..29999` 随机 1000 组上结果完全一致。

## 4. 例子：42 + 7

```text
42 的码元: [1, 3, 0, 3, 2, 4]   (LSB first)
 7 的码元: [5, 3, 5]

二进制展开:   101010 + 111 = 110001          (49)
平衡三进制:   PTTT0 + PTP  = PTTPP           (49, MSB first, P=+1 T=-1)

49 的码元: [5, 2, 0, 0, 5, 4]
二进制视图读回: 49
三进制视图读回: 49
```

（`42 = 81 - 27 - 9 - 3 + 0`，`7 = 9 - 3 + 1`，`49 = 81 - 27 - 9 + 3 + 1`。）

## 5. 规则与限制

| 项目 | 规则 |
|---|---|
| 操作数 | 必须是 exact-dual；两个视图不一致 → `INVALID_LAYOUT` |
| 结果 | 非负整数；`sub` 出现负数 → `INVALID_PACKING` |
| 除法 | `divmod` 采用 Python floor 语义；除数为 0 → `INVALID_PACKING` |
| 数值范围 | Python 大整数，无固定位宽溢出 |
| 浮点 | 不支持；先按 `exact_dual.encode_f64` 编成位模式再当整数处理 |
| 长度 | 结果可能比操作数长（进位/乘积） |
| 性能 | 值级实现是 O(位数)；逐位加法也是 O(位数) |

## 6. 非目标

- 不定义 `d1 + d2` 这种"码元之间的算术"；
- 不做定点 / 浮点算术；
- 不做有符号负数（v1）；
- 不做 SIMD / C++ 内核（那是下游工作）。

## 7. 测试

`tests/test_arithmetic.py`：

- `add` / `sub` / `mul` / `divmod` 随机往返；
- `add_digits` 与 `add` 逐组对拍；
- 进位边界（`1+1`、`3+1`、`5+5`、`6⁵+1`、`2⁶⁴+2⁶⁴`）；
- 负数、除零、非 exact-dual 操作数的错误码。
