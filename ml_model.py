from __future__ import annotations

from dataclasses import dataclass
from math import exp, log2, sqrt
from typing import Dict

MODEL_BIAS = -1.4
WEIGHT_STD = 1.8
WEIGHT_ENTROPY = 2.0
WEIGHT_TRANSITION = 1.5
WEIGHT_HIGH_INTENSITY = 0.8
WEIGHT_CENTER_INTENSITY = 0.3
STD_NORMALIZATION = 127.5
INTENSITY_MIDPOINT = 127.5


@dataclass(frozen=True)
class ScanResult:
    label: str
    confidence: float
    probability: float
    message: str


def _entropy(byte_counts: Dict[int, int], total: int) -> float:
    entropy = 0.0
    for count in byte_counts.values():
        probability = count / total
        if probability > 0:
            entropy -= probability * log2(probability)
    return entropy / 8.0


def extract_features(image_bytes: bytes) -> Dict[str, float]:
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    total = len(image_bytes)
    mean = sum(image_bytes) / total
    variance = sum((b - mean) ** 2 for b in image_bytes) / total
    std = sqrt(variance)
    high_intensity_ratio = sum(1 for b in image_bytes if b > 200) / total

    transitions = 0
    for index in range(1, total):
        if abs(image_bytes[index] - image_bytes[index - 1]) > 32:
            transitions += 1
    transition_ratio = transitions / max(total - 1, 1)

    counts: Dict[int, int] = {}
    for value in image_bytes:
        counts[value] = counts.get(value, 0) + 1

    entropy = _entropy(counts, total)
    center_intensity = 1.0 - (abs(mean - INTENSITY_MIDPOINT) / INTENSITY_MIDPOINT)

    return {
        "mean": mean / 255.0,
        "std": std / STD_NORMALIZATION,
        "high_intensity_ratio": high_intensity_ratio,
        "transition_ratio": transition_ratio,
        "entropy": entropy,
        "center_intensity": max(0.0, min(center_intensity, 1.0)),
    }


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def predict_scan(image_bytes: bytes) -> ScanResult:
    features = extract_features(image_bytes)

    score = (
        MODEL_BIAS
        + WEIGHT_STD * features["std"]
        + WEIGHT_ENTROPY * features["entropy"]
        + WEIGHT_TRANSITION * features["transition_ratio"]
        + WEIGHT_HIGH_INTENSITY * features["high_intensity_ratio"]
        + WEIGHT_CENTER_INTENSITY * features["center_intensity"]
    )
    probability = _sigmoid(score)

    if probability >= 0.65:
        label = "tumor_suspected"
        message = "High anomaly pattern detected. Please consult a radiologist immediately."
        confidence = probability
    elif probability >= 0.45:
        label = "defect_suspected"
        message = "Moderate anomaly pattern detected. Further clinical review is recommended."
        confidence = probability
    else:
        label = "no_obvious_defect"
        message = "No major anomaly pattern detected by this prototype model."
        confidence = 1.0 - probability

    return ScanResult(
        label=label,
        confidence=round(max(0.0, min(confidence, 1.0)), 4),
        probability=round(max(0.0, min(probability, 1.0)), 4),
        message=message,
    )
