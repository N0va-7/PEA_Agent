#!/usr/bin/env python3
"""Train one email body candidate model in an isolated experiment directory."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.body_training_lab.benchmark import DEFAULT_TEXT_CSV, build_candidates


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "ml" / "body_training_lab" / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train one email body candidate model.")
    parser.add_argument("--candidate", choices=sorted(build_candidates(42).keys()), default="word_char_tfidf_logreg")
    parser.add_argument("--csv", type=Path, default=DEFAULT_TEXT_CSV)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fpr-target", type=float, default=0.03)
    parser.add_argument("--threshold-min", type=float, default=0.50)
    parser.add_argument("--threshold-max", type=float, default=0.99)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _set_csv_limit() -> None:
    max_csv_field = sys.maxsize
    while True:
        try:
            csv.field_size_limit(max_csv_field)
            return
        except OverflowError:
            max_csv_field //= 10


def load_dataset(csv_path: Path, max_rows: int, seed: int) -> tuple[list[str], list[int]]:
    _set_csv_limit()
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        rows = list(csv.DictReader(f))

    texts: list[str] = []
    labels: list[int] = []
    label_map = {"phishing email": 1, "safe email": 0}
    for row in rows:
        raw_text = (row.get("Email Text") or "").strip()
        raw_label = (row.get("Email Type") or "").strip().lower()
        if not raw_text or raw_label not in label_map:
            continue
        texts.append(raw_text)
        labels.append(label_map[raw_label])

    if max_rows > 0 and len(texts) > max_rows:
        rng = random.Random(seed)
        by_label: dict[int, list[int]] = {0: [], 1: []}
        for idx, label in enumerate(labels):
            by_label[label].append(idx)
        selected: list[int] = []
        for idxs in by_label.values():
            rng.shuffle(idxs)
            take = round(max_rows * (len(idxs) / len(texts)))
            selected.extend(idxs[:take])
        selected = sorted(selected[:max_rows])
        texts = [texts[i] for i in selected]
        labels = [labels[i] for i in selected]

    return texts, labels


def evaluate(y_true: list[int], y_score: list[float], threshold: float) -> dict[str, float | int]:
    y_pred = [1 if score >= threshold else 0 for score in y_score]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "fpr": float(fp / (fp + tn) if (fp + tn) else 0.0),
        "auc_roc": float(roc_auc_score(y_true, y_score)),
        "auc_pr": float(average_precision_score(y_true, y_score)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def select_threshold(
    y_true: list[int],
    y_score: list[float],
    threshold_min: float,
    threshold_max: float,
    threshold_step: float,
    fpr_target: float,
) -> dict[str, float | int]:
    candidates = []
    current = threshold_min
    while current <= threshold_max + 1e-12:
        candidates.append(evaluate(y_true, y_score, current))
        current += threshold_step
    valid = [item for item in candidates if float(item["fpr"]) <= fpr_target]
    if valid:
        valid.sort(key=lambda item: (-float(item["f1"]), -float(item["precision"]), -float(item["recall"]), float(item["threshold"])))
        return valid[0]
    candidates.sort(key=lambda item: (float(item["fpr"]), -float(item["f1"]), -float(item["precision"]), float(item["threshold"])))
    return candidates[0]


def main() -> None:
    args = parse_args()
    texts, labels = load_dataset(args.csv, args.max_rows, args.seed)
    x_train, x_tmp, y_train, y_tmp = train_test_split(
        texts,
        labels,
        test_size=0.30,
        random_state=args.seed,
        stratify=labels,
    )
    x_val, x_test, y_val, y_test = train_test_split(
        x_tmp,
        y_tmp,
        test_size=0.50,
        random_state=args.seed,
        stratify=y_tmp,
    )

    model = build_candidates(args.seed)[args.candidate]
    model.fit(x_train, y_train)
    val_scores = model.predict_proba(x_val)[:, 1].tolist()
    chosen = select_threshold(
        y_true=y_val,
        y_score=val_scores,
        threshold_min=args.threshold_min,
        threshold_max=args.threshold_max,
        threshold_step=args.threshold_step,
        fpr_target=args.fpr_target,
    )

    final_model = build_candidates(args.seed)[args.candidate]
    final_model.fit(x_train + x_val, y_train + y_val)
    test_scores = final_model.predict_proba(x_test)[:, 1].tolist()
    test_metrics = evaluate(y_test, test_scores, float(chosen["threshold"]))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = args.output_dir / f"{args.candidate}_{timestamp}.joblib"
    report_path = args.output_dir / f"{args.candidate}_{timestamp}.json"
    joblib.dump(final_model, artifact_path)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate": args.candidate,
        "artifact_path": str(artifact_path),
        "dataset_rows": len(texts),
        "selection_policy": {
            "objective": "maximize_f1_under_fpr_target",
            "fpr_target": args.fpr_target,
        },
        "selected_on_validation": chosen,
        "test_metrics": test_metrics,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
