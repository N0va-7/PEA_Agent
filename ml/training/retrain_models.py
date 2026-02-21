#!/usr/bin/env python3
"""Retrain URL/Text phishing models and export artifacts for backend inference."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEXT_CSV = PROJECT_ROOT / "ml" / "training" / "email_text" / "Phishing_Email.csv"
DEFAULT_URL_CSV = PROJECT_ROOT / "ml" / "training" / "email_url" / "phishing_site_urls.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "ml" / "artifacts"


@dataclass
class BinaryMetrics:
    threshold: float
    precision: float
    recall: float
    f1: float
    fpr: float
    tpr: float
    auc: float
    tn: int
    fp: int
    fn: int
    tp: int


@dataclass
class ModelResult:
    name: str
    phishing_label: str
    class_order: list[str]
    train_size: int
    val_size: int
    test_size: int
    selected_threshold: float
    fpr_target: float
    val_metrics: BinaryMetrics
    test_metrics: BinaryMetrics
    artifact_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrain phishing body/url models.")
    parser.add_argument("--text-csv", type=Path, default=DEFAULT_TEXT_CSV)
    parser.add_argument("--url-csv", type=Path, default=DEFAULT_URL_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fpr-target", type=float, default=0.03)
    parser.add_argument("--threshold-min", type=float, default=0.50)
    parser.add_argument("--threshold-max", type=float, default=0.95)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--report-json", type=Path, default=None)
    parser.add_argument("--text-max-rows", type=int, default=0, help="Only use first N text rows (debug).")
    parser.add_argument("--url-max-rows", type=int, default=0, help="Only use first N URL rows (debug).")
    return parser.parse_args()


def _read_csv_records(csv_path: Path) -> list[dict[str, str]]:
    max_csv_field = sys.maxsize
    while True:
        try:
            csv.field_size_limit(max_csv_field)
            break
        except OverflowError:
            max_csv_field = max_csv_field // 10
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _stratified_downsample(
    x: list[str],
    y: list[str],
    max_rows: int,
    seed: int,
) -> tuple[list[str], list[str]]:
    if max_rows <= 0 or len(x) <= max_rows:
        return x, y

    by_class: dict[str, list[int]] = {}
    for idx, label in enumerate(y):
        by_class.setdefault(label, []).append(idx)

    rng = random.Random(seed)
    classes = sorted(by_class.keys())
    selected_indices: list[int] = []
    per_class = max(3, max_rows // max(1, len(classes)))
    for label in classes:
        idxs = by_class[label]
        rng.shuffle(idxs)
        selected_indices.extend(idxs[: min(len(idxs), per_class)])

    if len(selected_indices) < max_rows:
        selected_set = set(selected_indices)
        remaining = [i for i in range(len(x)) if i not in selected_set]
        rng.shuffle(remaining)
        selected_indices.extend(remaining[: max_rows - len(selected_indices)])

    selected_indices = sorted(set(selected_indices[:max_rows]))
    return [x[i] for i in selected_indices], [y[i] for i in selected_indices]


def load_text_dataset(csv_path: Path, max_rows: int = 0, seed: int = 42) -> tuple[list[str], list[str]]:
    rows = _read_csv_records(csv_path)
    x: list[str] = []
    y: list[str] = []
    label_map = {"phishing email": "Phishing Email", "safe email": "Safe Email"}
    for row in rows:
        raw_text = (row.get("Email Text") or "").strip()
        raw_label = (row.get("Email Type") or "").strip().lower()
        if not raw_text:
            continue
        if raw_label not in label_map:
            continue
        x.append(raw_text)
        y.append(label_map[raw_label])
    return _stratified_downsample(x, y, max_rows, seed)


def load_url_dataset(csv_path: Path, max_rows: int = 0, seed: int = 42) -> tuple[list[str], list[str]]:
    rows = _read_csv_records(csv_path)
    x: list[str] = []
    y: list[str] = []
    for row in rows:
        raw_url = (row.get("URL") or "").strip().strip("'").strip('"')
        raw_label = (row.get("Label") or "").strip().lower()
        if not raw_url:
            continue
        if raw_label not in {"bad", "good"}:
            continue
        x.append(raw_url)
        y.append(raw_label)
    return _stratified_downsample(x, y, max_rows, seed)


def build_text_estimator(seed: int) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=160_000,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=1e-5,
                    class_weight="balanced",
                    max_iter=1000,
                    tol=1e-3,
                    random_state=seed,
                ),
            ),
        ]
    )
    return pipeline


def build_url_estimator(seed: int) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    lowercase=True,
                    min_df=2,
                    max_features=200_000,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=5e-6,
                    class_weight="balanced",
                    max_iter=1500,
                    tol=1e-3,
                    random_state=seed,
                ),
            ),
        ]
    )
    return pipeline


def _binarize_labels(y: Sequence[str], phishing_label: str) -> list[int]:
    return [1 if label == phishing_label else 0 for label in y]


def evaluate_at_threshold(
    y_true: Sequence[str],
    y_score: Sequence[float],
    threshold: float,
    phishing_label: str,
) -> BinaryMetrics:
    y_true_bin = _binarize_labels(y_true, phishing_label)
    y_pred_bin = [1 if s >= threshold else 0 for s in y_score]

    tn, fp, fn, tp = confusion_matrix(y_true_bin, y_pred_bin, labels=[0, 1]).ravel()
    precision = precision_score(y_true_bin, y_pred_bin, zero_division=0)
    recall = recall_score(y_true_bin, y_pred_bin, zero_division=0)
    f1 = f1_score(y_true_bin, y_pred_bin, zero_division=0)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    tpr = recall
    auc = roc_auc_score(y_true_bin, y_score)

    return BinaryMetrics(
        threshold=float(threshold),
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        fpr=float(fpr),
        tpr=float(tpr),
        auc=float(auc),
        tn=int(tn),
        fp=int(fp),
        fn=int(fn),
        tp=int(tp),
    )


def select_threshold(
    y_true: Sequence[str],
    y_score: Sequence[float],
    phishing_label: str,
    fpr_target: float,
    min_threshold: float,
    max_threshold: float,
    step: float,
) -> BinaryMetrics:
    current = min_threshold
    candidates: list[BinaryMetrics] = []
    while current <= max_threshold + 1e-12:
        metrics = evaluate_at_threshold(y_true, y_score, current, phishing_label)
        candidates.append(metrics)
        current += step

    valid = [m for m in candidates if m.fpr <= fpr_target]
    if valid:
        # Priority: lower FPR under target, then higher recall/F1.
        valid.sort(key=lambda m: (m.fpr, -m.recall, -m.f1))
        return valid[0]

    # If no threshold meets FPR target, choose the one with minimal FPR.
    candidates.sort(key=lambda m: (m.fpr, -m.recall, -m.f1))
    return candidates[0]


def train_one_model(
    name: str,
    x: list[str],
    y: list[str],
    phishing_label: str,
    estimator_builder: Callable[[int], Pipeline],
    output_path: Path,
    seed: int,
    fpr_target: float,
    threshold_min: float,
    threshold_max: float,
    threshold_step: float,
) -> ModelResult:
    x_train, x_tmp, y_train, y_tmp = train_test_split(
        x,
        y,
        test_size=0.30,
        random_state=seed,
        stratify=y,
    )
    x_val, x_test, y_val, y_test = train_test_split(
        x_tmp,
        y_tmp,
        test_size=0.50,
        random_state=seed,
        stratify=y_tmp,
    )

    selector_model = estimator_builder(seed)
    selector_model.fit(x_train, y_train)
    class_order = [str(c) for c in selector_model.classes_]
    phish_index = class_order.index(phishing_label)

    val_scores = selector_model.predict_proba(x_val)[:, phish_index]
    best_on_val = select_threshold(
        y_true=y_val,
        y_score=val_scores,
        phishing_label=phishing_label,
        fpr_target=fpr_target,
        min_threshold=threshold_min,
        max_threshold=threshold_max,
        step=threshold_step,
    )

    final_model = estimator_builder(seed)
    final_model.fit(x_train + x_val, y_train + y_val)
    final_class_order = [str(c) for c in final_model.classes_]
    phish_index_final = final_class_order.index(phishing_label)
    test_scores = final_model.predict_proba(x_test)[:, phish_index_final]
    test_metrics = evaluate_at_threshold(
        y_true=y_test,
        y_score=test_scores,
        threshold=best_on_val.threshold,
        phishing_label=phishing_label,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, output_path)

    return ModelResult(
        name=name,
        phishing_label=phishing_label,
        class_order=final_class_order,
        train_size=len(x_train),
        val_size=len(x_val),
        test_size=len(x_test),
        selected_threshold=best_on_val.threshold,
        fpr_target=fpr_target,
        val_metrics=best_on_val,
        test_metrics=test_metrics,
        artifact_path=str(output_path),
    )


def main() -> None:
    args = parse_args()

    text_x, text_y = load_text_dataset(args.text_csv, max_rows=args.text_max_rows, seed=args.seed)
    url_x, url_y = load_url_dataset(args.url_csv, max_rows=args.url_max_rows, seed=args.seed)
    if not text_x or not url_x:
        raise RuntimeError("Input dataset is empty after preprocessing. Please check CSV files.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    body_artifact = args.output_dir / "phishing_body.pkl"
    url_artifact = args.output_dir / "phishing_url.pkl"

    text_result = train_one_model(
        name="body_model",
        x=text_x,
        y=text_y,
        phishing_label="Phishing Email",
        estimator_builder=build_text_estimator,
        output_path=body_artifact,
        seed=args.seed,
        fpr_target=args.fpr_target,
        threshold_min=args.threshold_min,
        threshold_max=args.threshold_max,
        threshold_step=args.threshold_step,
    )

    url_result = train_one_model(
        name="url_model",
        x=url_x,
        y=url_y,
        phishing_label="bad",
        estimator_builder=build_url_estimator,
        output_path=url_artifact,
        seed=args.seed,
        fpr_target=args.fpr_target,
        threshold_min=args.threshold_min,
        threshold_max=args.threshold_max,
        threshold_step=args.threshold_step,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "fpr_target": args.fpr_target,
        "text_model": asdict(text_result),
        "url_model": asdict(url_result),
        "recommended_backend": {
            "body_only_threshold": text_result.selected_threshold,
            "fusion_threshold_hint": 0.79,
            "notes": (
                "Use tune_fusion_threshold.py on a labeled email-level validation set "
                "to compute final w_url/w_text/fusion_threshold."
            ),
        },
    }

    if args.report_json is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = args.output_dir / f"retrain_report_{timestamp}.json"
    else:
        report_path = args.report_json
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Retraining completed.")
    print(f"- Body artifact: {body_artifact}")
    print(f"- URL artifact:  {url_artifact}")
    print(f"- Report:        {report_path}")
    print(
        f"- Suggested thresholds: body_only={text_result.selected_threshold:.2f}, "
        f"url_only={url_result.selected_threshold:.2f}"
    )


if __name__ == "__main__":
    main()
