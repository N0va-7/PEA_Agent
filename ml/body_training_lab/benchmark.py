#!/usr/bin/env python3
"""Benchmark email body phishing models with a focus on lower false positives."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEXT_CSV = PROJECT_ROOT / "ml" / "training" / "email_text" / "Phishing_Email.csv"


@dataclass
class Metrics:
    threshold: float
    precision: float
    recall: float
    f1: float
    fpr: float
    auc_roc: float
    auc_pr: float
    tn: int
    fp: int
    fn: int
    tp: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark candidate email body phishing models.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_TEXT_CSV)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fpr-target", type=float, default=0.03)
    parser.add_argument("--threshold-min", type=float, default=0.50)
    parser.add_argument("--threshold-max", type=float, default=0.99)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--output-json", type=Path, default=None)
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


def build_candidates(seed: int) -> dict[str, Pipeline]:
    legacy_tfidf_random_forest = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 1),
                    min_df=2,
                    max_features=120000,
                ),
            ),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    current_word_sgd_balanced = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=160000,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=1e-5,
                    class_weight="balanced",
                    max_iter=2000,
                    tol=1e-3,
                    random_state=seed,
                ),
            ),
        ]
    )

    word_tfidf_logreg = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=180000,
                ),
            ),
            ("clf", LogisticRegression(max_iter=3000, C=3.0)),
        ]
    )

    word_char_tfidf_logreg = Pipeline(
        steps=[
            (
                "features",
                FeatureUnion(
                    transformer_list=[
                        (
                            "word",
                            TfidfVectorizer(
                                lowercase=True,
                                strip_accents="unicode",
                                ngram_range=(1, 2),
                                min_df=2,
                                sublinear_tf=True,
                                max_features=140000,
                            ),
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                lowercase=True,
                                ngram_range=(3, 5),
                                min_df=2,
                                sublinear_tf=True,
                                max_features=80000,
                            ),
                        ),
                    ]
                ),
            ),
            ("clf", LogisticRegression(max_iter=3000, C=2.0)),
        ]
    )

    return {
        "legacy_tfidf_random_forest": legacy_tfidf_random_forest,
        "current_word_sgd_balanced": current_word_sgd_balanced,
        "word_tfidf_logreg": word_tfidf_logreg,
        "word_char_tfidf_logreg": word_char_tfidf_logreg,
    }


def score_candidates(model: Pipeline, x_val: list[str]) -> list[float]:
    clf = model.named_steps["clf"]
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_val)[:, 1].tolist()

    decision = model.decision_function(x_val)
    return (1 / (1 + (2.718281828 ** (-decision)))).tolist()


def evaluate_at_threshold(y_true: list[int], y_score: list[float], threshold: float) -> Metrics:
    y_pred = [1 if score >= threshold else 0 for score in y_score]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return Metrics(
        threshold=float(threshold),
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        fpr=float(fp / (fp + tn) if (fp + tn) else 0.0),
        auc_roc=float(roc_auc_score(y_true, y_score)),
        auc_pr=float(average_precision_score(y_true, y_score)),
        tn=int(tn),
        fp=int(fp),
        fn=int(fn),
        tp=int(tp),
    )


def select_threshold(
    y_true: list[int],
    y_score: list[float],
    threshold_min: float,
    threshold_max: float,
    threshold_step: float,
    fpr_target: float,
) -> Metrics:
    candidates: list[Metrics] = []
    current = threshold_min
    while current <= threshold_max + 1e-12:
        candidates.append(evaluate_at_threshold(y_true, y_score, current))
        current += threshold_step

    valid = [item for item in candidates if item.fpr <= fpr_target]
    if valid:
        valid.sort(key=lambda item: (-item.f1, -item.precision, -item.recall, item.threshold))
        return valid[0]

    candidates.sort(key=lambda item: (item.fpr, -item.f1, -item.precision, item.threshold))
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

    results: dict[str, dict] = {}
    for name, model in build_candidates(args.seed).items():
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
        test_scores = model.predict_proba(x_test)[:, 1].tolist()
        test_metrics = evaluate_at_threshold(y_test, test_scores, chosen.threshold)
        results[name] = {
            "selected_on_validation": asdict(chosen),
            "test_metrics": asdict(test_metrics),
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "csv": str(args.csv),
            "rows": len(texts),
            "train_size": len(x_train),
            "val_size": len(x_val),
            "test_size": len(x_test),
            "positive_rate": sum(labels) / max(1, len(labels)),
        },
        "selection_policy": {
            "objective": "maximize_f1_under_fpr_target",
            "fpr_target": args.fpr_target,
            "threshold_min": args.threshold_min,
            "threshold_max": args.threshold_max,
            "threshold_step": args.threshold_step,
        },
        "results": results,
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
