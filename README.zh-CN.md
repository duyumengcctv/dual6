<h1 align="center">Dual6 · 二生三</h1>

<p align="center"><b>一个 6 态码元，同时装一个二进制位和一个平衡三进制位。</b><br>
为“二进制引擎和三进制引擎要读同一份字节”的那一天准备的存储容器。</p>

<p align="center">
  <a href="README.md">English</a> · <b>简体中文</b>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="tests" src="https://img.shields.io/badge/tests-306%20passing-brightgreen.svg">
  <img alt="python" src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg">
  <img alt="rust" src="https://img.shields.io/badge/rust-2021-DEA584.svg">
  <img alt="status" src="https://img.shields.io/badge/status-dormant-lightgrey.svg">
</p>

<p align="center">
  <img alt="Dual6 格式" src="docs/dual6-format.zh.svg" width="880">
</p>

```text
d = 3·b + (t + 1)        b = d // 3        t = d % 3 - 1

d ∈ {0..5}   b ∈ {0,1}   t ∈ {-1, 0, +1}
```

> **这是一个容器，不是加速器，也不是数值类型。**
> `d` 是**码元**，不是 base-6 数字。它上面不定义任何算术。

---

## 命名

用这个编码存下来的模型，就是**一个 `.p6` 文件**——`llama-3-8b.p6`、
`bitnet-2b.p6`，而不是一堆分片加一堆 sidecar。

后缀取 `6`，因为 6 是第一个**完全数**（1 + 2 + 3 = 6），也正是这个编码的来源：
**2 态 × 3 态 = 6 态**。

中文名是**二生三**，取自《道德经》"道生一，一生二，**二生三**，三生万物"：
二（二进制）生三（三进制），就装在这一个码元里。

## 缘起

我最初只想知道一件事：**如果一台机器真的同时有二进制通路和三进制通路，
权重该怎么存，才能让两边都读得动？**

两个显而易见的答案都不好。存两份——于是有了两个文件、两次校验、两个会
互相漂移的版本。存一份、读时转换——于是总有一方要在热路径里付转换成本。

Dual6 是第三个答案：**把两种视图装进码元内部**，谁也不转换。

```text
d = 3·b + (t + 1)      一个码元，一个 bit，一个 trit
```

bit 通道取商，trit 通道取余。二进制消费者永远不看三进制位，反之亦然。
写入时把两种展开各算一次，读取时两边都不用算。

**这件事的起点是好奇，不是基准测试。** 下面那些数字，是我去找答案时量到的。

## 为什么

一个三值模型把 2 bit 的信息塞进 1.58 bit 的熵里；一个二进制模型只想要平铺
的 bit。今天要么二选一，要么存两份并保证同步。

Dual6 存**一份**制品，其中：

- 二进制消费者读 `d // 3` —— 一个平铺的 bit 平面；
- 三值消费者读 `d % 3 - 1` —— 5 trits/byte，与现有的 5-trit 打包**逐字节相同**；
- 两边都不需要转换、不需要第二次读、不需要第二份校验和。

两个平面在同一个文件里，同一次 CRC 之下，同一个版本号之下。

## 布局

| 布局 | 码元 | 字节 | 使用位数 |
|---|---:|---:|---:|
| 交错 | 5 | 13 | `D = Σ dᵢ·6ⁱ` |
| `D6-64` | 24 | 8 | 63 / 64 |
| `D6-128` | 48 | 16 | 125 / 128 |
| `D6-40` | 40 | 13 | 104 / 104 |

| 双平面块 | bit 平面 | trit 平面 | 合计 |
|---|---:|---:|---:|
| `D6-64-DP` | 3 B | 5 B | 8 B |
| `D6-128-DP` | 6 B | 10 B | 16 B |
| `D6-40-DP` | 5 B | 8 B | 13 B |

## 帧

| 帧 | 帧头 | 完整性 | 用途 |
|---|---|---|---|
| `D6P0` | 17 B | 无 | 最小格式 |
| `D6P1` | 20 B | CRC32 | 一条完整双平面流 |
| `D6P2` | 33 B | CRC32 | dtype、flags、块元数据 |

`D6P2` 的两个选项：

| 选项 | 作用 |
|---|---|
| `FLAG_OMIT_BIT_PLANE` | 去掉 bit 平面 —— 纯三值负载从 2.6 bpw 降到 **1.6 bpw** |
| `layout = 1` | 压缩 bit 平面 —— 每块 1 个 flag 位，只有含置位的块才存位图 |

## 快速开始

```bash
pip install -e .                  # 在仓库根目录
python run_tests.py               # 306 项测试
python tools/build_native.py      # 可选：构建 Rust 扩展（更快，输出字节相同）
```

```python
import dual6

bits  = [1, 0, 1, 1]
trits = [1, -1, 0, 1]

symbols = dual6.mux(bits, trits)                  # [5, 0, 4, 5]
assert dual6.demux(symbols) == (bits, trits)      # 两种视图，零转换

frame = dual6.pack_dual_plane_v2(bits, trits)     # D6P2，帧头 + CRC32
assert dual6.unpack_dual_plane_v2(frame)[:2] == (bits, trits)
```

### 内存映射帧

读一个大帧不一定非要把它拷进内存：

```python
from dual6 import MappedFrame, pack_dual_plane_v2, write_frame

frame = pack_dual_plane_v2([1, 0, 1, 1], [1, -1, 0, 1])
write_frame("tiny-model.p6", frame)

with MappedFrame("tiny-model.p6") as m:
    version, bits, trits, meta = m.unpack()       # version ∈ {0, 1, 2}
```

### Rust

核心是一个普通 crate。它**没有发布到 crates.io**，所以只能用 path 或 git 依赖：

```toml
[dependencies]
dual6-core = { path = "crates/dual6-core" }
# dual6-core = { git = "https://github.com/duyumengcctv/dual6", package = "dual6-core" }
```

```rust
let symbols = dual6_core::mux(&bits, &trits)?;
let (bits, trits) = dual6_core::demux(&symbols)?;
```

`DUAL6_BACKEND=ref|native|auto` 选择 Python 侧的实现；两套实现被要求
**逐字节一致**。

## 综合评分测试：为什么写、测什么、怎么测

测量套件一共 5 份原始测量 CSV + 3 份派生/权重 CSV、6 张图。本节是
**scorecard**（编码对比测试台）；
另外四项测量（压缩 bit 平面、掩码结构、故障尺寸、故障矩阵）见
[`benchmarks/README.md`](benchmarks/README.md)，并在本节末尾给出入口。

> 原始数据：[`benchmarks/scorecard_raw.csv`](benchmarks/scorecard_raw.csv)（15 行 × 19 列）·
> 场景权重：[`benchmarks/scenario_weights.csv`](benchmarks/scenario_weights.csv) ·
> 派生表：[`scenario_scores.csv`](benchmarks/scenario_scores.csv)、
> [`bandwidth_sweep.csv`](benchmarks/bandwidth_sweep.csv) ·
> 图表与列定义：[`benchmarks/README.md`](benchmarks/README.md)。

### 为什么写这个测试

在此之前，对比大多是“单挑”：

| 对比 | 结果 | 回答不了什么 |
|---|---|---|
| Dual6 双平面 vs `TQ1_0`（解码） | 0.448 vs 0.450，打平 | 只比了一个指标 |
| 单帧 vs 两份数组（加载） | 1.00×~1.03× | 只比了一个指标 |
| Dual6 vs `int8`（稀疏） | Dual6 输 | 只在对手最强的那块地上比 |

每个结论都对，合起来却回答不了真实问题：**我该用哪个编码？** 真实负载对
存储、解码、随机访问、稀疏 gather、选择性读、完整性的权重完全不同，而每
个编码都有自己的主场。

还有一层原因：如果指标和权重都由作者在看见结果之后挑，作者的编码几乎必然
会赢。所以测试台和权重必须**先定后跑**，并且权重必须公开。仓库里的
`scenario_weights.csv` 就是这份公开的权重；任何人可以拿导出的子分重新加权，
不需要重跑实验。

最后，“哪个编码更好”在物理上没有唯一答案——它取决于数据从哪来（带宽）。
所以输出是**带条件的**，不是排行榜。

### 测了什么

#### 9 种编码

| 类别 | 编码 | 为什么选它 |
|---|---|---|
| 稠密基线 | `fp16` 稠密 | 存储上界，解码最省事 |
| 稠密基线 | `int8` 稠密 | 常见量化基线 |
| 三值标准 | `TQ1_0`（5 trit/byte） | 生态事实标准 |
| 三值变体 | `TQ2_0`（2 bit/trit） | 简单定宽对照 |
| 定宽槽位 | `6 态 3-bit 槽` | Dual6 的 `slot3` 布局 |
| 被测方案 | **Dual6 双平面** | 主打布局（1.0 bit + 1.6 trit bpw） |
| 被测方案 | **Dual6 trit-only 帧** | 纯三值模式（1.6 bpw、CRC、单对象） |
| 被测方案 | **Dual6 交错（13 bit/5 sym）** | 最紧凑的 Dual6 打包 |
| 朴素基线 | 两份独立数组 | 无帧、无校验的“什么都不做”对照组 |

#### 两种载荷

| 载荷 | 含义 | 谁适用 |
|---|---|---|
| `P_trit` | `n` 个元素，每个一个平衡三值 | 纯三值权重 |
| `P_dual` | `n` 个元素，每个一个 `(bit, trit)` 对 | 逐元素双载荷 |

装不下某种载荷的编码记 **N/A**，不记 0 分。让一个容器为它做不到的事买单，
是评分表最常见的作弊方式。

#### 九项计分指标

| 指标 | 定义 | 为什么测 |
|---|---|---|
| `bits_per_element` | 字节 × 8 / `n` | 存储成本，精确 |
| `encode_ns_per_element` | 完整写入一遍 | 建模型的一次性成本 |
| `decode_ns_net` | 完整解码一遍，扣掉空循环基线 | 主要算力成本 |
| `random_ns_net` | 8000 次随机单元素访问，扣掉调用基线 | 检查点、稀疏更新 |
| `sparse_ns_net` | 只取 5% 元素，扣掉调用基线 | MoE / 掩码消费 |
| `selective_bytes` | 只服务一个通道必须读多少字节 | 双视图容器独有的指标 |
| `integrity` | 自带校验和？0/1 | 精确，无噪声 |
| `single_object` | 能否单对象原子发布？0/1 | 精确，无噪声 |
| `ops_per_element` | 解码循环的运算/遍历数 | 机器无关的复杂度代理 |

原始 CSV 还保留了未扣基线的原始计时、两列 Python 校准值、native 解码列和
`compute_source` 标记；完整的 19 列定义见
[`benchmarks/README.md`](benchmarks/README.md)。

#### 两个派生模型

**(a) 场景加权分。** 五组公开权重——纯三值推理、稀疏 gather 5%、逐元素双
载荷、检查点热切换、边缘小模型——把九项指标合成 0–100 分。权重在
[`scenario_weights.csv`](benchmarks/scenario_weights.csv)；九个 `score_*`
子分全部导出到 [`scenario_scores.csv`](benchmarks/scenario_scores.csv)，任何人
可以重新加权。

**(b) 物理成本模型。** 不依赖任何权重：

```text
effective_ns = max(decode_compute_ns, bytes_per_element / bandwidth)
```

扫 7 档带宽（1、3、10、30、100、300、1000 GB/s）。它回答的是“**在这条链路上**
谁赢”，输出在 [`bandwidth_sweep.csv`](benchmarks/bandwidth_sweep.csv)。

### 方法

**同一份载荷、同一台机器、同一个 harness。** 所有编码由同一段代码驱动，同
一个 65,536 元素载荷，同一台机器。这是让差异来自编码而不是环境的唯一办法。

**计时：取 N 次最小值，并扣掉解释器基线。**

```text
decode_ns_net = min_of_5(full_decode) - py_loop_overhead_ns
random_ns_net = min_of_5(random_lookup) - py_call_overhead_ns
sparse_ns_net = min_of_5(sparse_gather) - py_call_overhead_ns
```

不扣基线的话，Python 自己的 `for v in blob: total += v` 空循环（约
16 ns/元素）会被当成 `int8` 的解码成本。原始列和两列校准值都保留在 CSV 里，
减法可以逐行复核。有一行做了夹取：`int8 dense / trit` 扣完基线为负，因此
`decode_ns_net` 固定为 0.1 ns，并由原始列标记。

**归一化：用比值，不用 min-max。**

```text
score = 最优值 / 本值        （越小越好）
score = 本值                 （二值指标：0 或 1）
```

min-max 会让每个历史分数都依赖最差候选，明天加一个新编码，所有旧分数全变。
比值是绝对的：0.5 表示“比最好贵一倍”，加新候选不会改变它。

**权重公开、子分导出。** 加权分只能回答“在这组权重下谁高”，回答不了“哪个
编码更好”。所以 README 公开权重表、九个 `score_*` 子分和排名；也正因为如
此，才需要另一个不依赖权重的物理模型。

**native 交叉验证与 memcpy 下限。** `decode_ns_native` 要么是 Rust 微基准
实测，要么是稠密格式的 `memcpy` 下限，并在 `compute_source = memcpy_floor`
中标记。这个代理对稠密格式有利，因此对 bit-packed 是偏保守的；偏差方向写
在数据里。

### 测试结果

#### 纯三值载荷（9 种编码）

| 编码 | bpw | 编码 ns | 解码 ns | native/floor ns | 随机 ns | 稀疏 5% ns | 选择性读 B | 校验 | 单对象 |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 稠密 | 16.00 | 41.5 | 23.9 | 0.035† | 71.5 | 60.2 | 131072 | — | — |
| int8 稠密 | 8.00 | 35.5 | 0.1 | 0.035† | 21.3 | 14.1 | 65536 | — | ✓ |
| TQ1_0 (5 trit/byte) | 1.60 | 85.9 | 59.3 | 0.450 | 90.5 | 77.8 | 13108 | — | ✓ |
| TQ2_0 (2 bit/trit) | 2.00 | 88.9 | 48.5 | 0.562 | 62.4 | 57.7 | 16384 | — | ✓ |
| 6 态 3-bit 槽 | 3.00 | 269.6 | 230.4 | 1.015 | 114.1 | 103.5 | 24576 | — | ✓ |
| Dual6 双平面 | 2.60 | 160.6 | 119.1 | 0.448 | 211.5 | 170.5 | 13108 | ✓ | ✓ |
| Dual6 双平面（trit-only） | 1.60 | 160.5 | 59.2 | 0.448 | 92.4 | 76.6 | 13108 | ✓ | ✓ |
| Dual6 交错（13 bit） | 2.60 | 156.2 | 113.6 | 1.648 | 343.6 | 319.9 | 21301 | ✓ | ✓ |
| 两份独立数组 | 1.60 | 87.3 | 80.0 | 0.448 | 120.1 | 98.8 | 13108 | — | — |

† `memcpy_floor`：稠密格式没有真正解码，这个数字是拷贝下限，作为对稠密格式
有利的乐观代理使用；因此对比对 Dual6 偏保守。

一张表就是完整的取舍：存储最省的是 `TQ1_0`、两份独立数组和 **Dual6
trit-only 帧**（都是 1.60 bpw）；`int8` 解码快 592 倍，但存储是 8.00 bpw。
自带校验的只有三种 Dual6 编码。

#### 双载荷（6 种编码）

| 编码 | bpw | 编码 ns | 解码 ns | native/floor ns | 随机 ns | 稀疏 5% ns | 选择性读 B | 校验 | 单对象 |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| fp16 稠密 | 32.00 | 79.1 | 55.8 | 0.035† | 71.8 | 61.3 | 262144 | — | — |
| int8 稠密 | 16.00 | 55.8 | 11.0 | 0.035† | 26.8 | 12.8 | 131072 | — | ✓ |
| 6 态 3-bit 槽 | 3.00 | 280.3 | 231.7 | 1.015 | 105.0 | 101.2 | 24576 | — | ✓ |
| Dual6 双平面 | 2.60 | 163.3 | 125.6 | 0.448 | 232.0 | 178.5 | 8192 | ✓ | ✓ |
| Dual6 交错（13 bit） | 2.60 | 167.8 | 112.8 | 1.648 | 330.3 | 319.4 | 21301 | ✓ | ✓ |
| 两份独立数组 | 2.60 | 165.6 | 135.6 | 0.448 | 245.0 | 190.8 | 8192 | — | — |

只有 6 种编码能承载逐元素 `(bit, trit)` 对，所以双载荷表只有 6 行。第二个
通道的代价是 **1.62× 存储**（2.60 vs 1.60 bpw）。结构性的回报是
`selective_bytes`：双平面帧服务一个通道只需 **8192 B**，而 `int8` 需要
131072 B，交错布局需要读全部 21301 B。

<p align="center">
  <img alt="九种编码：存储 vs 解码成本" src="benchmarks/charts/scorecard.png" width="620"><br>
  <sub>九种编码的存储 vs 解码成本（纯三值载荷）。星号是 trit-only 帧：与 TQ1_0
  同一套字节，外加一次 CRC。</sub>
</p>

#### 五组权重

| 场景 | 载荷 | bpw | 编码 | 解码 | 随机 | 稀疏 | 选择性 | 校验 | 单对象 | 运算 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pure_ternary | trit | 30 | 5 | 20 | 5 | 5 | 5 | 15 | 10 | 5 |
| sparse_gather | both | 20 | 5 | 10 | 15 | 30 | 5 | 5 | 5 | 5 |
| dual_channel | dual | 20 | 5 | 15 | 5 | 10 | 25 | 10 | 5 | 5 |
| checkpoint_hot_swap | both | 10 | 10 | 10 | 20 | 5 | 5 | 20 | 15 | 5 |
| edge_small_model | both | 40 | 10 | 15 | 5 | 5 | 5 | 10 | 5 | 5 |

每行权重之和都是 100；`both` 表示该场景对 trit / dual 两种载荷**分别**评分，
绝不跨载荷比较。

| 场景 | 载荷 | 赢家 | 分数 | 第二名 | 分数 |
|---|---|---|---:|---|---:|
| pure_ternary | trit | Dual6 双平面（trit-only） | 64.5 | int8 稠密 | 57.0 |
| sparse_gather | trit | int8 稠密 | 75.0 | Dual6 双平面（trit-only） | 46.3 |
| sparse_gather | dual | int8 稠密 | 73.6 | Dual6 双平面 | 42.7 |
| dual_channel | dual | Dual6 双平面 | 65.6 | 两份独立数组 | 54.1 |
| checkpoint_hot_swap | trit | int8 稠密 | 68.0 | Dual6 双平面（trit-only） | 59.0 |
| checkpoint_hot_swap | dual | int8 稠密 | 66.9 | Dual6 双平面 | 58.2 |
| edge_small_model | trit | Dual6 双平面（trit-only） | 65.6 | TQ1_0 (5 trit/byte) | 58.7 |
| edge_small_model | dual | Dual6 双平面 | 66.9 | Dual6 交错（13 bit） | 63.3 |

<p align="center">
  <img alt="场景评分" src="benchmarks/charts/scenario-scores.png" width="760"><br>
  <sub>每个子分都在 <code>scenario_scores.csv</code> 里；热图只是该文件的一种渲染。</sub>
</p>

五组权重给出的诚实结论：

- **没有全胜编码。** 存储 + 校验 + 单对象权重下 trit-only 帧赢；稀疏 gather
  和热切换权重下 `int8` 赢；双通道权重下双平面帧赢。
- **双平面的赢是有条件的。** 它赢在“确实要消费两个通道”的场景，不赢纯延迟
  场景。
- **权重本身就是论点。** 权重以数据形式公开，读者不同意可以拿导出的子分重
  新加权。

#### 物理成本模型

| 带宽 (GB/s) | trit 赢家 | 有效 ns | dual 赢家 | 有效 ns |
|---:|---|---:|---|---:|
| 1 | Dual6 双平面 / Dual6 双平面（trit-only） / 两份独立数组 | 0.448 | Dual6 双平面 / 两份独立数组 | 0.448 |
| 3 | int8 稠密 | 0.333 | Dual6 双平面 / 两份独立数组 | 0.448 |
| 10 | int8 稠密 | 0.100 | int8 稠密 | 0.200 |
| 30 | int8 稠密 | 0.035 | int8 稠密 | 0.067 |
| 100 | fp16 稠密 / int8 稠密 | 0.035 | int8 稠密 | 0.035 |
| 300 | fp16 稠密 / int8 稠密 | 0.035 | fp16 稠密 / int8 稠密 | 0.035 |
| 1000 | fp16 稠密 / int8 稠密 | 0.035 | fp16 稠密 / int8 稠密 | 0.035 |

<p align="center">
  <img alt="带宽交叉" src="benchmarks/charts/bandwidth-crossover.png" width="760"><br>
  <sub>每元素有效成本 vs 链路带宽。左：trit 载荷；右：dual 载荷。越低越好。</sub>
</p>

这张表是条件，不是排名：

- **慢链路由存储主导。** 1 GB/s 时，trit 载荷上 bit-packed 布局赢（0.448 ns），
  dual 载荷上双平面 / 两份数组赢（0.448 ns）。
- **中间区间由内存主导。** `int8` 在 trit 的 3–30 GB/s、dual 的 10–100 GB/s
  附近赢，因为每元素 1 字节足够便宜，而它的计算下限极低。
- **快链路由算力主导。** 大约从 trit 的 100 GB/s、dual 的 300 GB/s 开始，
  稠密格式落在 0.035 ns 的 `memcpy` 地板上并打平。交叉带大约是 trit **2–5 GB/s**、dual **4–9 GB/s**，取决于
  对比的是哪一对。“慢于 1–3 GB/s 存储赢、快于 30 GB/s 算力赢”是这些曲线的
  安全外包络，不是某个单点悬崖。

#### 这个测试确定了什么

| 问题 | 答案 |
|---|---|
| 有没有“全胜”编码？ | **没有。** 存储赢家（`TQ1_0`、两份独立数组、Dual6 trit-only）和延迟赢家（`int8`）是不同的编码。 |
| Dual6 纯三值模式什么水平？ | **与 `TQ1_0` 持平**：1.60 bpw / 59.2 ns vs 59.3 ns，外加 CRC32 和单对象帧。 |
| 第二个通道值多少？ | **1.62× 存储**（2.60 vs 1.60 bpw），且只有真被消费时才值。 |
| 什么条件下谁赢？ | 慢链路存储主导、bit-packed 赢；快链路算力主导、稠密赢。交叉点是一个带，不是一个点。 |
| Dual6 唯一的结构性优势？ | **选择性读**：dual 载荷下 8192 B 服务一个通道，`int8` 要 131072 B。 |

### 局限

1. **Python 计时放大约 100×**：能看排序，不能看绝对值；
2. **稠密格式的算力是 `memcpy` 代理**，并标记在 `compute_source`；
3. **单机**：绝对数字不可移植；
4. **合成载荷**：三值均匀分布，不是真实 BitNet 权重分布；
5. **只有 9 种编码**：没测 `Q4_0` / `IQ2` 等真实量化格式；
6. **没有测量跑在真实模型上**：最大载荷 8 MiB。

结构性结论（没有全胜编码、trit-only 持平、第二通道 1.62×、选择性读）由格式
定义决定，不依赖这六条；精确的纳秒值依赖它们。

### 套件里的其它测量

scorecard 比较的是编码。另外四份 CSV 回答不同问题：压缩 bit 平面
（`sparse_plane.csv`；聚集掩码在 5% 密度下可省 **−25% ~ −33%**）、掩码结构
（`mask_structure.csv`）、静默损坏 vs 载荷大小（`fault_size.csv`）、故障下
什么保护读者（`fault_matrix.csv`）。在这台机器上，静默损坏在 **64 KiB 到
512 KiB** 之间开始出现。故障尺寸这一项值得和 scorecard 放在一起看：

<p align="center">
  <img alt="静默损坏率 vs 载荷大小" src="benchmarks/charts/fault-size.png" width="560"><br>
  <sub>无校验容器的就地同尺寸覆盖：64 KiB 以下为零，512 KiB 是 1.5%，8 MiB 是 26.5%。</sub>
</p>

### 数据与复现

```bash
python tools/make_scores.py          # 重新生成 scenario_scores.csv + bandwidth_sweep.csv
python tools/make_scores.py --check  # 已提交的派生 CSV 过期则失败
python tools/make_charts.py          # 从 CSV 重新生成全部 6 张图
python run_tests.py                  # README 里的表格会与 CSV 逐格核对
```

产生原始计时的 benchmark **harness** 在私有工作档案里，不在本仓库。这里可
复现的是数据管线：原始 CSV → 派生 CSV → 图 → README 表格。绝对计时离开
harness 和同一台机器就无法复现。


## 结论

**它并没有更快，这个仓库应当以这种方式被阅读。**

| 问题 | 答案 |
|---|---|
| 解码更便宜吗？ | 不。trit 平面就是现有的 5-trit 打包，成本相同：trit-only 帧 **1.60 bpw / 59.2 ns**，`TQ1_0` 是 1.60 bpw / 59.3 ns。 |
| 存储更省吗？ | 双通道不省：**2.6 bpw** vs 纯三值的 1.6，溢价 **62.5%**。去掉 bit 平面就回到 1.6。 |
| 单帧加载更快吗？ | 不。最好情况是 ±5% 内等价，多轮重复下稳定慢约 2%。 |
| 第二个通道值这个价吗？ | 只有真的有人读它才值。在同时消费两个通道的融合 GEMV 里，成本大约翻倍。 |

活下来的有三样：

1. **trit-only 帧与现有打包持平**（1.60 bpw、同样的解码成本），却多了 CRC32
   和单对象帧——对纯三值负载来说，这是一次白得的完整性校验。
2. **压缩 bit 平面在 bit 通道是聚集掩码时划算**（5% 密度省 25%–33%），
   而在掩码是周期散射时反而贵 1.5%。**判据是全零块占比，不是密度。**
3. **最有用的结果不是这个编码。** 对四种容器、三种更新协议做故障注入后发现：
   静默损坏由**校验和 + 原子 rename** 决定，与字节怎么打包无关；而且它只在
   **超过某个尺寸阈值**之后才出现（本机是 64 KiB 到 512 KiB 之间）。
   这条结论对任何格式都成立，包括大家已经在用的那些。

诚实的总结：**一个只做一件事的容器（一份制品、两个视图、一次校验、一个版本），
它的价格只有在两个视图都真被消费时才划算。**

## 实际可能适用的场景

四种，每一条都写明**什么情况下它就不对**——一个声称什么都能装的容器，其实什么都装不了。

**1 · 三值权重旁边挂一条逐元素侧通道** —— `D6P2` 双平面

格式原本要服务的场景：三值主值 + 逐元素标志位（离群点、剪枝、"该用高精度副本"），
同一个 kernel 在同一遍里读两者。一条顺序流，没有指针跳转，没有第二个文件会失步。
掩码聚集时 `layout 1` 再省 **−24.7% ~ −32.9%**。

<p align="center">
  <img alt="压缩 bit 平面 vs 掩码结构" src="benchmarks/charts/mask-structure.png" width="600"><br>
  <sub>同样 5% 密度、五种排列、每种 5 次重复。聚集掩码省 25–33%；周期散射反而贵 1.5%。</sub>
</p>

*什么时候不对*：两个通道不是逐元素对齐的。今天的格式基本都这样——
AWQ / OWQ 用 per-*channel* scale，SpQR / SqueezeLLM 用稀疏索引，
**正是因为对齐的第二通道更贵**。所以**这个场景目前是假设性的**：
容器为它准备好了，不代表它已经存在。

**2 · 纯三值模型，但想要一个文件、一次校验** —— `FLAG_OMIT_BIT_PLANE`

落在 **1.60 bpw、59.2 ns/元素**，与 `TQ1_0`（1.60 / 59.3）持平，另外白得 CRC32
和单对象帧。适合慢介质与小机器：一次 `open`、一次 `mmap`、一次校验。

<p align="center">
  <img alt="压缩 bit 平面 vs 掩码密度" src="benchmarks/charts/sparse-plane.png" width="600"><br>
  <sub>同一选项的密度扫描：掩码越稀收益越大，超过约 10% 后收益消失。</sub>
</p>

*什么时候不对*：数据本来就快。**单帧加载并不更快**——最好情况 ±5% 内等价，
多轮重复下稳定慢约 2%——在 NVMe 或 cache 驻留场景里，帧头是纯开销。

**3 · 边服务边热更新** —— 任何帧 + 协议

**这不是容器的性质。** 对四种互不相关的容器做故障注入表明：静默损坏由
**校验和 + 原子 `rename`** 决定，与字节怎么打包无关。普通 GGUF 套一层 manifest
能得到同样的保护。

测量到的是曲线形状：**64 KiB 以下看不到撕裂，512 KiB 是 1.5%，
2 MiB 是 17.0%，8 MiB 是 26.5%**。也就是说：只要你原地覆盖模型文件，
不管什么格式，超过 512 KiB 就已经暴露。

**4 · 加载器要写在 C / C++ / Rust 里** —— `D6P1` / `D6P2`

固定头部给出平面偏移；bit 平面可直接寻址，trit 平面就是现成的 5-trit/byte 打包，
现有三值 kernel 不用改。嵌入成本是一次头部解析。

*"零拷贝"要小心用*：bit 平面可以直接用，**trit 平面仍然需要解包**。

**明确不适用的地方**：

- 纯三值推理、无逐元素元数据 → 用 `TQ1_0`；
- 能整体进 cache → `int8` 的解码快一个数量级；
- 跨层混合精度、MoE 路由表、KV cache 布局 → 通道不对齐，本文所有测量都不适用；
- 通用压缩格式 → 这是容器，不是编解码器。

详细版（每一行都带测量出处）见 [`docs/13-use-cases.md`](docs/13-use-cases.md)。

## 展望

容器已经做完，缺的是一个用它的理由。两个信号能提供这个理由：

1. **需求侧。** 出现一种公开的模型格式，其**逐元素**元数据与权重一起被读取。
   今天的格式把 scale 放在组粒度、把离群点放成稀疏索引，正是为了**永远不需要**
   一条对齐的第二通道。
2. **供给侧。** 三值**运算**原生执行。今天所有"三值推理"路径在相乘之前都先
   解包成 FP16，所以 bit 平面没有读者。

任一信号出现，接下来的工作已经想好了：给 `layout 1` 加块索引，让随机访问回到 O(1)；
如果 bit 通道真的活了，再上 CRT 变体（用 `b = d % 2` 而不是 `d // 3`），
让两个通道的按位加同时无进位。**两者都是规格变更，不是重写。**

如果几年内两个信号都没出现，诚实的结局就是现在这样：一个完整、有测试、有文档，
只是暂时没人需要的容器。

还有一个必须写下来的限制：**这里没有任何一个测量跑在真实模型上。**
最大的载荷是 8 MiB，故障注入的数字来自单机上的合成容器。

## 状态

**待命，不是废弃。** 容器能用、有测试；前提未经验证之前不再加新功能。

前提很窄：二进制引擎和三值引擎**在同一遍里读同一个元素**。今天它只成立一半——
BitNet 这类三值模型存的是三值，算的是 FP16，bit 通道没有消费者。两个信号会改变这一点：

1. 出现一种公开的模型格式，其**逐元素**元数据与权重一起被读取
   （不是 per-tensor scale，也不是稀疏索引）；
2. 三值**运算**原生执行，而不是先解包成浮点。

在这之前，它就是一个有规格、有实现、有测量的容器。

## 范围

**属于容器层**——码元、序列/布局/块打包、帧、错误码、单通道适配。

**不属于**——数值语义解释、量化、dtype/shape 元数据、张量算子、任何模型格式连接器。
容器只负责搬运字节，不解释它们。

## 文档

| 文件 | 内容 |
|---|---|
| [`docs/00-scope.md`](docs/00-scope.md) | 容器层的边界 |
| [`docs/01-symbol.md`](docs/01-symbol.md) | 6 态码元 |
| [`docs/02-sequence.md`](docs/02-sequence.md) | `mux` / `demux` |
| [`docs/03-layout.md`](docs/03-layout.md) | 交错、双平面、固定块 |
| [`docs/04-frame.md`](docs/04-frame.md) | `D6P0` / `D6P1` / `D6P2`、flags、布局 |
| [`docs/05-errors.md`](docs/05-errors.md) | 错误码 |
| [`docs/08-api.md`](docs/08-api.md) | 公开 API |
| [`docs/09-release.md`](docs/09-release.md) | 构建、测试与发布 |
| [`docs/11-exact-dual.md`](docs/11-exact-dual.md) | 可选编解码：一个整数，两种视图 |
| [`docs/12-arithmetic.md`](docs/12-arithmetic.md) | 可选的 exact-dual 算术助手 |
| [`docs/13-use-cases.md`](docs/13-use-cases.md) | 适用 / 不适用 / 在等什么 |
| [`benchmarks/README.md`](benchmarks/README.md) | 每份 CSV 测了什么、在哪台机器上 |
| [`tools/make_scores.py`](tools/make_scores.py) | 重新生成场景评分与带宽扫描 CSV |
| [`tools/make_charts.py`](tools/make_charts.py) | 从 CSV 重新生成全部六张图 |

## 仓库结构

```text
python/dual6/      参考实现（含适配层、CLI、mmap）
crates/            dual6-core（Rust）、dual6-py（PyO3）、dual6-ffi（C ABI）
docs/              规格文档，一个主题一个文件
benchmarks/        5 份原始 + 3 份派生 CSV，6 张图
tests/             306 项测试，含“文档驱动”的规格测试
examples/          三个可直接运行的程序
tools/             check_all.py、coverage.py、verify_package.py、build_native.py 等
```

## 测试

```bash
python run_tests.py                        # 306
DUAL6_BACKEND=ref python run_tests.py      # 只用参考实现
cargo test -p dual6-core                   # Rust 核心
```

[`tests/test_spec_from_scratch.py`](tests/test_spec_from_scratch.py) 会**解析
`docs/01`–`docs/05` 里的表格**并逐条校验实现，所以规格或代码任何一边改了没同步，
构建就会失败。[`tests/test_benchmark_data.py`](tests/test_benchmark_data.py) 负责把
`benchmarks/` 里的 CSV 与上文引用的数字绑在一起。

**覆盖了什么**：容器往返、golden vectors、错误码、双后端一致性
（native 与参考实现必须逐字节相同）、property 与 fuzz 测试、以及 `D6P2` 的两个选项。

**没覆盖什么**：benchmark 的**脚本**不在这个仓库里，只有它们的输出在。早前的
完整工作档案报出更大的数字，是因为它额外带着图表、打包和文档守卫测试——没有那些
脚本，那些测试没有意义。

## 许可证

MIT —— 见 [`LICENSE`](LICENSE)。
