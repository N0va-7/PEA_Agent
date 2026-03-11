from __future__ import annotations

from collections.abc import Iterable


def _resolve_classes(model) -> list:
    classes = getattr(model, "classes_", None)
    if classes is not None:
        return list(classes)
    steps = getattr(model, "steps", None)
    if steps:
        final_estimator = steps[-1][1]
        classes = getattr(final_estimator, "classes_", None)
        if classes is not None:
            return list(classes)
    named_steps = getattr(model, "named_steps", None)
    if named_steps:
        try:
            final_estimator = list(named_steps.values())[-1]
        except Exception:
            final_estimator = None
        classes = getattr(final_estimator, "classes_", None) if final_estimator is not None else None
        if classes is not None:
            return list(classes)
    return []


def _is_positive_label(label, positive_markers: tuple[str, ...]) -> bool:
    if isinstance(label, bool):
        return bool(label)
    if isinstance(label, int):
        return label == 1
    if isinstance(label, float):
        return int(label) == 1 if label.is_integer() else False
    normalized = str(label).strip().lower()
    if normalized in {"1", "true"}:
        return True
    return any(marker in normalized for marker in positive_markers)


def extract_binary_probabilities(
    model,
    prediction: Iterable[float],
    *,
    positive_markers: tuple[str, ...],
) -> tuple[float, float]:
    values = [float(item) for item in prediction]
    if not values:
        return 0.0, 0.0

    positive_index = 0
    classes = _resolve_classes(model)
    for index, label in enumerate(classes):
        if _is_positive_label(label, positive_markers):
            positive_index = index
            break

    phishing_probability = values[positive_index]
    legitimate_probability = 1.0 - phishing_probability if len(values) == 2 else max(0.0, 1.0 - phishing_probability)
    return phishing_probability, legitimate_probability
