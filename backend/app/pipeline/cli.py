"""Typer CLI entry point for the K-Bar AI data pipeline."""

import io
import logging
import sys
from datetime import date

import typer

# Fix Windows cp932 encoding for Japanese output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

app = typer.Typer(help="K-Bar AI data pipeline CLI")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


@app.command()
def ingest(
    source: str = typer.Option("kaggle", help="Data source (kaggle)"),
    csv_path: str | None = typer.Option(None, help="CSV file path (auto-detect from data/ if omitted)"),
):
    """Ingest race data from CSV into database."""
    if source != "kaggle":
        typer.echo(f"Unknown source: {source}", err=True)
        raise typer.Exit(code=1)

    from app.pipeline.ingest import run_ingest

    run_ingest(csv_path=csv_path)


@app.command()
def train(
    version: str = typer.Option(..., help="Model version (e.g. v1.0.0)"),
    cutoff: int = typer.Option(2020, help="Train/test cutoff year"),
    description: str | None = typer.Option(None, help="Model description"),
):
    """Train a LightGBM prediction model."""
    _setup_logging()

    from app.ml.trainer import train_model

    typer.echo(f"Training model {version} (cutoff={cutoff})...")
    metrics = train_model(version=version, cutoff_year=cutoff, description=description)

    typer.echo("\n=== Training Complete ===")
    typer.echo(f"  Accuracy:  {metrics['accuracy']:.4f}")
    typer.echo(f"  F1 Score:  {metrics['f1']:.4f}")
    typer.echo(f"  ROC AUC:   {metrics['roc_auc']:.4f}")
    typer.echo(f"  Test rows: {metrics['test_rows']}")
    typer.echo(f"  Best iter: {metrics['best_iteration']}")


@app.command()
def predict(
    version: str = typer.Option("v1.0.0", help="Model version to use"),
    race_id: str | None = typer.Option(None, help="Specific race_id to predict"),
    date_str: str | None = typer.Option(None, "--date", help="Date to predict (YYYY-MM-DD)"),
    no_save: bool = typer.Option(False, help="Do not save predictions to DB"),
):
    """Generate predictions for a race or date."""
    _setup_logging()

    if not race_id and not date_str:
        typer.echo("Specify --race-id or --date", err=True)
        raise typer.Exit(code=1)

    from app.ml.predictor import predict_race

    target_date = date.fromisoformat(date_str) if date_str else None

    results = predict_race(
        version=version,
        race_id_str=race_id,
        target_date=target_date,
        save_to_db=not no_save,
    )

    if not results:
        typer.echo("No results found.")
        raise typer.Exit(code=0)

    # Display grouped by race
    current_race = None
    for r in results:
        if r["race_id_str"] != current_race:
            current_race = r["race_id_str"]
            typer.echo(f"\n{'='*60}")
            typer.echo(f"Race: {current_race} ({r['racecourse_name']} {r['race_date'].strftime('%Y-%m-%d') if hasattr(r['race_date'], 'strftime') else r['race_date']})")
            typer.echo(f"{'='*60}")
            typer.echo(f"{'予想順':>6} {'馬名':<16} {'スコア':>8} {'信頼度':<8} {'実着順':>6}")
            typer.echo("-" * 60)

        actual = r.get("actual_finish", "?")
        typer.echo(
            f"{r['predicted_position']:>6} {r['horse_name']:<16} "
            f"{r['score']:>8.3f} {r['confidence']:<8} {str(actual):>6}"
        )
        typer.echo(f"       {r['explanation']}")

    typer.echo(f"\nTotal: {len(results)} predictions across {len(set(r['race_id_str'] for r in results))} races")


@app.command()
def verify(
    version: str = typer.Option("v1.0.0", "--model-version", help="Model version to verify"),
):
    """Verify predictions against actual race results."""
    _setup_logging()

    from app.ml.verifier import verify_predictions

    summary = verify_predictions(version)

    if summary.get("total_predictions", 0) == 0:
        typer.echo(f"No predictions found for version '{version}'")
        raise typer.Exit(code=0)

    typer.echo(f"\n=== Verification: {version} ===")
    typer.echo(f"  Races:          {summary['unique_races']}")
    typer.echo(f"  Predictions:    {summary['total_predictions']}")
    typer.echo(f"  Win hit rate:   {summary['win_hit_rate']:.1%} ({summary['win_hits']}/{summary['win_attempts']})")
    typer.echo(f"  Place hit rate: {summary['place_hit_rate']:.1%} ({summary['place_hits']}/{summary['place_attempts']})")


@app.command()
def evaluate(
    version: str = typer.Option("v1.0.0", "--model-version", help="Model version to evaluate"),
):
    """Show comprehensive model evaluation report."""
    _setup_logging()

    from app.ml.evaluator import evaluate_model

    report = evaluate_model(version)
    typer.echo(report)


if __name__ == "__main__":
    app()
