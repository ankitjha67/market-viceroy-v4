"""Tests for MLflow tracking (opt-in; local file store)."""

from __future__ import annotations

from pathlib import Path

from mv.intelligence.tracking import log_experiment, tracking_uri


def test_disabled_by_default_is_a_noop(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    assert tracking_uri() is None
    assert log_experiment("gate", params={"slug": "ema"}, metrics={"sharpe": 1.2}) is None


def test_logs_a_run_to_a_local_file_store(tmp_path: Path) -> None:
    uri = str(tmp_path / "mlruns")  # a local path is the mlflow file store
    run_id = log_experiment(
        "validation_gate",
        params={"slug": "ema_cross", "n_trials": 31},
        metrics={"oos_sharpe": 1.4, "max_drawdown": 0.08},
        tags={"phase": "9B"},
        uri=uri,
    )
    assert run_id is not None
    # The run is queryable from the same local store.
    import mlflow

    run = mlflow.get_run(run_id)
    assert run.data.params["slug"] == "ema_cross"
    assert run.data.metrics["oos_sharpe"] == 1.4
    assert run.data.tags["phase"] == "9B"
