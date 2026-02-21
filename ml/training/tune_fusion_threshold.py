#!/usr/bin/env python3
"""Tune fusion weights/threshold for backend final decision."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "ml" / "artifacts" / "fusion_tuning_latest.json"


@dataclass
class FusionMetrics:
    w_url_base: float
    w_text_base: float
    threshold: float
    precision: float
    recall: float
    f1: float
    fpr: float
    tn: int
    fp: int
    fn: int
    tp: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grid-search best fusion weights/threshold.")
    parser.add_argument("--csv", type=Path, required=True, help="CSV with url_prob,text_prob,label columns.")
    parser.add_argument("--url-col", type=str, default="url_prob")
    parser.add_argument("--text-col", type=str, default="text_prob")
    parser.add_argument("--label-col", type=str, default="label")
    parser.add_argument("--positive-labels", type=str, default="1,true,phishing,malicious,bad")
    parser.add_argument("--fpr-target", type=float, default=0.03)
    parser.add_argument("--w-step", type=float, default=0.05)
    parser.add_argument("--th-min", type=float, default=0.50)
    parser.add_argument("--th-max", type=float, default=0.95)
    parser.add_argument("--th-step", type=float, default=0.01)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help=f"Where to write tuned params for backend loading (default: {DEFAULT_OUTPUT_JSON})",
    )
    return parser.parse_args()


def _is_positive(raw_value: str, positive_set: set[str]) -> bool:
    return raw_value.strip().lower() in positive_set


def load_labeled_scores(
    csv_path: Path,
    url_col: str,
    text_col: str,
    label_col: str,
    positive_labels: set[str],
) -> tuple[list[float], list[float], list[int]]:
    url_probs: list[float] = []
    text_probs: list[float] = []
    labels: list[int] = []

    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                up = float((row.get(url_col) or "").strip())
                tp = float((row.get(text_col) or "").strip())
            except ValueError:
                continue

            if up < 0.0 or up > 1.0 or tp < 0.0 or tp > 1.0:
                continue

            raw_label = str(row.get(label_col) or "").strip()
            label = 1 if _is_positive(raw_label, positive_labels) else 0
            url_probs.append(up)
            text_probs.append(tp)
            labels.append(label)

    if not url_probs:
        raise RuntimeError("No valid rows loaded from CSV.")
    if 0 not in labels or 1 not in labels:
        raise RuntimeError("CSV labels must contain both negative and positive classes.")
    return url_probs, text_probs, labels


def fusion_score(url_prob: float, text_prob: float, w_url_base: float, w_text_base: float) -> float:
    # Keep consistent with backend/workflow/nodes/analysis.py current logic.
    c_u = abs(url_prob - 0.5) + 0.5
    c_t = abs(text_prob - 0.5) + 0.5
    w_u = (w_url_base * c_u) / (w_url_base * c_u + w_text_base * c_t)
    w_t = 1 - w_u
    return w_u * url_prob + w_t * text_prob


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute_metrics(
    url_probs: list[float],
    text_probs: list[float],
    labels: list[int],
    w_url_base: float,
    threshold: float,
) -> FusionMetrics:
    w_text_base = 1.0 - w_url_base
    tp = tn = fp = fn = 0

    for up, tpb, y in zip(url_probs, text_probs, labels):
        score = fusion_score(up, tpb, w_url_base, w_text_base)
        pred = 1 if score >= threshold else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 1:
            fn += 1
        else:
            tn += 1

    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    fpr = safe_div(fp, fp + tn)

    return FusionMetrics(
        w_url_base=round(w_url_base, 4),
        w_text_base=round(w_text_base, 4),
        threshold=round(threshold, 4),
        precision=round(precision, 6),
        recall=round(recall, 6),
        f1=round(f1, 6),
        fpr=round(fpr, 6),
        tn=tn,
        fp=fp,
        fn=fn,
        tp=tp,
    )


def frange(start: float, stop: float, step: float) -> Iterable[float]:
    value = start
    while value <= stop + 1e-12:
        yield value
        value += step


def main() -> None:
    args = parse_args()
    positive_labels = {s.strip().lower() for s in args.positive_labels.split(",") if s.strip()}
    url_probs, text_probs, labels = load_labeled_scores(
        csv_path=args.csv,
        url_col=args.url_col,
        text_col=args.text_col,
        label_col=args.label_col,
        positive_labels=positive_labels,
    )

    all_results: list[FusionMetrics] = []
    for w_url in frange(0.0, 1.0, args.w_step):
        for th in frange(args.th_min, args.th_max, args.th_step):
            all_results.append(
                compute_metrics(
                    url_probs=url_probs,
                    text_probs=text_probs,
                    labels=labels,
                    w_url_base=w_url,
                    threshold=th,
                )
            )

    feasible = [m for m in all_results if m.fpr <= args.fpr_target]
    if feasible:
        feasible.sort(key=lambda m: (-m.recall, -m.f1, m.fpr))
        best = feasible[0]
        ranking_pool = feasible
        reason = f"Selected from candidates with FPR <= {args.fpr_target:.4f}"
    else:
        all_results.sort(key=lambda m: (m.fpr, -m.recall, -m.f1))
        best = all_results[0]
        ranking_pool = all_results
        reason = f"No candidate met FPR target ({args.fpr_target:.4f}); selected minimal FPR candidate."

    top_k = ranking_pool[: max(1, args.top_k)]

    print("Fusion tuning completed.")
    print(f"- Dataset rows: {len(labels)}")
    print(f"- Selection rule: {reason}")
    print("- Best params:")
    print(
        f"  w_url_base={best.w_url_base:.2f}, w_text_base={best.w_text_base:.2f}, "
        f"threshold={best.threshold:.2f}, recall={best.recall:.4f}, fpr={best.fpr:.4f}, f1={best.f1:.4f}"
    )
    print("- Top candidates:")
    for idx, item in enumerate(top_k, start=1):
        print(
            f"  {idx}. w_url={item.w_url_base:.2f}, threshold={item.threshold:.2f}, "
            f"recall={item.recall:.4f}, fpr={item.fpr:.4f}, f1={item.f1:.4f}"
        )

    payload = {
        "csv": str(args.csv),
        "row_count": len(labels),
        "fpr_target": args.fpr_target,
        "selection_reason": reason,
        "best": asdict(best),
        "top_k": [asdict(item) for item in top_k],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"- Output JSON: {args.output_json}")


if __name__ == "__main__":
    main()
