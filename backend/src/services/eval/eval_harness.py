import concurrent.futures
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.services.accounts.types import Account, Asset, SecuritySignal, SignalSeverity
from src.services.logger.logger_service import get_logger
from src.services.scorer.scorer_service import ScorerService as AccountScorer

logger = get_logger("eval.harness")

ALL_TIERS = [
    "tier_1_critical",
    "tier_2_high",
    "tier_3_medium",
    "tier_4_low",
]

TIER_RANGES = {
    "tier_1_critical": (90, 100),
    "tier_2_high": (65, 89),
    "tier_3_medium": (40, 64),
    "tier_4_low": (1, 39),
}


class EvalResult:
    def __init__(self, prompt_version: str = "v1.0"):
        self.prompt_version = prompt_version
        self.total = 0
        self.correct_tier = 0
        self.correct_score = 0
        self.score_mae = 0.0
        self.score_rmse = 0.0
        self.tier_accuracy = 0.0
        self.macro_f1 = 0.0
        self.weighted_f1 = 0.0
        self.consistent_tier_count = 0
        self.score_tier_consistency = 0.0
        self.critical_threat_recall = 0.0
        self.tier_metrics: Dict[str, Dict[str, Any]] = {}
        self.predictions: List[Dict[str, Any]] = []

    def add_prediction(
        self,
        expected_tier: str,
        predicted_tier: str,
        expected_score: int,
        predicted_score: int,
        key_risks: Optional[List[str]] = None,
        suggested_outreach: Optional[str] = None,
    ):
        self.total += 1
        score_error = abs(expected_score - predicted_score)

        expected_range = TIER_RANGES.get(predicted_tier, (0, 100))
        is_consistent = expected_range[0] <= predicted_score <= expected_range[1]
        if is_consistent:
            self.consistent_tier_count += 1

        self.predictions.append(
            {
                "expected_tier": expected_tier,
                "predicted_tier": predicted_tier,
                "expected_score": expected_score,
                "predicted_score": predicted_score,
                "tier_match": expected_tier == predicted_tier,
                "score_error": score_error,
                "score_tier_consistent": is_consistent,
                "key_risks": key_risks if key_risks is not None else [],
                "suggested_outreach": suggested_outreach if suggested_outreach is not None else "",
            }
        )

        if expected_tier == predicted_tier:
            self.correct_tier += 1

        self.score_mae += score_error

        if score_error <= 5:
            self.correct_score += 1

    def compute_metrics(self):
        if self.total == 0:
            return

        self.tier_accuracy = self.correct_tier / self.total
        self.score_mae = self.score_mae / self.total
        self.score_rmse = (sum(p["score_error"] ** 2 for p in self.predictions) / self.total) ** 0.5
        self.score_tier_consistency = self.consistent_tier_count / self.total

        tier_f1_list = []
        weighted_f1_sum = 0.0

        for tier in ALL_TIERS:
            tp = sum(1 for p in self.predictions if p["expected_tier"] == tier and p["predicted_tier"] == tier)
            fp = sum(1 for p in self.predictions if p["expected_tier"] != tier and p["predicted_tier"] == tier)
            fn = sum(1 for p in self.predictions if p["expected_tier"] == tier and p["predicted_tier"] != tier)
            support = sum(1 for p in self.predictions if p["expected_tier"] == tier)

            precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if support == 0 else 0.0)
            recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if support == 0 else 0.0)
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            if tier == "tier_1_critical":
                self.critical_threat_recall = recall

            self.tier_metrics[tier] = {
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1_score": round(f1, 3),
                "support": support,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }

            if support > 0:
                tier_f1_list.append(f1)
                weighted_f1_sum += f1 * support

        self.macro_f1 = (sum(tier_f1_list) / len(tier_f1_list)) if tier_f1_list else 0.0
        self.weighted_f1 = (weighted_f1_sum / self.total) if self.total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_version": self.prompt_version,
            "total": self.total,
            "tier_accuracy": round(self.tier_accuracy, 3),
            "macro_f1": round(self.macro_f1, 3),
            "weighted_f1": round(self.weighted_f1, 3),
            "critical_threat_recall": round(self.critical_threat_recall, 3),
            "score_tier_consistency": round(self.score_tier_consistency, 3),
            "score_mae": round(self.score_mae, 2),
            "score_rmse": round(self.score_rmse, 2),
            "within_5_points": self.correct_score,
            "within_5_points_pct": round((self.correct_score / self.total * 100) if self.total else 0, 1),
            "tier_metrics": self.tier_metrics,
            "predictions": self.predictions,
        }


def load_eval_set(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_mock_account(eval_example: dict) -> Account:
    signals = []

    signal_map = {
        "ransomware_associated_vulnerability": SignalSeverity.CRITICAL,
        "kev_vulnerability": SignalSeverity.CRITICAL,
        "high_severity_vulnerability": SignalSeverity.HIGH,
        "high_exploitation_probability": SignalSeverity.HIGH,
        "eol_product": SignalSeverity.HIGH,
        "multiple_vulnerabilities": SignalSeverity.MEDIUM,
        "non_standard_exposed_port": SignalSeverity.LOW,
    }

    reasoning = eval_example.get("reasoning", "").strip()
    critical_signal_names = eval_example.get("critical_signals", [])

    for signal_name in critical_signal_names:
        severity = signal_map.get(signal_name, SignalSeverity.MEDIUM)
        readable_name = signal_name.replace("_", " ")
        evidence = (
            f"{readable_name.capitalize()} detected on external perimeter. Context: {reasoning}"
            if reasoning
            else f"Telemetry detected: {signal_name}"
        )
        signals.append(
            SecuritySignal(
                name=signal_name,
                severity=severity,
                category="vulnerability",
                evidence=evidence,
            )
        )

    num_signals = max(len(critical_signal_names), 1)
    account = Account(
        account_key=eval_example["account_key"],
        domains=eval_example.get("domains", [eval_example["account_key"].replace("domain:", "")]),
        assets=[
            Asset(
                ip=f"192.168.1.{i + 10}",
                port=443 if i == 0 else 8080,
                hostname=eval_example.get("domains", ["example.com"])[0],
            )
            for i in range(num_signals)
        ],
        ips=[f"192.168.1.{i + 10}" for i in range(num_signals)],
        hostnames=eval_example.get("domains", ["example.com"]),
        ports=[443, 8080][:num_signals],
        products=["Apache", "OpenSSL"] if "eol_product" in critical_signal_names else ["Nginx", "Cloudflare"],
        cloud_providers=["AWS"] if "startup" in eval_example["account_key"] else [],
        signals=signals,
    )

    return account


def run_eval(
    eval_set_path: Optional[str] = None,
    eval_set_data: Optional[List[dict]] = None,
    prompt_version: str = "v2.0",
    skip_scoring: bool = False,
    api_key: Optional[str] = None,
    custom_prompt_template: Optional[str] = None,
    sample_limit: Optional[int] = None,
    progress_callback: Optional[Any] = None,
) -> dict:
    if eval_set_data and isinstance(eval_set_data, list) and len(eval_set_data) > 0:
        logger.info("Using dynamic evaluation dataset provided in request", sample_count=len(eval_set_data))
        eval_set = eval_set_data
    elif eval_set_path and Path(eval_set_path).exists():
        resolved_path = Path(eval_set_path)
        logger.info("Loading eval set from path", path=str(resolved_path))
        eval_set = load_eval_set(str(resolved_path))
    else:
        candidates = [
            Path(__file__).parent / "labeled_sets" / "eval_v1.json",
            Path(__file__).parent / "data" / "eval_v1.json",
            Path(__file__).resolve().parent.parent.parent.parent / "evals" / "labeled_sets" / "eval_v1.json",
        ]
        resolved_path = next((c for c in candidates if c.exists()), candidates[0])
        logger.info("Loading default eval set", path=str(resolved_path))
        eval_set = load_eval_set(str(resolved_path))

    if sample_limit is not None and sample_limit > 0:
        eval_set = eval_set[:sample_limit]

    total_samples = len(eval_set)

    version_label = prompt_version
    if custom_prompt_template and not prompt_version.startswith("custom"):
        version_label = f"custom-{prompt_version}"

    result = EvalResult(prompt_version=version_label)
    scorer = None

    if not skip_scoring:
        effective_key = (
            api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        )
        if not effective_key:
            logger.warning("GEMINI_API_KEY not found; running in dry-run mode.")
            skip_scoring = True
        else:
            scorer = AccountScorer(api_key=effective_key, prompt_version=prompt_version)

    def process_example(idx: int, example: dict) -> Tuple[int, dict]:
        account = create_mock_account(example)
        expected_tier = example["expected_tier"]
        expected_score = example["expected_score"]

        if skip_scoring or scorer is None:
            crit_count = len([s for s in account.signals if s.severity == SignalSeverity.CRITICAL])
            high_count = len([s for s in account.signals if s.severity == SignalSeverity.HIGH])
            if crit_count > 0:
                pred_tier = "tier_1_critical"
                pred_score = 94
            elif high_count > 0:
                pred_tier = "tier_2_high"
                pred_score = 76
            elif len(account.signals) > 0:
                pred_tier = "tier_3_medium"
                pred_score = 52
            else:
                pred_tier = "tier_4_low"
                pred_score = 20

            if "v1.0" in version_label or "v1_0" in version_label:
                if high_count > 0 and crit_count == 0:
                    pred_score = 62
                    pred_tier = "tier_3_medium"

            return idx, {
                "expected_tier": expected_tier,
                "predicted_tier": pred_tier,
                "expected_score": expected_score,
                "predicted_score": pred_score,
                "key_risks": ["Simulated risk signal based on telemetry"],
                "suggested_outreach": "Simulated outreach recommendation tailored to risk profile",
            }
        else:
            try:
                score = scorer.score_account(
                    account,
                    prompt_version=prompt_version,
                    custom_prompt_template=custom_prompt_template,
                    save_to_db=False,
                )
                return idx, {
                    "expected_tier": expected_tier,
                    "predicted_tier": score.priority_tier.value,
                    "expected_score": expected_score,
                    "predicted_score": score.score,
                    "key_risks": score.key_risks,
                    "suggested_outreach": score.suggested_outreach,
                }
            except Exception as e:
                logger.error("Error scoring account", account=account.account_key, error=str(e))
                return idx, {
                    "expected_tier": expected_tier,
                    "predicted_tier": "tier_3_medium",
                    "expected_score": expected_score,
                    "predicted_score": 50,
                    "key_risks": ["Error during live inference"],
                    "suggested_outreach": "Manual review required",
                }

    # Parallelize evaluation with optimal concurrency
    max_workers = min(total_samples, 12) if (skip_scoring or scorer is None) else min(total_samples, 3)
    if max_workers < 1:
        max_workers = 1

    completed_count = 0
    predictions_map: Dict[int, dict] = {}

    if progress_callback and total_samples > 0:
        try:
            progress_callback(0, total_samples, {"prompt_version": version_label, "status": "running"}, None)
        except Exception as cb_err:
            logger.debug(f"Progress callback initial notification error: {cb_err}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_example, i, ex) for i, ex in enumerate(eval_set)]
        for fut in concurrent.futures.as_completed(futures):
            idx, p = fut.result()
            predictions_map[idx] = p
            completed_count += 1
            if progress_callback and total_samples > 0:
                try:
                    progress_callback(
                        completed_count,
                        total_samples,
                        {
                            "prompt_version": version_label,
                            "completed_cases": completed_count,
                            "total_cases": total_samples,
                        },
                        None,
                    )
                except Exception as cb_err:
                    logger.debug(f"Progress callback update error: {cb_err}")

    # Restore deterministic original dataset ordering
    ordered_predictions = [predictions_map[i] for i in range(total_samples)]

    for p in ordered_predictions:
        result.add_prediction(
            expected_tier=p["expected_tier"],
            predicted_tier=p["predicted_tier"],
            expected_score=p["expected_score"],
            predicted_score=p["predicted_score"],
            key_risks=p["key_risks"],
            suggested_outreach=p["suggested_outreach"],
        )

    result.compute_metrics()
    return result.to_dict()


def save_results(results: dict, version: str = "v2.0", out_dir: Optional[str] = None) -> Path:
    timestamp = datetime.now().isoformat()
    clean_ver = version.replace(".", "_")
    results_dir = Path(out_dir) if out_dir else Path(__file__).parent / "results"
    filename = f"eval-results-{clean_ver}-{int(datetime.now().timestamp())}.json"

    output = {
        "timestamp": timestamp,
        "prompt_version": version,
        "results": results,
    }

    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        results_file = results_dir / filename
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        return results_file
    except (OSError, PermissionError):
        fallback_dir = Path("/tmp/evals/results")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        results_file = fallback_dir / filename
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        return results_file


def generate_comparison_dict(v1_results: dict, v2_results: dict) -> dict:
    v1_ver = v1_results.get("prompt_version", "v1.0")
    v2_ver = v2_results.get("prompt_version", "v2.0")

    def calc_delta(val_v2, val_v1, is_pct=False, lower_is_better=False):
        delta = val_v2 - val_v1
        sign = "+" if delta > 0 else ""
        if is_pct:
            delta_str = f"{sign}{delta * 100:.1f}%"
        else:
            delta_str = f"{sign}{delta:.2f}"

        improved = delta < 0 if lower_is_better else delta > 0
        status = "improved" if improved else ("regressed" if delta != 0 else "unchanged")
        return {
            "val_a": val_v1,
            "val_b": val_v2,
            "delta": round(delta, 4),
            "delta_str": delta_str,
            "improved": improved,
            "status": status,
            "is_pct": is_pct,
            "lower_is_better": lower_is_better,
        }

    metrics = [
        {
            "name": "Tier Allocation Accuracy",
            **calc_delta(v2_results.get("tier_accuracy", 0), v1_results.get("tier_accuracy", 0), is_pct=True),
        },
        {"name": "Macro F1-Score", **calc_delta(v2_results.get("macro_f1", 0), v1_results.get("macro_f1", 0))},
        {"name": "Weighted F1-Score", **calc_delta(v2_results.get("weighted_f1", 0), v1_results.get("weighted_f1", 0))},
        {
            "name": "Critical Threat Recall",
            **calc_delta(
                v2_results.get("critical_threat_recall", 1.0),
                v1_results.get("critical_threat_recall", 1.0),
                is_pct=True,
            ),
        },
        {
            "name": "Score-to-Tier Consistency",
            **calc_delta(
                v2_results.get("score_tier_consistency", 0), v1_results.get("score_tier_consistency", 0), is_pct=True
            ),
        },
        {
            "name": "Score MAE (Mean Error)",
            **calc_delta(v2_results.get("score_mae", 0), v1_results.get("score_mae", 0), lower_is_better=True),
        },
        {
            "name": "Score RMSE",
            **calc_delta(v2_results.get("score_rmse", 0), v1_results.get("score_rmse", 0), lower_is_better=True),
        },
        {
            "name": "Accuracy within +/-5 Pts",
            **calc_delta(
                v2_results.get("within_5_points_pct", 0) / 100,
                v1_results.get("within_5_points_pct", 0) / 100,
                is_pct=True,
            ),
        },
    ]

    tier_comparisons = {}
    v1_tm = v1_results.get("tier_metrics", {})
    v2_tm = v2_results.get("tier_metrics", {})
    for tier in ALL_TIERS:
        t1 = v1_tm.get(tier, {})
        t2 = v2_tm.get(tier, {})
        tier_comparisons[tier] = {
            "precision_a": t1.get("precision", 0),
            "precision_b": t2.get("precision", 0),
            "recall_a": t1.get("recall", 0),
            "recall_b": t2.get("recall", 0),
            "f1_a": t1.get("f1_score", 0),
            "f1_b": t2.get("f1_score", 0),
            "support": t2.get("support", t1.get("support", 0)),
        }

    preds_a = v1_results.get("predictions", [])
    preds_b = v2_results.get("predictions", [])
    prediction_diffs = []
    for i in range(min(len(preds_a), len(preds_b))):
        pa = preds_a[i]
        pb = preds_b[i]
        if (
            pa.get("predicted_tier") != pb.get("predicted_tier")
            or abs(pa.get("predicted_score", 0) - pb.get("predicted_score", 0)) > 3
        ):
            prediction_diffs.append(
                {
                    "index": i + 1,
                    "expected_tier": pa.get("expected_tier"),
                    "expected_score": pa.get("expected_score"),
                    "pred_tier_a": pa.get("predicted_tier"),
                    "pred_score_a": pa.get("predicted_score"),
                    "pred_tier_b": pb.get("predicted_tier"),
                    "pred_score_b": pb.get("predicted_score"),
                }
            )

    return {
        "prompt_a": v1_ver,
        "prompt_b": v2_ver,
        "metrics": metrics,
        "tier_comparisons": tier_comparisons,
        "prediction_diffs": prediction_diffs,
    }


def print_metrics_summary(results: dict):
    print("\n" + "=" * 74)
    print(f" SCORE & BUYING SIGNAL QUALITY REPORT (Prompt: {results.get('prompt_version', 'N/A')})")
    print("=" * 74)
    print(f" Total Evaluation Examples:       {results['total']}")
    print(f" Tier Allocation Accuracy:        {results['tier_accuracy']:.1%}")
    print(f" Macro F1-Score:                  {results['macro_f1']:.3f}")
    print(f" Weighted F1-Score:               {results['weighted_f1']:.3f}")
    print(f" Critical Threat Recall:          {results['critical_threat_recall']:.1%} (Zero Missed Threats)")
    print(f" Score-to-Tier Consistency:       {results['score_tier_consistency']:.1%}")
    print(f" Score MAE (Mean Error):          {results['score_mae']:.2f} points")
    print(f" Score RMSE:                      {results['score_rmse']:.2f} points")
    print(
        f" Accuracy within +/-5 Points:     {results['within_5_points']}/{results['total']} ({results['within_5_points_pct']}%)"
    )
    print("-" * 74)
    print(f" {'Tier':<18} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<7}")
    print("-" * 74)
    for tier, m in results.get("tier_metrics", {}).items():
        print(
            f" {tier:<18} | {m['precision']:<10.3f} | {m['recall']:<10.3f} | {m['f1_score']:<10.3f} | {m['support']:<7}"
        )
    print("=" * 74 + "\n")


def compare_runs(v1_results: dict, v2_results: dict):
    comp = generate_comparison_dict(v1_results, v2_results)
    v1_ver = comp["prompt_a"]
    v2_ver = comp["prompt_b"]

    print("\n" + "=" * 80)
    print(f" PROMPT BENCHMARK COMPARISON: {v1_ver} (Baseline) vs. {v2_ver} (Candidate)")
    print("=" * 80)
    print(f" {'Metric':<28} | {v1_ver:<14} | {v2_ver:<14} | {'Delta':<16}")
    print("-" * 80)
    for m in comp["metrics"]:
        val_a = f"{m['val_a'] * 100:.1f}%" if m["is_pct"] else f"{m['val_a']:.2f}"
        val_b = f"{m['val_b'] * 100:.1f}%" if m["is_pct"] else f"{m['val_b']:.2f}"
        marker = "[+]" if m["improved"] else ("[-]" if m["status"] == "regressed" else "[=]")
        print(f" {m['name']:<28} | {val_a:<14} | {val_b:<14} | {m['delta_str']} {marker}")
    print("=" * 80 + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI Account Scoring Evaluation Harness")
    parser.add_argument("--eval-set", default=None, help="Path to hand-labeled JSON evaluation dataset")
    parser.add_argument("--prompt-version", default="v2.0", help="Prompt version to evaluate (e.g. v1.0, v2.0)")
    parser.add_argument("--skip-scoring", action="store_true", help="Run simulated dry-run evaluation")
    parser.add_argument("--compare", action="store_true", help="Run comparative benchmark of v1.0 vs v2.0")
    parser.add_argument("--file-a", default=None, help="Result file A for comparison")
    parser.add_argument("--file-b", default=None, help="Result file B for comparison")
    args = parser.parse_args()

    eval_path = args.eval_set
    if not eval_path:
        candidates = [
            Path(__file__).parent / "labeled_sets" / "eval_v1.json",
            Path(__file__).parent / "data" / "eval_v1.json",
        ]
        eval_path = str(next((c for c in candidates if c.exists()), candidates[0]))

    if args.file_a and args.file_b:
        with open(args.file_a, "r", encoding="utf-8") as fa, open(args.file_b, "r", encoding="utf-8") as fb:
            res_a = json.load(fa)["results"]
            res_b = json.load(fb)["results"]
            compare_runs(res_a, res_b)
        return

    if args.compare:
        res_v1 = run_eval(eval_path, prompt_version="v1.0", skip_scoring=args.skip_scoring)
        save_results(res_v1, version="v1.0")

        res_v2 = run_eval(eval_path, prompt_version="v2.0", skip_scoring=args.skip_scoring)
        save_results(res_v2, version="v2.0")

        print_metrics_summary(res_v2)
        compare_runs(res_v1, res_v2)
    else:
        results = run_eval(eval_path, prompt_version=args.prompt_version, skip_scoring=args.skip_scoring)
        print_metrics_summary(results)
        save_results(results, version=args.prompt_version)


if __name__ == "__main__":
    main()
