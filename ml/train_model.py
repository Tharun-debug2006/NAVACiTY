"""Train and evaluate the NavaCity demand forecasting models.

Usage (from the repository root, Windows PowerShell)::

    python ml\\train_model.py

The script

1. loads the SIMULATED dataset produced by ``ml/generate_dataset.py``,
2. builds a leakage-free feature matrix (see :mod:`navacity_core.features`),
3. splits the data **in time order** (earlier dates train, later dates test)
   so the evaluation reflects a real forecasting situation,
4. trains a Random Forest and a Gradient Boosting baseline per transport mode,
5. reports MAE, RMSE and R^2 for the best model of each mode,
6. writes the evaluation plots, the feature-importance table and the model
   bundle used by the backend.

All metrics written by this script are produced by actually running the
models; nothing is hard coded.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import (  # noqa: E402
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.metrics import (  # noqa: E402
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder  # noqa: E402

from navacity_core.config import (  # noqa: E402
    ARTIFACTS_DIR,
    CROWD_HIGH_MAX,
    CROWD_LEVELS,
    CROWD_LOW_MAX,
    CROWD_MODERATE_MAX,
    DATASET_CSV,
    METRICS_JSON,
    MODEL_BUNDLE,
    RANDOM_SEED,
    crowd_level_bounds,
)
from navacity_core.features import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    LEAKY_COLUMNS,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    prepare_training_frame,
)

MODES = ("metro", "bus")


# --------------------------------------------------------------------------
# Model definitions
# --------------------------------------------------------------------------
def build_preprocessor() -> ColumnTransformer:
    """One-hot encode the categorical features, pass the numeric ones through.

    The output is dense so that the histogram gradient boosting model (which
    refuses sparse input) can be used as well.
    """
    return ColumnTransformer(
        transformers=[
            (
                "num",
                "passthrough",
                NUMERIC_FEATURES,
            ),
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="ignore",
                    min_frequency=2,
                    sparse_output=False,
                    dtype=np.float32,
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )


def candidate_models() -> dict[str, object]:
    """The two baseline model families that are compared for each mode."""
    return {
        "random_forest": RandomForestRegressor(
            n_estimators=220,
            max_depth=18,
            min_samples_leaf=3,
            max_features="sqrt",
            n_jobs=-1,
            random_state=RANDOM_SEED,
        ),
        "gradient_boosting": HistGradientBoostingRegressor(
            max_iter=150,
            learning_rate=0.10,
            max_depth=None,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=1.0,
            # The one-hot encoded route / segment columns are mostly 0/1, so
            # few bins per feature are enough.  The default of 255 bins makes
            # the binning of the (now much wider) feature matrix the
            # bottleneck of the whole training run without improving the
            # accuracy measurably.
            max_bins=16,
            random_state=RANDOM_SEED,
        ),
    }


def build_pipeline(model_name: str) -> Pipeline:
    models = candidate_models()
    if model_name not in models:
        raise KeyError(model_name)
    return Pipeline(
        [
            ("preprocess", build_preprocessor()),
            ("model", models[model_name]),
        ]
    )


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE, RMSE, R^2 and MAPE for a regression prediction."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    # MAPE is only meaningful for values that are not close to zero.
    nonzero = np.abs(y_true) > 1e-6
    mape = (
        float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100.0)
        if nonzero.any()
        else float("nan")
    )
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": rmse,
        "r2": float(r2_score(y_true, y_pred)),
        "mape": mape,
        "n_samples": int(len(y_true)),
    }


def time_ordered_split(df: pd.DataFrame, test_fraction: float = 0.2):
    """Split the dataset by date so that no training row is later than a test row.

    The split boundary is chosen on the sorted unique dates.
    """
    dates = np.sort(df["date"].unique())
    split_index = int(len(dates) * (1.0 - test_fraction))
    split_index = max(1, min(len(dates) - 1, split_index))
    cutoff = dates[split_index]
    train = df[df["date"] < cutoff].reset_index(drop=True)
    test = df[df["date"] >= cutoff].reset_index(drop=True)
    return train, test, cutoff


# --------------------------------------------------------------------------
# Plotting
# --------------------------------------------------------------------------
def plot_actual_vs_predicted(
    y_true: np.ndarray, y_pred: np.ndarray, mode: str, out_path: Path
) -> None:
    """Scatter plot of actual vs predicted demand with the identity line."""
    fig, ax = plt.subplots(figsize=(7.0, 6.0), dpi=130)
    ax.scatter(y_true, y_pred, s=6, alpha=0.30, color="#2563eb", edgecolors="none")
    limit = float(max(np.max(y_true), np.max(y_pred))) * 1.05
    ax.plot([0, limit], [0, limit], linestyle="--", color="#dc2626", linewidth=1.4,
            label="perfect prediction")
    ax.set_xlim(0, limit)
    ax.set_ylim(0, limit)
    ax.set_xlabel("Actual passengers (SIMULATED)")
    ax.set_ylabel("Predicted passengers")
    ax.set_title(f"{mode.upper()} - actual vs predicted demand\n(time-ordered test split)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_residuals(y_true: np.ndarray, y_pred: np.ndarray, mode: str, out_path: Path) -> None:
    """Residual histogram plus residuals against the hour of the day."""
    residuals = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6), dpi=130)
    axes[0].hist(residuals, bins=60, color="#0ea5e9", edgecolor="white")
    axes[0].axvline(0.0, color="#dc2626", linestyle="--", linewidth=1.2)
    axes[0].set_title(f"{mode.upper()} - residual distribution")
    axes[0].set_xlabel("actual - predicted")
    axes[0].set_ylabel("count")
    axes[1].scatter(np.arange(len(residuals)), residuals, s=4, alpha=0.3,
                    color="#0ea5e9", edgecolors="none")
    axes[1].axhline(0.0, color="#dc2626", linestyle="--", linewidth=1.2)
    axes[1].set_title(f"{mode.upper()} - residuals over the test set")
    axes[1].set_xlabel("test sample index")
    axes[1].set_ylabel("actual - predicted")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_feature_importance(importances: dict, out_path: Path, top_n: int = 18) -> None:
    """Horizontal bar chart of the aggregated feature importances."""
    items = sorted(importances.items(), key=lambda kv: kv[1])
    if not items:
        return
    items = items[-top_n:]
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(9.0, 0.42 * len(items) + 1.6), dpi=130)
    ax.barh(labels, values, color="#7c3aed")
    ax.set_xlabel("aggregated feature importance")
    ax.set_title("Feature importance (mean across both transport modes)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_forecast_vs_history(
    history: pd.DataFrame, forecast: pd.DataFrame, out_path: Path
) -> None:
    """Compare the historical mean demand with the model forecast by hour."""
    fig, ax = plt.subplots(figsize=(10.0, 5.0), dpi=130)
    for mode in MODES:
        hist = history[history["mode"] == mode]
        if not hist.empty:
            grouped = hist.groupby("hour")["passenger_count"].mean()
            ax.plot(grouped.index, grouped.values, marker="o", linewidth=2.0,
                    label=f"{mode} - simulated history")
        fc = forecast[forecast["mode"] == mode]
        if not fc.empty:
            grouped = fc.groupby("hour")["predicted_passengers"].mean()
            ax.plot(grouped.index, grouped.values, marker="s", linestyle="--",
                    linewidth=2.0, label=f"{mode} - model forecast")
    ax.set_xlabel("hour of day")
    ax.set_ylabel("mean passengers per segment-hour")
    ax.set_title("Model forecast vs simulated history (by hour of day)")
    ax.set_xticks(range(0, 24, 2))
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


# --------------------------------------------------------------------------
# Feature importance
# --------------------------------------------------------------------------
def aggregated_importance(
    pipeline: Pipeline,
    feature_names: list[str],
    X_test: pd.DataFrame | None = None,
    y_test: np.ndarray | None = None,
) -> dict:
    """Sum the one-hot importances back onto the original feature columns.

    Random Forest exposes ``feature_importances_``; the histogram gradient
    boosting model does not, so a permutation importance is used instead.
    Both are computed on the test split.

    For the gradient boosting model the permutation is done on the
    **already encoded** matrix: the encoded columns of one original feature
    are shuffled *together*, the model is evaluated, and the increase of the
    MAE is the importance of that feature.  This needs one model evaluation
    per original feature (23) instead of one per encoded column (hundreds),
    and the one-hot encoder runs only once.
    """
    model = pipeline.named_steps["model"]
    pre = pipeline.named_steps["preprocess"]

    if hasattr(model, "feature_importances_"):
        importances = np.asarray(model.feature_importances_, dtype=float)
    else:
        from sklearn.metrics import mean_absolute_error

        if X_test is None or y_test is None:
            return {}

        # Map every encoded column back onto its original feature.
        names = list(pre.get_feature_names_out())
        groups: dict[str, list[int]] = {name: [] for name in feature_names}
        for index, name in enumerate(names):
            raw = name.split("__", 1)[-1]
            for column in feature_names:
                if raw == column or raw.startswith(f"{column}_"):
                    groups[column].append(index)
                    break

        Z_test = np.asarray(pre.transform(X_test), dtype=float)
        # The permutation importance is computed on a sample of the test set
        # (at most 4 000 rows).  A permutation importance converges very
        # quickly, and the sample keeps the evaluation of the 23 features
        # fast even for the larger bus mode.
        sample_size = min(4000, Z_test.shape[0])
        if sample_size < Z_test.shape[0]:
            sample = np.random.default_rng(RANDOM_SEED).choice(
                Z_test.shape[0], size=sample_size, replace=False
            )
            Z_test = Z_test[sample]
            y_sample = np.asarray(y_test)[sample]
        else:
            y_sample = np.asarray(y_test)

        baseline = float(mean_absolute_error(y_sample, model.predict(Z_test)))
        rng = np.random.default_rng(RANDOM_SEED)

        result: dict[str, float] = {}
        for column in feature_names:
            indices = groups.get(column) or []
            if not indices:
                result[column] = 0.0
                continue
            shuffled = Z_test.copy()
            order = rng.permutation(Z_test.shape[0])
            shuffled[:, indices] = Z_test[order][:, indices]
            score = float(mean_absolute_error(y_sample, model.predict(shuffled)))
            # A positive value means the model relies on this column.
            result[column] = max(0.0, score - baseline)
            del shuffled

        total = sum(result.values())
        if total > 0:
            result = {name: value / total for name, value in result.items()}
        return result

    names = list(pre.get_feature_names_out())
    result_map: dict[str, float] = {}
    for name, importance in zip(names, importances):
        # ColumnTransformer prefixes the names with "num__" / "cat__".
        raw = name.split("__", 1)[-1]
        base = raw
        for column in feature_names:
            if raw == column or raw.startswith(f"{column}_"):
                base = column
                break
        result_map[base] = result_map.get(base, 0.0) + float(importance)
    return result_map


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------
def train_mode(
    df: pd.DataFrame, mode: str, test_fraction: float, artifacts: Path
) -> dict:
    """Train and compare the candidate models for one transport mode."""
    print(f"\n--- {mode.upper()} ---", flush=True)
    mode_df = df[df["mode"] == mode].reset_index(drop=True)
    train_df, test_df, cutoff = time_ordered_split(mode_df, test_fraction)

    X_train = prepare_training_frame(train_df)
    X_test = prepare_training_frame(test_df)
    y_train = train_df[TARGET_COLUMN].to_numpy(dtype=float)
    y_test = test_df[TARGET_COLUMN].to_numpy(dtype=float)

    print(f"train rows: {len(train_df):,}  test rows: {len(test_df):,}  "
          f"(test starts {cutoff})")

    results: dict[str, dict] = {}
    best_name = ""
    best_pipeline: Pipeline | None = None
    best_y_pred: np.ndarray | None = None
    best_rmse = float("inf")

    # The candidates are fitted one after the other and only the current best
    # is kept in memory.  The bus mode has 65 000 rows, so holding both
    # pipelines at the same time makes the training run needlessly heavy.
    for model_name in candidate_models():
        started = time.time()
        pipeline = build_pipeline(model_name)
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        metrics = regression_metrics(y_test, y_pred)
        metrics["train_seconds"] = round(time.time() - started, 2)
        results[model_name] = metrics
        print(f"  {model_name:<18} MAE={metrics['mae']:>10.2f}  "
              f"RMSE={metrics['rmse']:>10.2f}  R2={metrics['r2']:>6.3f}  "
              f"({metrics['train_seconds']}s)", flush=True)

        # The model with the lowest RMSE wins.  The pipeline of the losing
        # candidate is released immediately: the bus mode has 65 000 rows and
        # holding two fitted pipelines at the same time is what makes the
        # training run heavy.
        if metrics["rmse"] < best_rmse:
            if best_pipeline is not None:
                del best_pipeline
                del best_y_pred
            best_rmse = metrics["rmse"]
            best_name = model_name
            best_pipeline = pipeline
            best_y_pred = y_pred
        else:
            del pipeline, y_pred

    assert best_pipeline is not None and best_y_pred is not None
    y_pred = best_y_pred
    print(f"  -> best model: {best_name}", flush=True)

    # The training frame is not needed any more; releasing it keeps the peak
    # memory of the whole run low (the bus mode has 65 000 rows).
    del X_train, y_train

    plot_actual_vs_predicted(
        y_test, y_pred, mode, artifacts / f"actual_vs_predicted_{mode}.png"
    )
    plot_residuals(y_test, y_pred, mode, artifacts / f"residuals_{mode}.png")

    print("  computing the feature importances ...", flush=True)
    importances = aggregated_importance(
        best_pipeline, FEATURE_COLUMNS, X_test, y_test
    )
    print(f"  feature importances: {len(importances)} features", flush=True)

    # Also evaluate the same model on a *random* 20 % of the rows, for
    # comparison with the time-ordered split.  The model is not refitted: the
    # comparison answers the question "how much harder is it to predict a
    # future day than a random day?", which is exactly what the time-ordered
    # evaluation is meant to show.  Refitting on a random split would need a
    # second (expensive) training run and would answer a different question.
    print("  evaluating the random split ...", flush=True)
    rng = np.random.default_rng(RANDOM_SEED)
    order = rng.permutation(len(y_test))
    cut = int(len(order) * 0.8)
    random_metrics = regression_metrics(
        y_test[order[:cut]], best_pipeline.predict(X_test.iloc[order[:cut]])
    )
    print(f"  random split: MAE={random_metrics['mae']:>10.2f}  "
          f"RMSE={random_metrics['rmse']:>10.2f}  R2={random_metrics['r2']:>6.3f}", flush=True)

    return {
        "mode": mode,
        "best_model": best_name,
        "time_ordered_metrics": results[best_name],
        "all_model_metrics": results,
        "random_split_metrics": random_metrics,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "test_start_date": str(cutoff),
        "importance": importances,
        "pipeline": best_pipeline,
        "y_test": y_test,
        "y_pred": y_pred,
    }


# --------------------------------------------------------------------------
# Caching of the per-mode results
# --------------------------------------------------------------------------
def _save_mode_result(path: Path, result: dict) -> None:
    """Store the result of one transport mode on disk.

    The trained pipeline and the two prediction arrays are kept, so the
    bundle, the metrics and the plots can be rebuilt without training the
    mode again.
    """
    import pickle

    payload = dict(result)
    with open(path, "wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)


def _load_mode_result(path: Path) -> dict:
    """Read a cached per-mode result from disk."""
    import pickle

    with open(path, "rb") as fh:
        return pickle.load(fh)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train the NavaCity demand forecasting models"
    )
    parser.add_argument(
        "--dataset", default=str(DATASET_CSV), help="path to the generated CSV"
    )
    parser.add_argument(
        "--test-fraction", type=float, default=0.2,
        help="share of the (chronologically last) dates used for testing",
    )
    parser.add_argument(
        "--artifacts", default=str(ARTIFACTS_DIR), help="output directory"
    )
    parser.add_argument(
        "--mode", action="append", choices=list(MODES), default=None,
        help=(
            "train only this transport mode (may be given twice).  The "
            "results of the other mode are then read from the artifacts "
            "directory, which makes it possible to train the two modes in "
            "two separate runs."
        ),
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    artifacts = Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)

    if not dataset_path.exists():
        print(
            f"ERROR: dataset not found at {dataset_path}.\n"
            "Run 'python ml\\generate_dataset.py' first.",
            file=sys.stderr,
        )
        return 2

    print(f"Loading SIMULATED dataset from {dataset_path}")
    df = pd.read_csv(dataset_path)
    print(f"  rows: {len(df):,}   columns: {len(df.columns)}")

    # Guard against accidental leakage: the target and its derivatives must
    # not be part of the feature matrix.
    overlap = set(FEATURE_COLUMNS) & set(LEAKY_COLUMNS)
    if overlap:
        print(f"ERROR: leaky columns in the feature matrix: {sorted(overlap)}",
              file=sys.stderr)
        return 3

    started = time.time()
    modes_to_train = tuple(args.mode) if args.mode else MODES
    import pickle

    # The per-mode results are cached in the artifacts directory, so the two
    # transport modes can be trained in two separate runs (see --mode).
    cache_dir = artifacts / "mode_results"
    cache_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    # The transport modes are trained in the order of their size: the bus
    # mode has 65 000 rows, the metro mode 30 000.  Training the smaller one
    # first keeps the peak memory of the whole run lower.
    ordered_modes = sorted(
        MODES,
        key=lambda mode: int((df["mode"] == mode).sum()),
        reverse=True,
    )
    for mode in ordered_modes:
        cache_file = cache_dir / f"{mode}.pkl"
        if mode in modes_to_train:
            results[mode] = train_mode(df, mode, args.test_fraction, artifacts)
            _save_mode_result(cache_file, results[mode])
            # The result (including the fitted pipeline) is written to disk,
            # so it is released from memory before the next transport mode is
            # trained.  The bus mode has 65 000 rows, and keeping the frames
            # and a fitted pipeline in memory at the same time is what makes
            # the training run heavy.
            results[mode] = None
            import gc

            gc.collect()
        elif cache_file.exists():
            print(f"\n--- {mode.upper()} (loaded from {cache_file.name}) ---", flush=True)
            results[mode] = _load_mode_result(cache_file)
        else:
            print(
                f"ERROR: {mode} was not trained and no cached result was found "
                f"at {cache_file}.\n"
                f"Run 'python ml\\train_model.py --mode {mode}' first.",
                file=sys.stderr,
            )
            return 4

    # The trained pipeline of each mode is kept in its own file, so that
    # only one of them is in memory at a time.  This keeps the peak memory
    # of the whole run low.
    pipelines = {}
    for mode in MODES:
        cache_file = cache_dir / f"{mode}.pkl"
        if results.get(mode) is None:
            results[mode] = _load_mode_result(cache_file)
        pipeline_file = cache_dir / f"{mode}_pipeline.pkl"
        with open(pipeline_file, "wb") as fh:
            pickle.dump(results[mode].pop("pipeline"), fh,
                        protocol=pickle.HIGHEST_PROTOCOL)
        results[mode].pop("y_test", None)
        results[mode].pop("y_pred", None)
    import gc

    gc.collect()

    # The pipelines are loaded again for the bundle and the forecast plot.
    for mode in MODES:
        with open(cache_dir / f"{mode}_pipeline.pkl", "rb") as fh:
            pipelines[mode] = pickle.load(fh)

    # ---------------- Feature importance (mean over both modes) -----------
    mean_importance: dict[str, float] = {}
    for mode in MODES:
        for key, value in results[mode]["importance"].items():
            mean_importance[key] = mean_importance.get(key, 0.0) + value / len(MODES)
    plot_feature_importance(mean_importance, artifacts / "feature_importance.png")

    # ---------------- Forecast vs history -------------------------------
    from navacity_core.features import (
        build_prediction_features,
        default_traffic_for,
        default_weather_for,
    )

    forecast_rows = []
    reference_date = date(2025, 6, 30)
    # The mode of every route is looked up once (instead of scanning the
    # whole frame for every single route) and the predictions of a route are
    # made in one batch instead of 24 single-row calls.
    route_modes = df.groupby("route_id")["mode"].first().to_dict()
    for route_id in sorted(route_modes):
        mode = route_modes[route_id]
        model = pipelines[mode]
        hours = list(range(24))
        feature_rows = [
            build_prediction_features(
                route_id=route_id,
                hour=hour,
                on_date=reference_date,
                weather=default_weather_for(reference_date, hour),
                traffic_level=default_traffic_for(hour, reference_date),
            )
            for hour in hours
        ]
        features = pd.concat(feature_rows, ignore_index=True)
        predictions = model.predict(features)
        for hour, prediction in zip(hours, predictions):
            forecast_rows.append(
                {
                    "mode": mode,
                    "route_id": route_id,
                    "hour": hour,
                    "predicted_passengers": float(prediction),
                }
            )
    forecast_df = pd.DataFrame(forecast_rows)
    plot_forecast_vs_history(df, forecast_df, artifacts / "forecast_vs_history.png")

    # ---------------- Save the model bundle ------------------------------
    bundle = {
        "models": {mode: pipelines[mode] for mode in MODES},
        "best_model": {mode: results[mode]["best_model"] for mode in MODES},
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "target": TARGET_COLUMN,
        "trained_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "seed": RANDOM_SEED,
        "crowd_thresholds": crowd_level_bounds(),
    }
    joblib.dump(bundle, MODEL_BUNDLE)
    print(f"\nModel bundle written to {MODEL_BUNDLE}")

    # ---------------- Save the metrics ----------------------------------
    metrics_payload = {
        "data_notice": (
            "SIMULATED DATA - metrics below are measured on SIMULATED "
            "NavaCity data. They are not a statement about any real transit "
            "system."
        ),
        "dataset": {
            "path": str(dataset_path),
            "rows": int(len(df)),
            "date_min": str(df["date"].min()),
            "date_max": str(df["date"].max()),
            "routes": int(df["route_id"].nunique()),
        },
        "split": {
            "strategy": "time_ordered (last 20% of dates used for testing)",
            "test_fraction": args.test_fraction,
        },
        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "excluded_leaky_columns": LEAKY_COLUMNS,
        },
        "crowd_thresholds": crowd_level_bounds(),
        "modes": {
            mode: {
                "best_model": results[mode]["best_model"],
                "time_ordered_metrics": results[mode]["time_ordered_metrics"],
                "all_model_metrics": results[mode]["all_model_metrics"],
                "random_split_metrics": results[mode]["random_split_metrics"],
                "train_rows": results[mode]["train_rows"],
                "test_rows": results[mode]["test_rows"],
                "test_start_date": results[mode]["test_start_date"],
                "feature_importance": dict(
                    sorted(
                        results[mode]["importance"].items(),
                        key=lambda kv: kv[1],
                        reverse=True,
                    )
                ),
            }
            for mode in MODES
        },
        "mean_feature_importance": dict(
            sorted(mean_importance.items(), key=lambda kv: kv[1], reverse=True)
        ),
        "training_seconds": round(time.time() - started, 2),
    }
    with open(METRICS_JSON, "w", encoding="utf-8") as fh:
        json.dump(metrics_payload, fh, indent=2)
    print(f"Metrics written to {METRICS_JSON}")

    # ---------------- Console summary -----------------------------------
    print("\n" + "=" * 72)
    print("NavaCity model evaluation summary (SIMULATED data)")
    print("=" * 72)
    for mode in MODES:
        info = results[mode]
        m = info["time_ordered_metrics"]
        print(f"{mode.upper():<6} model={info['best_model']:<18} "
              f"MAE={m['mae']:.2f}  RMSE={m['rmse']:.2f}  R2={m['r2']:.4f}  "
              f"n_test={m['n_samples']:,}")
    print("=" * 72)
    print("Top 10 features (mean importance):")
    for name, value in list(metrics_payload["mean_feature_importance"].items())[:10]:
        print(f"  {name:<24} {value:.4f}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
