"""Round-trip a real model's weights through Dual6 and compare logits.

This is an optional artifact experiment, not part of the CI golden path: it
needs ``torch``, ``transformers`` and a model checkpoint.  The repository keeps
the resulting CSV, not the weights.

Two scopes are supported:

* ``linears`` -- ternarize only the transformer linear weights and keep
  embeddings / LayerNorm / biases in fp16 (the realistic mixed-precision case);
* ``all_2d`` -- ternarize every 2D weight, including embeddings and ``lm_head``
  (a pure format-losslessness stress test).

The script compares the **ternary baseline** against the **Dual6-decoded**
model.  It deliberately does not compare against the original fp16 model for
the losslessness claim, because that difference is quantization, not storage.

Usage
-----
    python tools/model_roundtrip.py --check-csv
    python tools/model_roundtrip.py --download --scope linears
    python tools/model_roundtrip.py --local-dir models/gpt2 --scope all_2d
    python tools/model_roundtrip.py --smoke

``--check-csv`` validates the committed ``benchmarks/model_roundtrip.csv``
without importing torch or downloading anything.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from typing import Dict, List, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "python") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "python"))

BENCH = os.path.join(ROOT, "benchmarks")
DEFAULT_OUT = os.path.join(BENCH, "model_roundtrip.csv")
DEFAULT_REPO = "AI-ModelScope/gpt2"
DEFAULT_LOCAL = os.path.join(ROOT, "models", "gpt2")
CHUNK = 65536
HEADER_BYTES = 33

FIELDS = (
    "model_repo",
    "model",
    "scope",
    "parameters_total",
    "encoded_elements",
    "non_encoded_elements",
    "encoded_tensors",
    "chunk_elements",
    "frames",
    "dual6_payload_bytes",
    "dual6_header_bytes",
    "dual6_scale_bytes",
    "dual6_encoded_total_bytes",
    "dual6_model_total_bytes",
    "dual6_bpw_encoded",
    "dual6_bpw_overall",
    "tq1_payload_bytes",
    "tq1_scale_bytes",
    "tq1_encoded_total_bytes",
    "tq1_model_total_bytes",
    "tq1_bpw_encoded",
    "tq1_bpw_overall",
    "two_bit_payload_bytes",
    "two_bit_scale_bytes",
    "two_bit_encoded_total_bytes",
    "two_bit_model_total_bytes",
    "two_bit_bpw_encoded",
    "two_bit_bpw_overall",
    "int8_payload_bytes",
    "int8_scale_bytes",
    "int8_encoded_total_bytes",
    "int8_model_total_bytes",
    "int8_bpw_encoded",
    "int8_bpw_overall",
    "weights_exact",
    "logits_exact",
    "max_logit_diff",
    "top1_agreement",
    "quantized_max_logit_diff",
    "quantized_top1_agreement",
    "roundtrip_seconds",
    "notes",
)

INT_FIELDS = tuple(f for f in FIELDS if f not in (
    "model_repo", "model", "scope",
    "dual6_bpw_encoded", "dual6_bpw_overall",
    "tq1_bpw_encoded", "tq1_bpw_overall",
    "two_bit_bpw_encoded", "two_bit_bpw_overall",
    "int8_bpw_encoded", "int8_bpw_overall",
    "max_logit_diff", "top1_agreement",
    "quantized_max_logit_diff", "quantized_top1_agreement",
    "roundtrip_seconds", "notes",
))
FLOAT_FIELDS = tuple(f for f in FIELDS if f.endswith(("_bpw_encoded", "_bpw_overall")) or f in (
    "max_logit_diff", "top1_agreement",
    "quantized_max_logit_diff", "quantized_top1_agreement",
    "roundtrip_seconds",
))


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def _read(name: str) -> List[Dict[str, str]]:
    with open(name, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(name: str, rows: Sequence[Dict[str, object]]) -> None:
    with open(name, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(v) if isinstance(v, float) else v for k, v in row.items()})


def validate_rows(rows: Sequence[Dict[str, str]]) -> List[str]:
    problems: List[str] = []
    if not rows:
        return ["no rows"]
    for row in rows:
        scope = row.get("scope", "?")
        missing = [f for f in FIELDS if f not in row]
        if missing:
            problems.append(f"{scope}: missing columns {missing}")
            continue
        try:
            ints = {f: int(row[f]) for f in INT_FIELDS}
            floats = {f: float(row[f]) for f in FLOAT_FIELDS}
        except ValueError as exc:
            problems.append(f"{scope}: bad numeric value: {exc}")
            continue

        def close(
            name: str, expected: float, actual: float, tol: float = 1e-5, scope: str = scope
        ) -> None:
            if abs(expected - actual) > tol:
                problems.append(f"{scope}: {name} {actual} != expected {expected}")

        frames = ints["frames"]
        close("header_bytes", frames * HEADER_BYTES, ints["dual6_header_bytes"])
        close(
            "dual6_encoded_total",
            ints["dual6_payload_bytes"] + ints["dual6_header_bytes"] + ints["dual6_scale_bytes"],
            ints["dual6_encoded_total_bytes"],
        )
        non_encoded_bytes = ints["non_encoded_elements"] * 2
        close(
            "dual6_model_total",
            ints["dual6_encoded_total_bytes"] + non_encoded_bytes,
            ints["dual6_model_total_bytes"],
        )
        for prefix in ("tq1", "two_bit", "int8"):
            close(
                f"{prefix}_encoded_total",
                ints[f"{prefix}_payload_bytes"] + ints[f"{prefix}_scale_bytes"],
                ints[f"{prefix}_encoded_total_bytes"],
            )
            close(
                f"{prefix}_model_total",
                ints[f"{prefix}_encoded_total_bytes"] + non_encoded_bytes,
                ints[f"{prefix}_model_total_bytes"],
            )
        for prefix in ("dual6", "tq1", "two_bit", "int8"):
            close(
                f"{prefix}_bpw_encoded",
                ints[f"{prefix}_encoded_total_bytes"] * 8 / ints["encoded_elements"],
                floats[f"{prefix}_bpw_encoded"],
            )
            close(
                f"{prefix}_bpw_overall",
                ints[f"{prefix}_model_total_bytes"] * 8 / ints["parameters_total"],
                floats[f"{prefix}_bpw_overall"],
            )
        if ints["weights_exact"] not in (0, 1) or ints["logits_exact"] not in (0, 1):
            problems.append(f"{scope}: exact flags must be 0/1")
        if floats["max_logit_diff"] != 0.0 or floats["top1_agreement"] != 1.0:
            problems.append(f"{scope}: ternary baseline and Dual6 logits are not identical")
    return problems


def check_csv(path: str) -> int:
    rows = _read(path)
    problems = validate_rows(rows)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    for row in rows:
        print(
            f"ok: {row['model']} / {row['scope']}: "
            f"{row['dual6_bpw_encoded']} bpw encoded, "
            f"{row['dual6_bpw_overall']} bpw overall, "
            f"logits exact={row['logits_exact']}"
        )
    return 0


def _is_linear(name: str) -> bool:
    return any(
        key in name
        for key in (
            ".attn.c_attn.weight",
            ".attn.c_proj.weight",
            ".mlp.c_fc.weight",
            ".mlp.c_proj.weight",
        )
    )


def _load_model(path: str):
    from transformers import GPT2LMHeadModel

    model = GPT2LMHeadModel.from_pretrained(path, local_files_only=True)
    model.eval()
    return model


def _build_tiny_model():
    from transformers import GPT2Config, GPT2LMHeadModel

    config = GPT2Config(
        vocab_size=128, n_positions=64, n_embd=64, n_layer=2, n_head=2
    )
    return GPT2LMHeadModel(config).eval()


def _roundtrip(model, scope: str, chunk: int, seed: int) -> Dict[str, object]:
    import copy

    import dual6
    import torch

    params = [(name, p) for name, p in model.named_parameters() if p.dim() == 2]
    if scope == "linears":
        params = [(name, p) for name, p in params if _is_linear(name)]
    elif scope != "all_2d":
        raise SystemExit(f"unknown scope {scope!r}")

    encoded_elements = sum(p.numel() for _, p in params)
    parameters_total = sum(p.numel() for p in model.parameters())
    non_encoded_elements = parameters_total - encoded_elements
    scales = 4 * len(params)
    tq1_payload = sum((p.numel() + 4) // 5 for _, p in params)
    two_bit_payload = sum((p.numel() + 3) // 4 for _, p in params)
    int8_payload = encoded_elements

    ternary: Dict[str, object] = {}
    decoded: Dict[str, object] = {}
    frames = 0
    dual6_payload = 0
    dual6_header = 0

    start = time.time()
    with torch.no_grad():
        for name, p in params:
            scale = p.data.abs().mean().clamp_min(1e-12)
            trits = torch.clamp(torch.round(p.data / scale), -1, 1).to(torch.int8)
            flat = trits.flatten()
            out = torch.empty(flat.numel(), dtype=torch.float32)
            for index in range(0, flat.numel(), chunk):
                part = flat[index : index + chunk].tolist()
                frame = dual6.pack_dual_plane_v2(
                    [0] * len(part), part, flags=dual6.FLAG_OMIT_BIT_PLANE
                )
                bits, got, meta = dual6.unpack_dual_plane_v2(frame)
                if bits != [0] * len(part) or got != part:
                    raise SystemExit(f"round-trip mismatch in {name}")
                out[index : index + len(part)] = torch.tensor(got, dtype=torch.float32)
                frames += 1
                dual6_payload += meta["payload_len"]
                dual6_header += len(frame) - meta["payload_len"]
            ternary[name] = trits.float().reshape(p.shape) * scale
            decoded[name] = out.reshape(p.shape) * scale
            if not torch.equal(decoded[name], ternary[name]):
                raise SystemExit(f"decoded tensor mismatch in {name}")
    elapsed = time.time() - start

    with torch.no_grad():
        ternary_model = copy.deepcopy(model)
        decoded_model = copy.deepcopy(model)
        for name, tensor in ternary.items():
            ternary_model.state_dict()[name].copy_(tensor)
        for name, tensor in decoded.items():
            decoded_model.state_dict()[name].copy_(tensor)
        torch.manual_seed(seed)
        tokens = torch.randint(0, model.config.vocab_size, (4, 16))
        original_logits = model(tokens).logits
        ternary_logits = ternary_model(tokens).logits
        decoded_logits = decoded_model(tokens).logits

    max_diff = (ternary_logits - decoded_logits).abs().max().item()
    top1 = (ternary_logits.argmax(-1) == decoded_logits.argmax(-1)).float().mean().item()
    quant_max = (original_logits - ternary_logits).abs().max().item()
    quant_top1 = (
        original_logits.argmax(-1) == ternary_logits.argmax(-1)
    ).float().mean().item()

    non_encoded_bytes = non_encoded_elements * 2
    dual6_encoded_total = dual6_payload + dual6_header + scales
    tq1_encoded_total = tq1_payload + scales
    two_bit_encoded_total = two_bit_payload + scales
    int8_encoded_total = int8_payload + scales

    def bpw(total: int, denominator: int) -> float:
        return total * 8 / denominator

    return {
        "model_repo": "",
        "model": "",
        "scope": scope,
        "parameters_total": parameters_total,
        "encoded_elements": encoded_elements,
        "non_encoded_elements": non_encoded_elements,
        "encoded_tensors": len(params),
        "chunk_elements": chunk,
        "frames": frames,
        "dual6_payload_bytes": dual6_payload,
        "dual6_header_bytes": dual6_header,
        "dual6_scale_bytes": scales,
        "dual6_encoded_total_bytes": dual6_encoded_total,
        "dual6_model_total_bytes": dual6_encoded_total + non_encoded_bytes,
        "dual6_bpw_encoded": bpw(dual6_encoded_total, encoded_elements),
        "dual6_bpw_overall": bpw(dual6_encoded_total + non_encoded_bytes, parameters_total),
        "tq1_payload_bytes": tq1_payload,
        "tq1_scale_bytes": scales,
        "tq1_encoded_total_bytes": tq1_encoded_total,
        "tq1_model_total_bytes": tq1_encoded_total + non_encoded_bytes,
        "tq1_bpw_encoded": bpw(tq1_encoded_total, encoded_elements),
        "tq1_bpw_overall": bpw(tq1_encoded_total + non_encoded_bytes, parameters_total),
        "two_bit_payload_bytes": two_bit_payload,
        "two_bit_scale_bytes": scales,
        "two_bit_encoded_total_bytes": two_bit_encoded_total,
        "two_bit_model_total_bytes": two_bit_encoded_total + non_encoded_bytes,
        "two_bit_bpw_encoded": bpw(two_bit_encoded_total, encoded_elements),
        "two_bit_bpw_overall": bpw(two_bit_encoded_total + non_encoded_bytes, parameters_total),
        "int8_payload_bytes": int8_payload,
        "int8_scale_bytes": scales,
        "int8_encoded_total_bytes": int8_encoded_total,
        "int8_model_total_bytes": int8_encoded_total + non_encoded_bytes,
        "int8_bpw_encoded": bpw(int8_encoded_total, encoded_elements),
        "int8_bpw_overall": bpw(int8_encoded_total + non_encoded_bytes, parameters_total),
        "weights_exact": 1,
        "logits_exact": 1 if torch.equal(ternary_logits, decoded_logits) else 0,
        "max_logit_diff": max_diff,
        "top1_agreement": top1,
        "quantized_max_logit_diff": quant_max,
        "quantized_top1_agreement": quant_top1,
        "roundtrip_seconds": elapsed,
        "notes": (
            "all 2D weights ternarized; embeddings and lm_head included"
            if scope == "all_2d"
            else "only transformer linear weights ternarized; embedding/LayerNorm/bias kept fp16"
        ),
    }


def _download(repo: str, local_dir: str) -> None:
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError as exc:
        raise SystemExit(
            "modelscope is not installed; run `python -m pip install modelscope`"
        ) from exc
    snapshot_download(
        repo,
        local_dir=local_dir,
        allow_file_pattern=[
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "vocab.json",
            "merges.txt",
            "generation_config.json",
        ],
    )


def _upsert(path: str, row: Dict[str, object]) -> None:
    rows: List[Dict[str, str]] = []
    if os.path.exists(path):
        rows = _read(path)
    key = (str(row["model_repo"]), str(row["scope"]), str(row["chunk_elements"]))
    rows = [
        r for r in rows
        if (r.get("model_repo"), r.get("scope"), r.get("chunk_elements")) != key
    ]
    rows.append({k: (_fmt(v) if isinstance(v, float) else str(v)) for k, v in row.items()})
    rows.sort(key=lambda r: (r["model_repo"], r["scope"], int(r["chunk_elements"])))
    _write(path, rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-csv", action="store_true", help="validate the committed CSV only")
    parser.add_argument("--smoke", action="store_true", help="run a local tiny GPT-2, no download")
    parser.add_argument("--download", action="store_true", help="download the model from ModelScope")
    parser.add_argument("--local-dir", default=DEFAULT_LOCAL, help="local model directory")
    parser.add_argument("--model-repo", default=DEFAULT_REPO, help="ModelScope repo id")
    parser.add_argument("--model-name", default="gpt2-small", help="display name in the CSV")
    parser.add_argument("--scope", choices=("linears", "all_2d"), default="linears")
    parser.add_argument("--chunk", type=int, default=CHUNK, help="trits per D6P2 frame")
    parser.add_argument("--seed", type=int, default=0, help="seed for the comparison tokens")
    parser.add_argument("--output", default=DEFAULT_OUT, help="CSV to update")
    args = parser.parse_args(argv)

    if args.check_csv:
        return check_csv(args.output)

    if args.download:
        _download(args.model_repo, args.local_dir)

    if args.smoke:
        model = _build_tiny_model()
        row = _roundtrip(model, args.scope, args.chunk, args.seed)
        row["model_repo"] = "local"
        row["model"] = "tiny-gpt2"
        print({k: row[k] for k in ("scope", "encoded_elements", "frames",
                                   "dual6_bpw_encoded", "logits_exact")})
        return 0

    if not os.path.isdir(args.local_dir):
        raise SystemExit(
            f"model directory not found: {args.local_dir}; "
            "pass --download or --local-dir"
        )

    model = _load_model(args.local_dir)
    row = _roundtrip(model, args.scope, args.chunk, args.seed)
    row["model_repo"] = args.model_repo
    row["model"] = args.model_name
    _upsert(args.output, row)
    print(f"wrote {args.output}: {row['model']} / {row['scope']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
