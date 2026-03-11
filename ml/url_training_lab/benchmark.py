#!/usr/bin/env python3
"""Benchmark URL phishing models with a focus on false-positive reduction."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.url_training_lab.features import LexicalFeatureTransformer

DEFAULT_URL_CSV = PROJECT_ROOT / "ml" / "training" / "email_url" / "phishing_site_urls.csv"


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
    parser = argparse.ArgumentParser(description="Benchmark candidate URL phishing models.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_URL_CSV)
    parser.add_argument("--max-rows", type=int, default=120000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fpr-target", type=float, default=0.01)
    parser.add_argument("--threshold-min", type=float, default=0.50)
    parser.add_argument("--threshold-max", type=float, default=0.99)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def load_dataset(csv_path: Path, max_rows: int, seed: int) -> tuple[list[str], list[int]]:
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        rows = list(csv.DictReader(f))

    urls: list[str] = []
    labels: list[int] = []
    for row in rows:
        raw_url = (row.get("URL") or "").strip().strip("'").strip('"')
        raw_label = (row.get("Label") or "").strip().lower()
        if not raw_url or raw_label not in {"bad", "good"}:
            continue
        urls.append(raw_url)
        labels.append(1 if raw_label == "bad" else 0)

    if max_rows > 0 and len(urls) > max_rows:
        rng = random.Random(seed)
        by_label: dict[int, list[int]] = {0: [], 1: []}
        for index, label in enumerate(labels):
            by_label[label].append(index)
        selected: list[int] = []
        for label, idxs in by_label.items():
            rng.shuffle(idxs)
            take = round(max_rows * (len(idxs) / len(urls)))
            selected.extend(idxs[:take])
        selected = sorted(selected[:max_rows])
        urls = [urls[i] for i in selected]
        labels = [labels[i] for i in selected]

    return urls, labels


def build_candidates() -> dict[str, Pipeline]:
    legacy_word_logreg = Pipeline(
        steps=[
            ("vectorizer", CountVectorizer(lowercase=True)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )

    current_char_sgd_balanced = Pipeline(
        steps=[
            (
                "vectorizer",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    lowercase=True,
                    min_df=2,
                    sublinear_tf=True,
                    max_features=220000,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=5e-6,
                    class_weight="balanced",
                    max_iter=2000,
                    tol=1e-3,
                    random_state=42,
                ),
            ),
        ]
    )

    char_tfidf_logreg = Pipeline(
        steps=[
            (
                "vectorizer",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    lowercase=True,
                    min_df=2,
                    sublinear_tf=True,
                    max_features=250000,
                ),
            ),
            ("clf", LogisticRegression(max_iter=1500, C=3.0)),
        ]
    )

    hybrid_char_lex_logreg = Pipeline(
        steps=[
            (
                "features",
                FeatureUnion(
                    transformer_list=[
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                lowercase=True,
                                min_df=2,
                                sublinear_tf=True,
                                max_features=220000,
                            ),
                        ),
                        (
                            "lexical",
                            Pipeline(
                                steps=[
                                    ("extract", LexicalFeatureTransformer()),
                                    ("vectorize", DictVectorizer(sparse=True)),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
            ("clf", LogisticRegression(max_iter=1500, C=2.0)),
        ]
    )

    return {
        "legacy_word_logreg": legacy_word_logreg,
        "current_char_sgd_balanced": current_char_sgd_balanced,
        "char_tfidf_logreg": char_tfidf_logreg,
        "hybrid_char_lex_logreg": hybrid_char_lex_logreg,
    }


def evaluate_at_threshold(y_true: list[int], y_score: list[float], threshold: float) -> Metrics:
    y_pred = [1 if score >= threshold else 0 for score in y_score]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return Metrics(
        threshold=float(threshold),
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        fpr=float(fpr),
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

    urls, labels = load_dataset(args.csv, max_rows=args.max_rows, seed=args.seed)
    x_train, x_tmp, y_train, y_tmp = train_test_split(
        urls,
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
    for name, model in build_candidates().items():
        model.fit(x_train, y_train)
        val_scores = model.predict_proba(x_val)[:, 1]
        chosen = select_threshold(
            y_true=y_val,
            y_score=val_scores.tolist(),
            threshold_min=args.threshold_min,
            threshold_max=args.threshold_max,
            threshold_step=args.threshold_step,
            fpr_target=args.fpr_target,
        )
        test_scores = model.predict_proba(x_test)[:, 1]
        test_metrics = evaluate_at_threshold(y_test, test_scores.tolist(), chosen.threshold)
        results[name] = {
            "selected_on_validation": asdict(chosen),
            "test_metrics": asdict(test_metrics),
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "csv": str(args.csv),
            "rows": len(urls),
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
