"""Train v2: Small neural network with better feature engineering.

Improvements over v1:
- Condense correlated hours_above features into derived features
- Add interaction features (snowfall * cold = powder indicator)
- 2-layer neural network for non-linear decision boundaries
- Class-balanced loss to avoid collapsing to FAIR
"""

import json
from pathlib import Path

import numpy as np

ML_DIR = Path(__file__).parent
FEATURES_FILE = ML_DIR / "training_features.json"
SCORES_DIR = ML_DIR / "scores"
WEIGHTS_FILE = ML_DIR / "model_weights_v2.json"
VALIDATION_REPORT = ML_DIR / "validation_report_v2.txt"

# Raw feature columns from data collection
RAW_FEATURE_COLUMNS = [
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


def engineer_features(raw_features: dict) -> list[float]:
    """Transform raw features into engineered features for the model.

    Reduces multicollinearity and adds interaction terms.
    Returns a list of float values.
    """
    ct = raw_features["cur_temp"]
    max24 = raw_features["max_temp_24h"]
    max48 = raw_features["max_temp_48h"]
    min24 = raw_features["min_temp_24h"]
    ft_days = raw_features["freeze_thaw_days_ago"]
    warmest = raw_features["warmest_thaw"]
    snow_ft = raw_features["snow_since_freeze_cm"]
    snow24 = raw_features["snowfall_24h_cm"]
    snow72 = raw_features["snowfall_72h_cm"]
    elev = raw_features["elevation_m"]

    # Hours above thresholds since freeze-thaw
    ha0 = raw_features["total_hours_above_0C_since_ft"]
    ha3 = raw_features["total_hours_above_3C_since_ft"]
    ha6 = raw_features["total_hours_above_6C_since_ft"]

    # Current warm spell hours
    ca0 = raw_features["cur_hours_above_0C"]
    ca3 = raw_features["cur_hours_above_3C"]
    ca6 = raw_features["cur_hours_above_6C"]

    return [
        # Temperature features (4)
        ct,
        max24,
        min24,
        max48 - max24,  # temperature trend (warming or cooling)
        # Freeze-thaw features (3)
        min(ft_days, 14.0),  # cap at 14 (no freeze-thaw detected)
        warmest,
        warmest * (1.0 / max(ft_days, 0.1)),  # thaw intensity / recency
        # Snowfall features (4)
        snow_ft,
        snow24,
        snow72,
        snow72 - snow24,  # older snow accumulation
        # Elevation (1)
        elev / 1000.0,  # normalize to km
        # Warm hours since freeze-thaw (condensed from 7 to 3)
        ha0,  # any above-freezing exposure
        ha3,  # significant warming
        ha6,  # extreme warming
        # Current warm spell (condensed from 7 to 3)
        ca0,
        ca3,
        ca6,
        # Interaction features (6) - these capture the non-linear relationships
        snow24 * max(0, -ct) / 10.0,  # fresh powder indicator (snow * cold)
        snow_ft * max(0, -ct) / 10.0,  # accumulated powder indicator
        max(0, ct) * ca0,  # warm degradation indicator
        max(0, max24 - 3) * ha3,  # severe thaw damage
        snow24 * (1.0 if ct < 0 else 0.5),  # fresh snow adjusted for temp
        1.0 if (ct > 10 and ca0 > 48) else 0.0,  # summer/no-snow flag
    ]


ENGINEERED_FEATURE_NAMES = [
    "cur_temp",
    "max_temp_24h",
    "min_temp_24h",
    "temp_trend_48h",
    "freeze_thaw_days_ago",
    "warmest_thaw",
    "thaw_intensity_recency",
    "snow_since_freeze_cm",
    "snowfall_24h_cm",
    "snowfall_72h_cm",
    "older_snow_accum",
    "elevation_km",
    "hours_above_0C_ft",
    "hours_above_3C_ft",
    "hours_above_6C_ft",
    "cur_hours_above_0C",
    "cur_hours_above_3C",
    "cur_hours_above_6C",
    "fresh_powder_indicator",
    "accumulated_powder_indicator",
    "warm_degradation",
    "severe_thaw_damage",
    "temp_adjusted_fresh_snow",
    "summer_flag",
]


def load_data(historical_weight=1.0):
    """Load features and merge with scores.

    Loads real data, synthetic data, and optionally historical data.
    Returns X, y, metadata, source_weights arrays.

    Args:
        historical_weight: Weight multiplier for historical samples (0.0 to exclude,
            1.0 for full weight, 0.3-0.5 recommended due to noisier labels).
    """
    features_by_key = {}
    source_by_key = {}

    # Load real features
    with open(FEATURES_FILE) as f:
        features_data = json.load(f)
    for item in features_data["data"]:
        key = (item["resort_id"], item["date"])
        features_by_key[key] = item
        source_by_key[key] = "real"

    # Load synthetic features if available
    synthetic_file = ML_DIR / "synthetic_features.json"
    if synthetic_file.exists():
        with open(synthetic_file) as f:
            synth_data = json.load(f)
        for item in synth_data["data"]:
            key = (item["resort_id"], item["date"])
            features_by_key[key] = item
            source_by_key[key] = "synthetic"
        print(f"  + {len(synth_data['data'])} synthetic samples")

    # Load historical features if available
    historical_file = ML_DIR / "historical_features.json"
    if historical_file.exists() and historical_weight > 0:
        with open(historical_file) as f:
            hist_data = json.load(f)
        for item in hist_data["data"]:
            key = (item["resort_id"], item["date"])
            features_by_key[key] = item
            source_by_key[key] = "historical"
        print(
            f"  + {len(hist_data['data'])} historical samples (weight={historical_weight})"
        )

    # Load all score files
    scores_by_key = {}
    for score_file in sorted(SCORES_DIR.glob("scores_*.json")):
        with open(score_file) as f:
            scores = json.load(f)
        for item in scores:
            key = (item["resort_id"], item["date"])
            scores_by_key[key] = item["score"]

    print(f"Loaded {len(features_by_key)} features and {len(scores_by_key)} scores")

    X = []
    y = []
    metadata = []
    source_weights = []
    for key, features in features_by_key.items():
        if key in scores_by_key:
            row = engineer_features(features)
            X.append(row)
            y.append(scores_by_key[key])
            source = source_by_key.get(key, "real")
            metadata.append({"resort_id": key[0], "date": key[1], "source": source})
            source_weights.append(historical_weight if source == "historical" else 1.0)

    return (
        np.array(X, dtype=np.float64),
        np.array(y, dtype=np.float64),
        metadata,
        np.array(source_weights, dtype=np.float64),
    )


# --- Neural Network ---


def relu(x):
    return np.maximum(0, x)


def relu_grad(x):
    return (x > 0).astype(float)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


class SimpleNN:
    """2-layer neural network: input → hidden → output."""

    def __init__(self, n_input, n_hidden=32):
        # He initialization
        self.W1 = np.random.randn(n_input, n_hidden) * np.sqrt(2.0 / n_input)
        self.b1 = np.zeros(n_hidden)
        self.W2 = np.random.randn(n_hidden, 1) * np.sqrt(2.0 / n_hidden)
        self.b2 = np.zeros(1)

    def forward(self, X):
        """Forward pass. Returns prediction and cache for backprop."""
        Z1 = X @ self.W1 + self.b1
        A1 = relu(Z1)
        Z2 = A1 @ self.W2 + self.b2
        # Output: scale to [1, 6] range using shifted sigmoid
        out = sigmoid(Z2) * 5.0 + 1.0
        return out.flatten(), {"Z1": Z1, "A1": A1, "Z2": Z2, "X": X}

    def backward(self, y_true, y_pred, cache, sample_weights=None):
        """Backward pass. Returns gradients."""
        n = len(y_true)
        if sample_weights is None:
            sample_weights = np.ones(n)

        # d(loss)/d(out) = 2/n * (y_pred - y_true) * weight
        d_out = (2.0 / n) * (y_pred - y_true) * sample_weights

        # d(out)/d(Z2): derivative of sigmoid * 5 + 1
        sig = (y_pred - 1.0) / 5.0  # recover sigmoid output
        d_Z2 = d_out * (sig * (1 - sig) * 5.0)
        d_Z2 = d_Z2.reshape(-1, 1)

        # Gradients for W2, b2
        dW2 = cache["A1"].T @ d_Z2
        db2 = d_Z2.sum(axis=0)

        # Backprop through hidden layer
        d_A1 = d_Z2 @ self.W2.T
        d_Z1 = d_A1 * relu_grad(cache["Z1"])

        # Gradients for W1, b1
        dW1 = cache["X"].T @ d_Z1
        db1 = d_Z1.sum(axis=0)

        return {"dW1": dW1, "db1": db1, "dW2": dW2, "db2": db2}

    def update(self, grads, lr, weight_decay=1e-4):
        """Update weights with gradient descent + L2 regularization."""
        self.W1 -= lr * (grads["dW1"] + weight_decay * self.W1)
        self.b1 -= lr * grads["db1"]
        self.W2 -= lr * (grads["dW2"] + weight_decay * self.W2)
        self.b2 -= lr * grads["db2"]

    def predict(self, X):
        out, _ = self.forward(X)
        return np.clip(out, 1.0, 6.0)


def compute_sample_weights(y):
    """Compute inverse-frequency weights for class balancing."""
    # Map scores to quality levels
    quality_bins = np.digitize(y, bins=[1.5, 2.5, 3.5, 4.5, 5.5])
    unique, counts = np.unique(quality_bins, return_counts=True)
    total = len(y)
    weights = np.ones(len(y))
    for cls, cnt in zip(unique, counts):
        w = total / (len(unique) * cnt)
        weights[quality_bins == cls] = w
    return weights


def normalize_features(X):
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-8] = 1.0
    X_norm = (X - mean) / std
    return X_norm, mean, std


def score_to_quality(score):
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
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    true_quality = [score_to_quality(s) for s in y_true]
    pred_quality = [score_to_quality(s) for s in y_pred]
    accuracy = sum(1 for t, p in zip(true_quality, pred_quality) if t == p) / len(
        y_true
    )

    quality_order = ["horrible", "bad", "poor", "fair", "good", "excellent"]
    within_1 = sum(
        1
        for t, p in zip(true_quality, pred_quality)
        if abs(quality_order.index(t) - quality_order.index(p)) <= 1
    ) / len(y_true)

    lines = [
        f"{'=' * 60}",
        "Model Evaluation Report (v2 - Neural Network)",
        f"{'=' * 60}",
        f"Samples: {len(y_true)}",
        f"MAE: {mae:.3f}",
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

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "accuracy": accuracy,
        "within_1": within_1,
    }


def train_model(
    X_train,
    y_train,
    X_val,
    y_val,
    weights,
    meta_val,
    hidden_sizes=None,
    seeds=None,
    n_epochs=3000,
    checkpoint_interval=50,
    verbose=True,
):
    """Train model with grid search over hidden sizes and seeds.

    Uses fine-grained checkpointing to find optimal training epoch.
    Selection metric combines MAE with within-1 accuracy to avoid
    selecting models that overfit on average error but miss quality levels.

    Returns (best_model, best_model_state, best_val_mae).
    """
    if hidden_sizes is None:
        hidden_sizes = [16, 24, 32, 48, 64]
    if seeds is None:
        seeds = [7, 42, 77, 123, 256, 512, 777, 1234]

    quality_order = ["horrible", "bad", "poor", "fair", "good", "excellent"]
    n_features = X_train.shape[1]
    best_score = float("inf")
    best_val_mae = float("inf")
    best_model_state = None
    batch_size = 64
    total_configs = len(hidden_sizes) * len(seeds)
    config_num = 0

    for n_hidden in hidden_sizes:
        for seed in seeds:
            config_num += 1
            np.random.seed(seed)
            model = SimpleNN(n_features, n_hidden=n_hidden)
            lr = 0.01

            for epoch in range(n_epochs):
                perm = np.random.permutation(len(X_train))

                for start in range(0, len(X_train), batch_size):
                    batch_idx = perm[start : start + batch_size]
                    X_batch = X_train[batch_idx]
                    y_batch = y_train[batch_idx]
                    w_batch = weights[batch_idx]

                    y_pred, cache = model.forward(X_batch)
                    grads = model.backward(y_batch, y_pred, cache, w_batch)
                    model.update(grads, lr)

                if epoch > 0 and epoch % 500 == 0:
                    lr *= 0.5

                # Fine-grained checkpointing
                should_eval = epoch % checkpoint_interval == 0 or epoch == n_epochs - 1
                if should_eval:
                    val_pred = model.predict(X_val)
                    val_mae = np.mean(np.abs(y_val - val_pred))

                    # Compute within-1 accuracy for selection metric
                    tq = [score_to_quality(s) for s in y_val]
                    pq = [score_to_quality(s) for s in val_pred]
                    within_1 = sum(
                        1
                        for t, p in zip(tq, pq)
                        if abs(quality_order.index(t) - quality_order.index(p)) <= 1
                    ) / len(y_val)

                    # Combined score: prioritize within-1 = 100%, then minimize MAE
                    # Penalty of 1.0 for each % below 100% within-1
                    within_1_penalty = max(0, 1.0 - within_1) * 5.0
                    combined_score = val_mae + within_1_penalty

                    if verbose and epoch % 500 == 0:
                        train_pred = model.predict(X_train)
                        train_mae = np.mean(np.abs(y_train - train_pred))
                        print(
                            f"  [{config_num}/{total_configs}] "
                            f"h={n_hidden} s={seed} ep={epoch}: "
                            f"train={train_mae:.3f} val={val_mae:.3f} "
                            f"w1={within_1:.1%} lr={lr:.5f}"
                        )

                    if combined_score < best_score:
                        best_score = combined_score
                        best_val_mae = val_mae
                        best_model_state = {
                            "n_hidden": n_hidden,
                            "seed": seed,
                            "epoch": epoch,
                            "within_1": within_1,
                            "W1": model.W1.copy(),
                            "b1": model.b1.copy(),
                            "W2": model.W2.copy(),
                            "b2": model.b2.copy(),
                        }

            if verbose:
                print(
                    f"  -> Config h={n_hidden} s={seed} done. "
                    f"Best so far: h={best_model_state['n_hidden']} "
                    f"s={best_model_state['seed']} "
                    f"ep={best_model_state['epoch']} "
                    f"mae={best_val_mae:.3f} "
                    f"w1={best_model_state['within_1']:.1%}"
                )

    model = SimpleNN(n_features, n_hidden=best_model_state["n_hidden"])
    model.W1 = best_model_state["W1"]
    model.b1 = best_model_state["b1"]
    model.W2 = best_model_state["W2"]
    model.b2 = best_model_state["b2"]
    return model, best_model_state, best_val_mae


def evaluate_by_source(y_true, y_pred, metadata):
    """Evaluate model performance broken down by data source."""
    quality_order = ["horrible", "bad", "poor", "fair", "good", "excellent"]
    sources = set(m.get("source", "real") for m in metadata)
    results = {}
    for src in sorted(sources):
        mask = [i for i, m in enumerate(metadata) if m.get("source", "real") == src]
        if not mask:
            continue
        yt = y_true[mask]
        yp = y_pred[mask]
        mae = np.mean(np.abs(yt - yp))
        tq = [score_to_quality(s) for s in yt]
        pq = [score_to_quality(s) for s in yp]
        exact = sum(1 for t, p in zip(tq, pq) if t == p) / len(yt)
        w1 = sum(
            1
            for t, p in zip(tq, pq)
            if abs(quality_order.index(t) - quality_order.index(p)) <= 1
        ) / len(yt)
        results[src] = {"n": len(mask), "mae": mae, "exact": exact, "within_1": w1}
        print(
            f"  {src:>12s} (n={len(mask):4d}): MAE={mae:.3f}, Exact={exact:.1%}, Within-1={w1:.1%}"
        )
    return results


def main(historical_weight=None):
    import sys

    # Parse historical weight from command line or argument
    if historical_weight is None:
        historical_weight = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

    print(f"\n{'=' * 60}")
    print(f"Training with historical_weight={historical_weight}")
    print(f"{'=' * 60}")

    X_raw, y, metadata, source_weights = load_data(historical_weight=historical_weight)
    print(f"Data: {X_raw.shape[0]} samples, {X_raw.shape[1]} engineered features")

    # Split 80/20
    np.random.seed(42)
    n = len(y)
    indices = np.random.permutation(n)
    split = int(0.8 * n)
    train_idx = indices[:split]
    val_idx = indices[split:]

    X_train_raw, y_train = X_raw[train_idx], y[train_idx]
    X_val_raw, y_val = X_raw[val_idx], y[val_idx]
    meta_train = [metadata[i] for i in train_idx]
    meta_val = [metadata[i] for i in val_idx]
    source_weights_train = source_weights[train_idx]

    # Normalize
    X_train, mean, std = normalize_features(X_train_raw)
    X_val = (X_val_raw - mean) / std

    # Sample weights: class balancing * source weights
    class_weights = compute_sample_weights(y_train)
    weights = class_weights * source_weights_train

    # Train
    model, best_model_state, best_val_mae = train_model(
        X_train, y_train, X_val, y_val, weights, meta_val
    )

    print(f"\nBest model: h={best_model_state['n_hidden']}, val_mae={best_val_mae:.3f}")

    # Final evaluation
    y_train_pred = model.predict(X_train)
    print("\n--- Training Set ---")
    train_metrics = evaluate(y_train, y_train_pred, meta_train)
    print("\n  By source:")
    evaluate_by_source(y_train, y_train_pred, meta_train)

    y_val_pred = model.predict(X_val)
    print("\n--- Validation Set ---")
    val_metrics = evaluate(y_val, y_val_pred, meta_val, VALIDATION_REPORT)
    print("\n  By source:")
    source_metrics = evaluate_by_source(y_val, y_val_pred, meta_val)

    # Save model
    model_data = {
        "version": "v2",
        "type": "neural_network",
        "architecture": {
            "input_size": X_train.shape[1],
            "hidden_size": best_model_state["n_hidden"],
            "output_size": 1,
            "activation": "relu",
            "output_activation": "sigmoid_scaled",
        },
        "engineered_feature_names": ENGINEERED_FEATURE_NAMES,
        "raw_feature_columns": RAW_FEATURE_COLUMNS,
        "weights": {
            "W1": best_model_state["W1"].tolist(),
            "b1": best_model_state["b1"].tolist(),
            "W2": best_model_state["W2"].tolist(),
            "b2": best_model_state["b2"].tolist(),
        },
        "normalization": {
            "mean": mean.tolist(),
            "std": std.tolist(),
        },
        "quality_thresholds": {
            "excellent": 5.5,
            "good": 4.5,
            "fair": 3.5,
            "poor": 2.5,
            "bad": 1.5,
            "horrible": 0.0,
        },
        "training_config": {
            "historical_weight": historical_weight,
            "n_samples": len(y),
        },
        "metrics": {
            "train": {k: float(v) for k, v in train_metrics.items()},
            "validation": {k: float(v) for k, v in val_metrics.items()},
            "validation_by_source": {
                k: {
                    kk: float(vv) if isinstance(vv, (float, np.floating)) else vv
                    for kk, vv in v.items()
                }
                for k, v in source_metrics.items()
            },
        },
    }

    with open(WEIGHTS_FILE, "w") as f:
        json.dump(model_data, f, indent=2)
    print(f"\nModel saved to {WEIGHTS_FILE}")


if __name__ == "__main__":
    main()
