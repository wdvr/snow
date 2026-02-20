"""Train a linear regression model for snow quality scoring.

Reads features from training_features.json and scores from ml/scores/*.json,
trains a model, evaluates on held-out validation set, and exports weights.
"""

import json
import os
from pathlib import Path

import numpy as np

ML_DIR = Path(__file__).parent
FEATURES_FILE = ML_DIR / "training_features.json"
SCORES_DIR = ML_DIR / "scores"
WEIGHTS_FILE = ML_DIR / "model_weights.json"
VALIDATION_REPORT = ML_DIR / "validation_report.txt"

# Feature columns in order (must match backend integration)
FEATURE_COLUMNS = [
    "cur_temp",
    "max_temp_24h",
    "max_temp_48h",
    "min_temp_24h",
    "freeze_thaw_days_ago",
    "warmest_thaw",
    "snow_since_freeze_cm",
    "snowfall_24h_cm",
    "snowfall_72h_cm",
    "elevation_m",
    "total_hours_above_0C_since_ft",
    "total_hours_above_1C_since_ft",
    "total_hours_above_2C_since_ft",
    "total_hours_above_3C_since_ft",
    "total_hours_above_4C_since_ft",
    "total_hours_above_5C_since_ft",
    "total_hours_above_6C_since_ft",
    "cur_hours_above_0C",
    "cur_hours_above_1C",
    "cur_hours_above_2C",
    "cur_hours_above_3C",
    "cur_hours_above_4C",
    "cur_hours_above_5C",
    "cur_hours_above_6C",
]


def load_data():
    """Load features and merge with scores."""
    # Load features
    with open(FEATURES_FILE) as f:
        features_data = json.load(f)

    # Index features by (resort_id, date)
    features_by_key = {}
    for item in features_data["data"]:
        key = (item["resort_id"], item["date"])
        features_by_key[key] = item

    # Load all score files
    scores_by_key = {}
    for score_file in sorted(SCORES_DIR.glob("scores_*.json")):
        with open(score_file) as f:
            scores = json.load(f)
        for item in scores:
            key = (item["resort_id"], item["date"])
            scores_by_key[key] = item["score"]

    print(
        f"Loaded {len(features_by_key)} feature vectors and {len(scores_by_key)} scores"
    )

    # Merge
    X = []
    y = []
    metadata = []
    missing = 0
    for key, features in features_by_key.items():
        if key in scores_by_key:
            row = [features[col] for col in FEATURE_COLUMNS]
            X.append(row)
            y.append(scores_by_key[key])
            metadata.append({"resort_id": key[0], "date": key[1]})
        else:
            missing += 1

    if missing > 0:
        print(f"Warning: {missing} samples missing scores")

    return np.array(X, dtype=np.float64), np.array(y, dtype=np.float64), metadata


def normalize_features(X):
    """Normalize features to zero mean, unit variance. Returns (X_norm, mean, std)."""
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    # Avoid division by zero for constant features
    std[std < 1e-8] = 1.0
    X_norm = (X - mean) / std
    return X_norm, mean, std


def train_linear_regression(X, y):
    """Train with ordinary least squares + L2 regularization (Ridge regression)."""
    # Add bias column
    X_bias = np.column_stack([X, np.ones(len(X))])

    # Ridge regression: (X^T X + λI)^(-1) X^T y
    lambda_reg = 0.01
    n_features = X_bias.shape[1]
    identity = np.eye(n_features)
    identity[-1, -1] = 0  # Don't regularize bias

    weights = np.linalg.solve(X_bias.T @ X_bias + lambda_reg * identity, X_bias.T @ y)

    return weights[:-1], weights[-1]  # (weights, bias)


def predict(X, weights, bias):
    """Predict scores, clipped to [1, 6]."""
    raw = X @ weights + bias
    return np.clip(raw, 1.0, 6.0)


def score_to_quality(score):
    """Convert numeric score to quality label."""
    if score >= 5.5:
        return "excellent"
    elif score >= 4.5:
        return "good"
    elif score >= 3.5:
        return "fair"
    elif score >= 2.5:
        return "poor"
    elif score >= 1.5:
        return "bad"
    else:
        return "horrible"


def evaluate(y_true, y_pred, metadata, report_file=None):
    """Evaluate model performance."""
    # Regression metrics
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    r2 = 1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - np.mean(y_true)) ** 2)

    # Classification accuracy (when rounded to quality levels)
    true_quality = [score_to_quality(s) for s in y_true]
    pred_quality = [score_to_quality(s) for s in y_pred]
    accuracy = sum(1 for t, p in zip(true_quality, pred_quality) if t == p) / len(
        y_true
    )

    # Within-1 accuracy (prediction is at most 1 quality level off)
    quality_order = ["horrible", "bad", "poor", "fair", "good", "excellent"]
    within_1 = sum(
        1
        for t, p in zip(true_quality, pred_quality)
        if abs(quality_order.index(t) - quality_order.index(p)) <= 1
    ) / len(y_true)

    lines = [
        f"{'=' * 60}",
        "Model Evaluation Report",
        f"{'=' * 60}",
        f"Samples: {len(y_true)}",
        f"MAE: {mae:.3f} (mean absolute error in score units)",
        f"RMSE: {rmse:.3f}",
        f"R²: {r2:.3f}",
        f"Exact quality match: {accuracy:.1%}",
        f"Within-1 quality level: {within_1:.1%}",
        "",
        "Score distribution:",
        f"  True  - mean: {y_true.mean():.2f}, std: {y_true.std():.2f}",
        f"  Pred  - mean: {y_pred.mean():.2f}, std: {y_pred.std():.2f}",
        "",
    ]

    # Quality confusion summary
    from collections import Counter

    confusion = Counter()
    for t, p in zip(true_quality, pred_quality):
        confusion[(t, p)] += 1

    lines.append("Quality confusion (true → predicted):")
    for true_q in quality_order:
        preds = {p: c for (t, p), c in confusion.items() if t == true_q}
        if preds:
            pred_str = ", ".join(
                f"{p}={c}" for p, c in sorted(preds.items(), key=lambda x: -x[1])
            )
            total = sum(preds.values())
            lines.append(f"  {true_q:>10s} ({total:3d}): {pred_str}")

    # Worst predictions
    errors = np.abs(y_true - y_pred)
    worst_idx = np.argsort(-errors)[:15]
    lines.append("\nWorst 15 predictions:")
    lines.append(
        f"  {'Resort':<35s} {'Date':<12s} {'True':>5s} {'Pred':>5s} {'Error':>5s}"
    )
    for idx in worst_idx:
        m = metadata[idx]
        lines.append(
            f"  {m['resort_id']:<35s} {m['date']:<12s} "
            f"{y_true[idx]:>5.1f} {y_pred[idx]:>5.1f} {errors[idx]:>5.2f}"
        )

    report = "\n".join(lines)
    print(report)

    if report_file:
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\nReport saved to {report_file}")

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "accuracy": accuracy,
        "within_1": within_1,
    }


def main():
    # Load data
    X_raw, y, metadata = load_data()
    print(f"Training data: {X_raw.shape[0]} samples, {X_raw.shape[1]} features")

    # Split into train (80%) and validation (20%)
    np.random.seed(42)
    n = len(y)
    indices = np.random.permutation(n)
    split = int(0.8 * n)
    train_idx = indices[:split]
    val_idx = indices[split:]

    X_train_raw, y_train = X_raw[train_idx], y[train_idx]
    X_val_raw, y_val = X_raw[val_idx], y[val_idx]
    meta_val = [metadata[i] for i in val_idx]

    # Normalize using training stats
    X_train, mean, std = normalize_features(X_train_raw)
    X_val = (X_val_raw - mean) / std

    # Train
    weights, bias = train_linear_regression(X_train, y_train)

    # Evaluate on training set
    y_train_pred = predict(X_train, weights, bias)
    print("\n--- Training Set ---")
    train_metrics = evaluate(y_train, y_train_pred, [metadata[i] for i in train_idx])

    # Evaluate on validation set
    y_val_pred = predict(X_val, weights, bias)
    print("\n--- Validation Set ---")
    val_metrics = evaluate(y_val, y_val_pred, meta_val, VALIDATION_REPORT)

    # Feature importance (absolute weight magnitude)
    importance = np.abs(weights)
    importance_order = np.argsort(-importance)
    print("\nFeature importance (top 10):")
    for i, idx in enumerate(importance_order[:10]):
        print(f"  {i + 1}. {FEATURE_COLUMNS[idx]:<35s} weight={weights[idx]:>7.3f}")

    # Save model weights
    model = {
        "feature_columns": FEATURE_COLUMNS,
        "weights": weights.tolist(),
        "bias": float(bias),
        "normalization": {
            "mean": mean.tolist(),
            "std": std.tolist(),
        },
        "metrics": {
            "train": {k: float(v) for k, v in train_metrics.items()},
            "validation": {k: float(v) for k, v in val_metrics.items()},
        },
        "quality_thresholds": {
            "excellent": 5.5,
            "good": 4.5,
            "fair": 3.5,
            "poor": 2.5,
            "bad": 1.5,
            "horrible": 0.0,
        },
    }

    with open(WEIGHTS_FILE, "w") as f:
        json.dump(model, f, indent=2)
    print(f"\nModel weights saved to {WEIGHTS_FILE}")


if __name__ == "__main__":
    main()
