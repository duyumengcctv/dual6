# 09 · 构建、测试与发布

本文件描述 Dual6 的构建路径和发布门禁。它对应仓库里的
`tools/check_all.py`、`tools/coverage.py`、`tools/verify_package.py`。

## 1. 版本号

版本号只有一个来源，分布在四处，必须一致：

```text
Cargo.toml            [workspace.package] version
crates/dual6-py/Cargo.toml
pyproject.toml        [project] version
python/dual6/__init__.py  __version__
```

检查：

```bash
python tools/check_version.py
```

## 2. 两条构建路径

### 2.1 纯 Python wheel（默认）

不需要 Rust，`setuptools.build_meta` 直接打出 `py3-none-any` wheel：

```bash
python -m pip install build
python -m build --wheel
pip install .
```

包内始终先加载 `dual6._ref`；没有 native 扩展时就是完整的参考实现。

### 2.2 可选 native 扩展（PyO3）

```bash
python tools/build_native.py                 # 先 cargo test，再编译并复制
python tools/build_native.py --skip-tests    # 只编译
```

脚本把扩展复制成 `python/dual6/_native.pyd`（Windows）、`.so`（Linux）或
`.dylib`（macOS）。运行时用 `DUAL6_BACKEND` 选择后端：

```bash
DUAL6_BACKEND=auto    python run_tests.py    # 默认：有 native 就用
DUAL6_BACKEND=ref     python run_tests.py    # 只用纯 Python
DUAL6_BACKEND=native  python run_tests.py    # 要求 native，缺失即报错
```

两个后端必须产生逐字节相同的结果，并抛出相同的 `Dual6Error` 错误码；
`python/dual6/_conformance.py` 负责这条约束。

## 3. 发布门禁

```bash
python tools/check_all.py             # 版本 + native 覆盖率 + 派生数据 + cargo test/build + Python 测试
python tools/check_all.py --skip-rust # 纯 Python 环境
python tools/coverage.py --html       # 测试 + 覆盖率（htmlcov/）
python tools/verify_package.py --build --install-test
```

| 脚本 | 作用 |
|---|---|
| `tools/check_all.py` | 总门禁；`--skip-rust` 跳过 cargo |
| `tools/coverage.py` | 在 `unittest` 套件上跑 coverage |
| `tools/verify_package.py` | 构建 wheel + sdist，检查内容并在临时 venv 里安装冒烟 |
| `tools/native_coverage.py` | 检查 Rust 导出、`_native.pyi` 与公开 API 是否一致 |
| `tools/check_version.py` | 检查四处版本号一致 |
| `tools/make_scores.py` | 重建 8 份派生 CSV（场景、带宽、综合评分、X/S 评分、信息预算、解码比值、权重敏感性、权重扫描）；`--check` 校验未过期 |
| `tools/make_charts.py` | 从 CSV 重建 9 张图（需要 matplotlib） |
| `tools/bench_xs.py` | X/S 解码路径微基准；`--check-csv` 纯离线校验 |
| `tools/model_roundtrip.py` | 可选：真实小模型无损性实验；`--check-csv` 纯离线校验 |

## 4. 发布产物

```bash
python tools/verify_package.py --build --install-test
ls dist/
# dual6-0.3.0-py3-none-any.whl
# dual6-0.3.0.tar.gz
```

`verify_package.py` 会检查：

- wheel 包含 `dual6/_ref`、`dual6/adapters`、`py.typed`、`_native.pyi`；
- sdist 包含 README、docs（含 SVG）、benchmarks（含 CSV 与图表 PNG）、
  tools、tests 与 golden vectors；
- 两个产物都不含 `__pycache__`、`.pyc`、`.pyd`、`.so`、`.dll` 等构建产物；
- wheel 能装进全新 venv，并完成 `mux`/`demux`、D6P2 往返和 CLI 冒烟。

## 5. CI

`.github/workflows/ci.yml` 有三个 job：

| job | 内容 |
|---|---|
| `ref-matrix` | Python 3.9–3.13，`check_all.py --skip-rust` + `coverage.py --html` |
| `native` | 构建 PyO3 扩展，`cargo test`，`DUAL6_BACKEND=native check_all.py --skip-rust` |
| `package` | `verify_package.py --build --install-test` |

## 6. 发布 checklist

1. 更新四处版本号；
2. `python tools/make_scores.py --check`（派生 CSV 未过期）；
3. `python tools/check_all.py`（有 Rust 工具链时不要加 `--skip-rust`）；
4. `python tools/coverage.py --html`；
5. `python tools/verify_package.py --build --install-test`；
6. 确认 `dist/` 里只有这一版的 wheel 和 sdist；
7. 打 tag 并上传产物。
