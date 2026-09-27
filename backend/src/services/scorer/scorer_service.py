import json
import os
import random
import re
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from google import genai
from google.genai import types

from src.core.config import (
    GEMINI_MODEL,
    PRICING,
    PROMPT_VERSION,
)
from src.services.accounts.types import Account
from src.services.database.dependencies import default_database_service
from src.services.database.database_service import DatabaseService
from src.services.logger.logger_service import get_logger
from src.services.scorer.dependencies import (
    ScorerServiceDependencyContext,
    get_scorer_dependency_context,
)
from src.services.scorer.protocols import (
    IScoreReader,
    IScorerService,
    IScoreWriter,
)
from src.services.scorer.types import (
    AccountScore,
    BatchScoreCommand,
    LLMTrace,
    PriorityTier,
    ScoreAccountCommand,
    ScoringResponse,
)

logger = get_logger("services.scorer")

MODEL = GEMINI_MODEL


class GlobalRateLimiter:
    def __init__(self, min_interval: float = 0.25):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call_time = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call_time = time.time()


_global_rate_limiter = GlobalRateLimiter(min_interval=0.05)


class ScorerService(IScorerService):
    def __init__(
        self,
        context: Optional[ScorerServiceDependencyContext] = None,
    ):
        ctx = context or get_scorer_dependency_context()
        self._reader: IScoreReader = ctx.reader
        self._writer: IScoreWriter = ctx.writer
        self.reader = self._reader
        self.writer = self._writer
        self._accounts_service = ctx.accounts_service
        self._prompt_service = ctx.prompt_service

        self.db_path = Path(ctx.db_path) if isinstance(ctx.db_path, str) else ctx.db_path
        self._local_db_service = DatabaseService(db_path=self.db_path) if self.db_path is not None else None

        self.api_key = ctx.api_key
        self.client = genai.Client(api_key=ctx.api_key) if ctx.api_key else None
        self.prompt_version = ctx.prompt_version or PROMPT_VERSION
        self.model = ctx.model or GEMINI_MODEL
        self.trace_dir = Path(ctx.trace_dir) if ctx.trace_dir is not None else None
        self.trace_file = (self.trace_dir / f"llm-traces-{int(time.time())}.jsonl") if self.trace_dir else None
        self.traces: List[LLMTrace] = []

    def _get_gemini_client(self) -> Any:
        if self.client:
            return self.client
        api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        if api_key:
            return genai.Client(api_key=api_key)
        return None

    def set_accounts_service(self, accounts_service: Any) -> None:
        self._accounts_service = accounts_service

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * PRICING["input"]
        output_cost = (output_tokens / 1_000_000) * PRICING["output"]
        return input_cost + output_cost

    def _format_signal_evidence_summary(
        self,
        critical_signals: List[Any],
        high_signals: List[Any],
        medium_signals: List[Any],
        low_signals: List[Any],
        total_signals: int,
        max_sample: int = 15,
    ) -> Tuple[str, str, str]:
        crit_sample = critical_signals[:max_sample]
        high_sample = high_signals[:max_sample]
        other_sample = (medium_signals + low_signals)[:10]

        crit_text = "\n".join(f"- {s.name}: {s.evidence}" for s in crit_sample) if crit_sample else "None"
        if len(critical_signals) > max_sample:
            crit_text += f"\n- ... and {len(critical_signals) - max_sample} more critical signals"

        high_text = "\n".join(f"- {s.name}: {s.evidence}" for s in high_sample) if high_sample else "None"
        if len(high_signals) > max_sample:
            high_text += f"\n- ... and {len(high_signals) - max_sample} more high-severity signals"

        sample_signals = crit_sample + high_sample + other_sample
        all_signals_sample_text = "\n".join(
            f"- [{getattr(s.severity, 'value', str(s.severity)).upper()}] {s.name}: {s.evidence}"
            for s in sample_signals
        )
        if total_signals > len(sample_signals):
            all_signals_sample_text += (
                f"\n- ... ({total_signals} total signals detected: "
                f"{len(critical_signals)} critical, {len(high_signals)} high, "
                f"{len(medium_signals)} medium, {len(low_signals)} low)"
            )

        return crit_text, high_text, all_signals_sample_text

    def format_account_context(self, account: Union[Account, Dict[str, Any], Any]) -> str:
        signals = getattr(account, "signals", None) if not isinstance(account, dict) else account.get("signals")
        signals = signals or []
        critical_signals = [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "critical" or (isinstance(s, dict) and s.get("severity") == "critical"))]
        high_signals = [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "high" or (isinstance(s, dict) and s.get("severity") == "high"))]
        medium_signals = [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "medium" or (isinstance(s, dict) and s.get("severity") == "medium"))]
        low_signals = [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "low" or (isinstance(s, dict) and s.get("severity") == "low"))]

        crit_text, high_text, sample_text = self._format_signal_evidence_summary(
            critical_signals, high_signals, medium_signals, low_signals, len(signals)
        )

        domains = getattr(account, "domains", None) if not isinstance(account, dict) else account.get("domains")
        domains = domains or []
        assets = getattr(account, "assets", None) if not isinstance(account, dict) else account.get("assets")
        assets = assets or []
        ips = getattr(account, "ips", None) if not isinstance(account, dict) else account.get("ips")
        ips = ips or []
        products = getattr(account, "products", None) if not isinstance(account, dict) else account.get("products")
        products = products or []
        cloud_providers = getattr(account, "cloud_providers", None) if not isinstance(account, dict) else account.get("cloud_providers")
        cloud_providers = cloud_providers or []
        account_key = getattr(account, "account_key", None) or (account.get("account_key") if isinstance(account, dict) else str(account))

        return textwrap.dedent(f"""
        Account: {account_key}
        Domains: {", ".join(domains[:20])}
        Assets discovered: {len(assets)}
        Unique IPs: {len(ips)}
        Technology stack: {", ".join(products[:30]) or "Unknown"}
        Cloud providers: {", ".join(cloud_providers) or "None detected"}

        SECURITY SIGNALS SUMMARY:
        Total Signals: {len(signals)} (Critical: {len(critical_signals)}, High: {len(high_signals)}, Medium: {len(medium_signals)}, Low: {len(low_signals)})

        Critical ({len(critical_signals)}):
        {crit_text}

        High severity ({len(high_signals)}):
        {high_text}

        Representative Signal Sample:
        {sample_text}
        """).strip()

    def get_prompt(
        self,
        account: Union[Account, Dict[str, Any], Any],
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
    ) -> str:
        context = self.format_account_context(account)

        if custom_prompt_template:
            if "{account_context}" in custom_prompt_template:
                return custom_prompt_template.replace("{account_context}", context)
            return f"{custom_prompt_template}\n\n{context}"

        if self._prompt_service:
            template = self._prompt_service.get_template(prompt_version or self.prompt_version)
        else:
            from src.services.prompts.dependencies import default_prompt_service

            version = prompt_version or self.prompt_version
            template = default_prompt_service.get_template(version)

        if "{account_context}" in template:
            return template.replace("{account_context}", context)
        return f"{template}\n\n{context}"

    def _generate_with_retry(self, client: Any, prompt: str, max_retries: int = 5) -> Any:
        for attempt in range(max_retries):
            try:
                _global_rate_limiter.acquire()
                return client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ScoringResponse,
                        max_output_tokens=2048,
                    ),
                )
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "quota"]):
                    if attempt < max_retries - 1:
                        match = re.search(r"retry in ([\d\.]+)s", err_str, re.IGNORECASE)
                        if match:
                            wait_time = float(match.group(1)) + random.uniform(0.5, 2.5)
                        else:
                            match_delay = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)s?", err_str)
                            if match_delay:
                                wait_time = float(match_delay.group(1)) + random.uniform(0.5, 2.5)
                            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                                wait_time = min(20.0, (2.0**attempt) * 2.5) + random.uniform(0.5, 2.0)
                            else:
                                wait_time = (2.0**attempt) * 1.5 + random.uniform(0.5, 1.5)

                        logger.warning(
                            f"Rate limit / transient error on attempt {attempt + 1}/{max_retries}. Waiting {wait_time:.1f}s",
                            attempt=attempt + 1,
                            wait_time_s=wait_time,
                        )
                        time.sleep(wait_time)
                        continue
                raise
        return None

    def _parse_scoring_json(self, content: str) -> Dict[str, Any]:
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = content[json_start:json_end]
            parsed_json = json.loads(json_str)
            return parsed_json if isinstance(parsed_json, dict) else {}
        except (json.JSONDecodeError, ValueError):
            logger.error("Failed to parse scoring response", response_content=content)
            return {
                "score": 50,
                "priority_tier": "tier_3_medium",
                "key_risks": ["Unable to parse AI response"],
                "suggested_outreach": "Manual review required",
            }

    def _extract_token_usage_and_cost(self, response: Any) -> Tuple[int, int, int, float]:
        usage = response.usage_metadata if response else None
        input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count else 0
        output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count else 0
        total_tokens = input_tokens + output_tokens
        cost_usd = self.calculate_cost(input_tokens, output_tokens)
        return input_tokens, output_tokens, total_tokens, cost_usd

    def _apply_score_guardrails(self, result: Dict[str, Any], account: Union[Account, Dict[str, Any], Any]) -> Tuple[int, PriorityTier, str]:
        try:
            raw_score = int(result.get("score", 50))
        except (ValueError, TypeError):
            raw_score = 50
        raw_score = max(1, min(100, raw_score))
        original_score = raw_score

        acc_key = (
            getattr(account, "account_key", None)
            or (account.get("account_key") if isinstance(account, dict) else str(account))
        )
        signals = getattr(account, "signals", None) if not isinstance(account, dict) else account.get("signals")
        signals = signals or []
        critical_signals_count = len(
            [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "critical" or (isinstance(s, dict) and s.get("severity") == "critical"))]
        )
        high_signals_count = len(
            [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "high" or (isinstance(s, dict) and s.get("severity") == "high"))]
        )
        medium_signals_count = len(
            [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "medium" or (isinstance(s, dict) and s.get("severity") == "medium"))]
        )
        low_signals_count = len(
            [s for s in signals if (getattr(s.severity, "value", getattr(s, "severity", "")) == "low" or (isinstance(s, dict) and s.get("severity") == "low"))]
        )

        if critical_signals_count == 0:
            if raw_score >= 90:
                if high_signals_count >= 2:
                    raw_score = 80
                elif high_signals_count == 1:
                    raw_score = 70
                elif medium_signals_count > 0:
                    raw_score = 55
                elif low_signals_count > 0:
                    raw_score = 35
                else:
                    raw_score = 20
                logger.warning(
                    "Clamped hallucinated score to verified signal ceiling",
                    account_key=acc_key,
                    original_score=original_score,
                    clamped_score=raw_score,
                )

        if critical_signals_count == 0 and high_signals_count == 0 and medium_signals_count == 0:
            if raw_score > 45:
                raw_score = 30 if low_signals_count > 0 else 18
                logger.warning(
                    "Clamped low-signal account score to low/medium ceiling",
                    account_key=acc_key,
                    clamped_score=raw_score,
                )

        if raw_score >= 90:
            priority_tier = PriorityTier.TIER_1_CRITICAL
        elif raw_score >= 65:
            priority_tier = PriorityTier.TIER_2_HIGH
        elif raw_score >= 40:
            priority_tier = PriorityTier.TIER_3_MEDIUM
        else:
            priority_tier = PriorityTier.TIER_4_LOW

        rationale = (
            result.get("score_rationale")
            or result.get("reasoning")
            or "Score calculated based on attack surface and threat signals."
        )
        return raw_score, priority_tier, rationale

    def _persist_account_score(self, score: AccountScore) -> None:
        with (
            self._local_db_service if self._local_db_service is not None else default_database_service
        ).get_connection() as conn:
            saved = self._writer.save_score(conn, score)
            if conn is not None and hasattr(conn, "commit"):
                conn.commit()
            score.version = saved.get("version")

    def score_account(
        self,
        account: Union[Account, Dict[str, Any], ScoreAccountCommand, Any],
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
        save_to_db: bool = True,
    ) -> AccountScore:
        if isinstance(account, ScoreAccountCommand):
            target_account = account.account
            target_version = account.prompt_version or prompt_version
            target_custom_template = account.custom_prompt_template or custom_prompt_template
            target_save_to_db = account.save_to_db
        else:
            target_account = account
            target_version = prompt_version
            target_custom_template = custom_prompt_template
            target_save_to_db = save_to_db

        client = self._get_gemini_client()
        if not client:
            raise ValueError(
                "Gemini API key is required for AI scoring. Please log in and set up your API key in your Profile settings."
            )

        version = target_version or self.prompt_version
        account_key = getattr(target_account, "account_key", str(target_account))

        with logger.span("scorer.inference", account_key=account_key, model=self.model, version=version):
            start_time = time.time()
            prompt = self.get_prompt(
                target_account,
                prompt_version=version,
                custom_prompt_template=target_custom_template,
            )

            try:
                response = self._generate_with_retry(client, prompt)
                latency_ms = int((time.time() - start_time) * 1000)

                input_tokens, output_tokens, total_tokens, cost_usd = self._extract_token_usage_and_cost(response)
                content = (response.text if response else "") or "{}"
                result = self._parse_scoring_json(content)
                final_score, priority_tier, rationale = self._apply_score_guardrails(result, target_account)

                score = AccountScore(
                    account_key=account_key,
                    account=target_account,
                    score=final_score,
                    score_rationale=rationale,
                    priority_tier=priority_tier,
                    key_risks=result.get("key_risks", []),
                    suggested_outreach=result.get("suggested_outreach", ""),
                    model_version=version,
                    timestamp=datetime.now(),
                    tokens_used={"input": input_tokens, "output": output_tokens},
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )

                if target_save_to_db:
                    self._persist_account_score(score)

                self.log_trace(
                    LLMTrace(
                        id=f"trace-{int(time.time() * 1000)}-{hash(account_key) % 10000}",
                        timestamp=datetime.now(),
                        model=self.model,
                        prompt_version=version,
                        account_key=account_key,
                        request_tokens=input_tokens,
                        response_tokens=output_tokens,
                        total_tokens=total_tokens,
                        latency_ms=latency_ms,
                        cost_usd=cost_usd,
                        score=score.score,
                        priority_tier=score.priority_tier.value,
                        key_risks=score.key_risks,
                        suggested_outreach=score.suggested_outreach,
                    )
                )

                logger.info(
                    "Account scored successfully",
                    account_key=account_key,
                    score=score.score,
                    priority_tier=score.priority_tier.value,
                    latency_ms=latency_ms,
                    tokens=total_tokens,
                    cost_usd=cost_usd,
                )
                return score

            except Exception as e:
                logger.error("Error during scoring", account_key=account_key, error=str(e))
                raise

    def score_batch(
        self,
        account_keys: Union[List[str], BatchScoreCommand],
        limit: int = 10,
    ) -> List[AccountScore]:
        if isinstance(account_keys, BatchScoreCommand):
            target_keys = account_keys.account_keys
            target_limit = account_keys.limit
            prompt_version = account_keys.prompt_version
        else:
            target_keys = account_keys
            target_limit = limit
            prompt_version = None

        if not self._accounts_service:
            from src.services.accounts.dependencies import default_accounts_service

            self._accounts_service = default_accounts_service

        sliced_keys = target_keys[:target_limit]
        with logger.span("scorer.score_batch", count=len(sliced_keys)):
            accounts = self._accounts_service.get_accounts_batch(sliced_keys)
            scores = []
            for account in accounts:
                try:
                    score = self.score_account(account, prompt_version=prompt_version)
                    scores.append(score)
                except Exception as e:
                    acc_key = getattr(account, "account_key", str(account))
                    logger.error("Error scoring batch item", account_key=acc_key, error=str(e))
                    continue
            logger.info("Batch scoring completed", scored_count=len(scores), total_requested=len(sliced_keys))
            return scores

    def save_score(self, score: Union[AccountScore, dict]) -> dict:
        with (
            self._local_db_service if self._local_db_service is not None else default_database_service
        ).get_connection() as conn:
            res = self._writer.save_score(conn, score)
            if conn is not None and hasattr(conn, "commit"):
                conn.commit()
            return res

    def get_latest_score(self, account_key: str) -> Optional[dict]:
        return self.get_latest_score_for_account(account_key)

    def get_score_history(self, account_key: str) -> List[dict]:
        return self.get_score_history_for_account(account_key)

    def get_latest_score_for_account(self, account_key: str, version: Optional[str] = None) -> Optional[dict]:
        with (
            self._local_db_service if self._local_db_service is not None else default_database_service
        ).get_connection() as conn:
            return self._reader.get_latest_score(conn, account_key, version=version)

    def get_score_history_for_account(self, account_key: str, version: Optional[str] = None) -> List[dict]:
        with (
            self._local_db_service if self._local_db_service is not None else default_database_service
        ).get_connection() as conn:
            return self._reader.get_score_history(conn, account_key, version=version)

    def log_trace(self, trace: LLMTrace) -> None:
        self.traces.append(trace)
        logger.info(
            "llm.trace",
            trace_id=trace.id or trace.trace_id,
            account_key=trace.account_key,
            model=trace.model,
            prompt_version=trace.prompt_version,
            latency_ms=trace.latency_ms,
            request_tokens=trace.request_tokens,
            response_tokens=trace.response_tokens,
            total_tokens=trace.total_tokens,
            cost_usd=trace.cost_usd,
            score=trace.score,
            priority_tier=trace.priority_tier,
        )
        if self.trace_dir and self.trace_file:
            try:
                self.trace_dir.mkdir(parents=True, exist_ok=True)
                with open(self.trace_file, "a", encoding="utf-8") as f:
                    f.write(trace.model_dump_json() + "\n")
            except Exception as e:
                logger.warning("Could not write trace file", error=str(e))

    def get_traces(self) -> List[LLMTrace]:
        return self.traces

    def get_summary(self) -> Dict[str, Any]:
        if not self.traces:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "avg_latency_ms": 0,
                "trace_file": str(self.trace_file) if self.trace_file else None,
            }

        total = len(self.traces)
        total_tokens = sum(t.total_tokens for t in self.traces)
        total_cost = sum(t.cost_usd for t in self.traces)
        avg_latency = sum(t.latency_ms for t in self.traces) / total

        return {
            "total_calls": total,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "trace_file": str(self.trace_file) if self.trace_file else None,
        }


AccountScorer = ScorerService
default_scorer_service = ScorerService()
