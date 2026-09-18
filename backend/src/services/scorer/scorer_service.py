"""Scorer Business Service."""

import json
import time
import os
import textwrap
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

from google import genai
from google.genai import types

from src.services.database import get_db_connection, is_deployed
from src.core.config import (
    GEMINI_MODEL,
    PROMPT_VERSION,
    PRICING,
    DEFAULT_TRACE_DIR,
    ROOT_DIR,
)
from src.services.accounts.types import Account
from src.services.scorer.types import (
    IScorerService,
    IScoreReader,
    IScoreWriter,
    AccountScore,
    LLMTrace,
    PriorityTier,
    ScoringResponse,
)
from src.services.scorer.repositories.reader import ScoreReader
from src.services.scorer.repositories.writer import ScoreWriter
from src.services.scorer.repositories.dynamo_score import DynamoScoreRepository
from src.services.logger import get_logger

logger = get_logger("services.scorer")

MODEL = GEMINI_MODEL


class ScorerService(IScorerService):

    def __init__(
        self,
        db_path: Optional[Path] = None,
        reader: Optional[IScoreReader] = None,
        writer: Optional[IScoreWriter] = None,
        accounts_service: Optional[Any] = None,
        trace_dir: Optional[Union[str, Path]] = None,
        api_key: Optional[str] = None,
        prompt_version: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.db_path = db_path
        if is_deployed() and (reader is None or writer is None):
            dynamo_repo = DynamoScoreRepository()
            self.reader = reader or dynamo_repo
            self.writer = writer or dynamo_repo
        else:
            self.reader = reader or ScoreReader()
            self.writer = writer or ScoreWriter()
        self._accounts_service = accounts_service

        self.api_key = api_key
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.prompt_version = prompt_version or PROMPT_VERSION
        self.model = model or GEMINI_MODEL
        self.trace_dir = Path(trace_dir) if trace_dir is not None else None
        self.trace_file = (self.trace_dir / f"llm-traces-{int(time.time())}.jsonl") if self.trace_dir else None
        self.traces: List[LLMTrace] = []

    def set_accounts_service(self, accounts_service: Any) -> None:
        """Inject accounts service for inter-service communication."""
        self._accounts_service = accounts_service

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate LLM cost based on input and candidate tokens."""
        input_cost = (input_tokens / 1_000_000) * PRICING["input"]
        output_cost = (output_tokens / 1_000_000) * PRICING["output"]
        return input_cost + output_cost

    def format_account_context(self, account: Account) -> str:
        """Format account data for prompt context with intelligent signal truncation."""
        critical_signals = [s for s in account.signals if (getattr(s.severity, "value", s.severity) == "critical")]
        high_signals = [s for s in account.signals if (getattr(s.severity, "value", s.severity) == "high")]
        medium_signals = [s for s in account.signals if (getattr(s.severity, "value", s.severity) == "medium")]
        low_signals = [s for s in account.signals if (getattr(s.severity, "value", s.severity) == "low")]

        max_sample = 15
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
        if len(account.signals) > len(sample_signals):
            all_signals_sample_text += f"\n- ... ({len(account.signals)} total signals detected: {len(critical_signals)} critical, {len(high_signals)} high, {len(medium_signals)} medium, {len(low_signals)} low)"

        context = textwrap.dedent(f"""
        Account: {account.account_key}
        Domains: {', '.join(account.domains[:20])}
        Assets discovered: {len(account.assets)}
        Unique IPs: {len(account.ips)}
        Technology stack: {', '.join(account.products[:30]) or 'Unknown'}
        Cloud providers: {', '.join(account.cloud_providers) or 'None detected'}

        SECURITY SIGNALS SUMMARY:
        Total Signals: {len(account.signals)} (Critical: {len(critical_signals)}, High: {len(high_signals)}, Medium: {len(medium_signals)}, Low: {len(low_signals)})

        Critical ({len(critical_signals)}):
        {crit_text}

        High severity ({len(high_signals)}):
        {high_text}

        Representative Signal Sample:
        {all_signals_sample_text}
        """).strip()

        return context

    def get_prompt(
        self,
        account: Account,
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
    ) -> str:
        """Generate scoring prompt using versioned template or custom user template."""
        context = self.format_account_context(account)

        if custom_prompt_template:
            if "{account_context}" in custom_prompt_template:
                return custom_prompt_template.replace("{account_context}", context)
            else:
                return f"{custom_prompt_template}\n\n{context}"

        from src.services.prompts import default_prompt_service

        version = prompt_version or self.prompt_version
        template = default_prompt_service.get_template(version)
        if "{account_context}" in template:
            return template.replace("{account_context}", context)
        return f"{template}\n\n{context}"

    def score_account(
        self,
        account: Account,
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
    ) -> AccountScore:
        if not self.client:
            raise ValueError(
                "Gemini API key is required for AI scoring. Please log in and set up your API key in your Profile settings."
            )

        version = prompt_version or self.prompt_version

        with logger.span("scorer.inference", account_key=account.account_key, model=self.model, version=version):
            start_time = time.time()
            prompt = self.get_prompt(
                account,
                prompt_version=version,
                custom_prompt_template=custom_prompt_template,
            )

            try:
                max_retries = 5
                response = None
                for attempt in range(max_retries):
                    try:
                        response = self.client.models.generate_content(
                            model=self.model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=ScoringResponse,
                                max_output_tokens=2048,
                            ),
                        )
                        break
                    except Exception as e:
                        err_str = str(e)
                        if any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "quota"]):
                            if attempt < max_retries - 1:
                                match = re.search(r"retry in ([\d\.]+)s", err_str, re.IGNORECASE)
                                if match:
                                    wait_time = float(match.group(1)) + 1.5
                                else:
                                    match_delay = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)s?", err_str)
                                    if match_delay:
                                        wait_time = float(match_delay.group(1)) + 1.5
                                    elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                                        wait_time = 32.0
                                    else:
                                        wait_time = 3.0 * (2 ** attempt)

                                logger.warning(
                                    f"Rate limit / transient error on attempt {attempt + 1}/{max_retries}. Waiting {wait_time:.1f}s",
                                    attempt=attempt + 1,
                                    wait_time_s=wait_time,
                                )
                                time.sleep(wait_time)
                                continue
                        raise

                latency_ms = int((time.time() - start_time) * 1000)
                usage = response.usage_metadata if response else None
                input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count else 0
                output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count else 0
                total_tokens = input_tokens + output_tokens
                cost_usd = self.calculate_cost(input_tokens, output_tokens)

                content = (response.text if response else "") or "{}"

                try:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start == -1 or json_end == 0:
                        raise ValueError("No JSON found in response")

                    json_str = content[json_start:json_end]
                    result = json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    logger.error("Failed to parse scoring response", response_content=content)
                    result = {
                        "score": 50,
                        "priority_tier": "tier_3_medium",
                        "key_risks": ["Unable to parse AI response"],
                        "suggested_outreach": "Manual review required",
                    }

                raw_score = int(result.get("score", 50))
                raw_score = max(1, min(100, raw_score))

                critical_signals_count = len([s for s in account.signals if (getattr(s.severity, "value", s.severity) == "critical")])
                high_signals_count = len([s for s in account.signals if (getattr(s.severity, "value", s.severity) == "high")])
                medium_signals_count = len([s for s in account.signals if (getattr(s.severity, "value", s.severity) == "medium")])
                low_signals_count = len([s for s in account.signals if (getattr(s.severity, "value", s.severity) == "low")])

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
                            account_key=account.account_key,
                            original_score=int(result.get("score", 50)),
                            clamped_score=raw_score,
                        )

                if critical_signals_count == 0 and high_signals_count == 0 and medium_signals_count == 0:
                    if raw_score > 45:
                        raw_score = 30 if low_signals_count > 0 else 18
                        logger.warning(
                            "Clamped low-signal account score to low/medium ceiling",
                            account_key=account.account_key,
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

                rationale = result.get("score_rationale") or result.get("reasoning") or "Score calculated based on attack surface and threat signals."

                score = AccountScore(
                    account_key=account.account_key,
                    account=account,
                    score=raw_score,
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

                with get_db_connection(self.db_path) as conn:
                    saved = self.writer.save_score(conn, score)
                    conn.commit()
                    score.version = saved.get("version")

                self.log_trace(
                    LLMTrace(
                        id=f"trace-{int(time.time() * 1000)}-{hash(account.account_key) % 10000}",
                        timestamp=datetime.now(),
                        model=self.model,
                        prompt_version=version,
                        account_key=account.account_key,
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
                    account_key=account.account_key,
                    score=score.score,
                    priority_tier=score.priority_tier.value,
                    latency_ms=latency_ms,
                    tokens=total_tokens,
                    cost_usd=cost_usd,
                )
                return score

            except Exception as e:
                logger.error("Error during scoring", account_key=account.account_key, error=str(e))
                raise

    def score_batch(self, account_keys: List[str], limit: int = 10) -> List[AccountScore]:
        if not self._accounts_service:
            from src.services.accounts.accounts_service import default_accounts_service
            self._accounts_service = default_accounts_service

        target_keys = account_keys[:limit]
        with logger.span("scorer.score_batch", count=len(target_keys)):
            accounts = self._accounts_service.get_accounts_batch(target_keys)
            scores = []
            for account in accounts:
                try:
                    score = self.score_account(account)
                    scores.append(score)
                except Exception as e:
                    logger.error("Error scoring batch item", account_key=account.account_key, error=str(e))
                    continue
            logger.info("Batch scoring completed", scored_count=len(scores), total_requested=len(target_keys))
            return scores

    def get_latest_score_for_account(self, account_key: str) -> Optional[dict]:
        """Retrieve latest AI score version for an account."""
        with get_db_connection(self.db_path) as conn:
            return self.reader.get_latest_score(conn, account_key)

    def get_score_history_for_account(self, account_key: str) -> List[dict]:
        """Retrieve full versioned score history for an account."""
        with get_db_connection(self.db_path) as conn:
            return self.reader.get_score_history(conn, account_key)

    def log_trace(self, trace: LLMTrace) -> None:
        self.traces.append(trace)
        logger.info(
            "llm.trace",
            trace_id=trace.id,
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
        if self.trace_dir:
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
