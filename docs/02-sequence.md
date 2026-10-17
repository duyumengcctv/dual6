# 02 · 序列

## 数据模型

```text
bits  = [b_0, b_1, ..., b_{n-1}]
trits = [t_0, t_1, ..., t_{n-1}]
symbols[i] = 3*b_i + (t_i + 1)
```

默认：

- LSB first；
- `bits`、`trits`、`symbols` 三者长度必须相同。

## API

```python
mux(bits, trits) -> list[int]
demux(symbols) -> (list[int], list[int])
```

宽度不一致时返回：

```text
WIDTH_MISMATCH
```

## 模块

```text
python/dual6/_ref/sequence.py
```
