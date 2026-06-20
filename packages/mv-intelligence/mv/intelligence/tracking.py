"""MLflow experiment tracking (PRD §9 observability) — local SQLite store, opt-in.

Logs runs (params + metrics + tags) for the validation gate, governed weight
proposals, and forecaster training. **Opt-in and a no-op by default:** with no
``MLFLOW_TRACKING_URI`` (and no explicit ``tracking_uri``) :func:`log_experiment`
returns ``None`` and touches nothing, so existing gates are unchanged when
tracking is off. When on, it uses a local file store — no server needed. The
``mlflow`` import is lazy so importing this module stays cheap.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def tracking_uri(explicit: str | None = None) -> str | None:
    """The active tracking URI: ``explicit`` > ``MLFLOW_TRACKING_URI`` > off (None)."""
    return explicit or os.environ.get("MLFLOW_TRACKING_URI")


def _store_uri(active: str) -> str:
    """Normalize a bare local path to a local **SQLite** tracking store.

    MLflow 3.x put the file store in maintenance mode; SQLite is the supported
    local backend (no server). A value already carrying a scheme is used as-is.
    """
    if "://" in active:
        return active
    db = (Path(active).absolute() / "mlflow.db").as_posix()
    return f"sqlite:///{db}"


def log_experiment(
    experiment: str,
    *,
    params: Mapping[str, object],
    metrics: Mapping[str, float],
    tags: Mapping[str, str] | None = None,
    uri: str | None = None,
) -> str | None:
    """Log one run to MLflow; return its ``run_id``, or ``None`` when disabled.

    Disabled (returns ``None``, no I/O) unless a tracking URI is configured (the
    ``uri`` arg or ``MLFLOW_TRACKING_URI``) — keeping the per-push gate
    deterministic and side-effect-free by default.
    """
    active = tracking_uri(uri)
    if active is None:
        return None

    import mlflow

    # Tracking-only path (no set_experiment) so the file store never trips the
    # model-registry URI resolver — the model registry has no file backend.
    mlflow.set_tracking_uri(_store_uri(active))
    existing = mlflow.get_experiment_by_name(experiment)
    experiment_id = existing.experiment_id if existing else mlflow.create_experiment(experiment)
    with mlflow.start_run(experiment_id=experiment_id) as run:
        mlflow.log_params(dict(params))
        mlflow.log_metrics(dict(metrics))
        if tags:
            mlflow.set_tags(dict(tags))
        run_id: str = run.info.run_id
    return run_id


__all__ = ["log_experiment", "tracking_uri"]
