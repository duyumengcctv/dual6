# 05 · 错误码

| 错误码 | 含义 |
|---|---|
| `OK` | 成功 |
| `INVALID_DIGIT` | 码元不在 `0..5` |
| `INVALID_PACKING` | 容器值超出 `6^n` |
| `WIDTH_MISMATCH` | bit / trit 宽度不一致 |
| `INVALID_BIT` | bit 不在 `{0,1}` |
| `INVALID_TRIT` | trit 不在 `{-1,0,1}` |
| `INVALID_LAYOUT` | 长度、magic、填充位非法 |
| `UNSUPPORTED_VERSION` | 帧版本不支持 |
| `CRC_MISMATCH` | D6P1 / D6P2 帧 CRC32 不匹配 |

Python 中抛出 `Dual6Error`，错误码在 `error.code`。

## 模块

```text
python/dual6/_ref/errors.py
```
