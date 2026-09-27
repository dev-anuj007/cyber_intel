import json
import os
import random
import re
import textwrap
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types

from src.core.config import GEMINI_MODEL, PRICING, PROMPT_VERSION
from src.services.accounts.protocols import IAccountsService
from src.services.accounts.types import Account, SecuritySignal
from src.services.scorer.dependencies import (
    ScorerServiceDependencyContext,
)
from src.services.scorer.internals.rate_limiter import global_rate_limiter
from src.services.scorer.protocols import IScorerService
from src.services.scorer.types import (
    AccountScore,
    BatchScoreCommand,
    CategorizedSignals,
    GetPromptQuery,
    LatestScoreResponse,
    LLMStats,
    PriorityTier,
    ScoreAccountCommand,
    ScoreHistoryItem,
    ScoringResponse,
)


class ScorerService(IScorerService):
    def __init__(
        self,
        context: ScorerServiceDependencyContext,
    ) -> None:
        self.context: ScorerServiceDependencyContext = context
        self.client: Optional[genai.Client] = (
            genai.Client(api_key=self.context.api_key) if self.context.api_key else None
        )
        self.prompt_version: str = self.context.prompt_version or PROMPT_VERSION
        self.model: str = self.context.model or GEMINI_MODEL
        self._accounts_service: Optional[IAccountsService] = (
            self.context.accounts_service
        )

    def score_account(
        self,
        command: ScoreAccountCommand,
    ) -> AccountScore:
        target_account = command.account
        version = command.prompt_version or self.prompt_version
        target_custom_template = command.custom_prompt_template
        target_save_to_db = command.save_to_db

        client = self._get_gemini_client()
        if not client:
            raise ValueError(
                "Gemini API key is required for AI scoring. Please log in and "
                "set up your API key in your Profile settings."
            )

        account_key = target_account.account_key

        with self.context.logger.span(
            "scorer.inference",
            account_key=account_key,
            model=self.model,
            version=version,
        ):
            start_time = time.time()
            prompt = self.get_prompt(
                GetPromptQuery(
                    account=target_account,
                    prompt_version=version,
                    custom_prompt_template=target_custom_template,
                )
            )

            try:
                response = self._generate_with_retry(client, prompt)
                latency_ms = int((time.time() - start_time) * 1000)

                (
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cost_usd,
                ) = self._extract_token_usage_and_cost(response)
                content = (response.text if response else "") or "{}"
                result = self._parse_scoring_json(content)
                (
                    final_score,
                    priority_tier,
                    rationale,
                ) = self._apply_score_guardrails(result, target_account)

                score = AccountScore(
                    account_key=account_key,
                    account=target_account,
                    score=final_score,
                    score_rationale=rationale,
                    priority_tier=priority_tier,
                    key_risks=result.get("key_risks", []),
                    suggested_outreach=result.get("suggested_outreach", ""),
                    model_version=version,
                    timestamp=datetime.now(timezone.utc),
                    tokens_used={"input": input_tokens, "output": output_tokens},
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )

                if target_save_to_db:
                    self._persist_account_score(score)

                self.context.logger.info(
                    "Account scored successfully",
                    account_key=account_key,
                    score=score.score,
                    priority_tier=score.priority_tier.value,
                    model=self.model,
                    prompt_version=version,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                )
                return score

            except Exception as e:
                self.context.logger.error(
                    "Error during scoring", account_key=account_key, error=str(e)
                )
                raise

    def score_batch(
        self,
        command: BatchScoreCommand,
    ) -> List[AccountScore]:
        accounts_service = self._accounts_service or self.context.accounts_service
        if not accounts_service:
            from src.services.accounts.dependencies import default_accounts_service

            accounts_service = default_accounts_service

        sliced_keys = command.account_keys[: command.limit]
        with self.context.logger.span("scorer.score_batch", count=len(sliced_keys)):
            accounts = accounts_service.get_accounts_batch(sliced_keys)
            scores: List[AccountScore] = []
            for account in accounts:
                try:
                    score = self.score_account(
                        ScoreAccountCommand(
                            account=account,
                            prompt_version=command.prompt_version,
                        )
                    )
                    scores.append(score)
                except Exception as e:
                    self.context.logger.error(
                        "Error scoring batch item",
                        account_key=account.account_key,
                        error=str(e),
                    )
                    continue
            self.context.logger.info(
                "Batch scoring completed",
                scored_count=len(scores),
                total_requested=len(sliced_keys),
            )
            return scores

    def save_score(self, score: AccountScore) -> dict:
        with self.context.db_service.get_connection() as conn:
            res = self.context.writer.save_score(conn, score)
            if conn is not None and hasattr(conn, "commit"):
                conn.commit()
            return res

    def get_latest_score(
        self, account_key: str, version: Optional[str] = None
    ) -> Optional[LatestScoreResponse]:
        with self.context.db_service.get_connection() as conn:
            raw = self.context.reader.get_latest_score(
                conn, account_key, version=version
            )
            return LatestScoreResponse(**raw) if raw else None

    def get_score_history(
        self, account_key: str, version: Optional[str] = None
    ) -> List[ScoreHistoryItem]:
        with self.context.db_service.get_connection() as conn:
            raw_history = self.context.reader.get_score_history(
                conn, account_key, version=version
            )
            return [ScoreHistoryItem(**item) for item in raw_history]

    def format_account_context(self, account: Account) -> str:
        categorized = self._categorize_signals(account.signals)
        crit_text, high_text, sample_text = self._format_signal_evidence_summary(
            categorized
        )

        domains = account.domains or []
        assets = account.assets or []
        ips = account.ips or []
        products = account.products or []
        cloud_providers = account.cloud_providers or []
        account_key = account.account_key

        return textwrap.dedent(f"""
        Account: {account_key}
        Domains: {", ".join(domains[:20])}
        Assets discovered: {len(assets)}
        Unique IPs: {len(ips)}
        Technology stack: {", ".join(products[:30]) or "Unknown"}
        Cloud providers: {", ".join(cloud_providers) or "None detected"}

        SECURITY SIGNALS SUMMARY:
        Total Signals: {categorized.total_count} (Critical: {len(categorized.critical)}, High: {len(categorized.high)}, Medium: {len(categorized.medium)}, Low: {len(categorized.low)})

        Critical ({len(categorized.critical)}):
        {crit_text}

        High severity ({len(categorized.high)}):
        {high_text}

        Representative Signal Sample:
        {sample_text}
        """).strip()

    def get_prompt(
        self,
        query: GetPromptQuery,
    ) -> str:
        context = self.format_account_context(query.account)

        if query.custom_prompt_template:
            if "{account_context}" in query.custom_prompt_template:
                return query.custom_prompt_template.replace(
                    "{account_context}", context
                )
            return f"{query.custom_prompt_template}\n\n{context}"

        version = query.prompt_version or self.prompt_version
        if self.context.prompt_service:
            template = self.context.prompt_service.get_template(version)
        else:
            from src.services.prompts.dependencies import default_prompt_service

            template = default_prompt_service.get_template(version)

        if "{account_context}" in template:
            return template.replace("{account_context}", context)
        return f"{template}\n\n{context}"

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * PRICING["input"]
        output_cost = (output_tokens / 1_000_000) * PRICING["output"]
        return input_cost + output_cost

    def get_summary(self) -> LLMStats:
        with self.context.db_service.get_connection() as conn:
            raw_stats = self.context.reader.get_llm_stats(conn)
            return LLMStats(**raw_stats)

    def set_accounts_service(self, accounts_service: IAccountsService) -> None:
        """Helper to dynamically set accounts service dependency."""
        self._accounts_service = accounts_service

    # =========================================================================
    # Internal / Helper Methods
    # =========================================================================

    def _get_gemini_client(self) -> Any:
        if self.client:
            return self.client
        api_key = self.context.api_key or os.getenv("GEMINI_API_KEY", "")
        if api_key:
            return genai.Client(api_key=api_key)
        return None

    def _generate_with_retry(
        self, client: Any, prompt: str, max_retries: int = 5
    ) -> Any:
        for attempt in range(max_retries):
            try:
                global_rate_limiter.acquire()
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
                if any(
                    code in err_str
                    for code in [
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "503",
                        "UNAVAILABLE",
                        "quota",
                    ]
                ):
                    if attempt < max_retries - 1:
                        match = re.search(
                            r"retry in ([\d\.]+)s", err_str, re.IGNORECASE
                        )
                        if match:
                            wait_time = float(match.group(1)) + random.uniform(0.5, 2.5)
                        else:
                            match_delay = re.search(
                                r"retryDelay['\"]?:\s*['\"]?(\d+)s?", err_str
                            )
                            if match_delay:
                                wait_time = float(
                                    match_delay.group(1)
                                ) + random.uniform(0.5, 2.5)
                            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                                wait_time = min(
                                    20.0, (2.0**attempt) * 2.5
                                ) + random.uniform(0.5, 2.0)
                            else:
                                wait_time = (2.0**attempt) * 1.5 + random.uniform(
                                    0.5, 1.5
                                )

                        self.context.logger.warning(
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
            self.context.logger.error(
                "Failed to parse scoring response", response_content=content
            )
            return {
                "score": 50,
                "priority_tier": "tier_3_medium",
                "key_risks": ["Unable to parse AI response"],
                "suggested_outreach": "Manual review required",
            }

    def _extract_token_usage_and_cost(
        self, response: Any
    ) -> Tuple[int, int, int, float]:
        usage = response.usage_metadata if response else None
        input_tokens = (
            usage.prompt_token_count if usage and usage.prompt_token_count else 0
        )
        output_tokens = (
            usage.candidates_token_count
            if usage and usage.candidates_token_count
            else 0
        )
        total_tokens = input_tokens + output_tokens
        cost_usd = self.calculate_cost(input_tokens, output_tokens)
        return input_tokens, output_tokens, total_tokens, cost_usd

    def _categorize_signals(
        self, signals: Optional[List[SecuritySignal]]
    ) -> CategorizedSignals:
        all_signals = signals or []
        critical_signals: List[SecuritySignal] = []
        high_signals: List[SecuritySignal] = []
        medium_signals: List[SecuritySignal] = []
        low_signals: List[SecuritySignal] = []

        for s in all_signals:
            sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
            sev_str = sev.lower()
            if sev_str == "critical":
                critical_signals.append(s)
            elif sev_str == "high":
                high_signals.append(s)
            elif sev_str == "medium":
                medium_signals.append(s)
            else:
                low_signals.append(s)

        return CategorizedSignals(
            critical=critical_signals,
            high=high_signals,
            medium=medium_signals,
            low=low_signals,
            total_count=len(all_signals),
        )

    def _apply_score_guardrails(
        self,
        result: Dict[str, Any],
        account: Account,
    ) -> Tuple[int, PriorityTier, str]:
        try:
            raw_score = int(result.get("score", 50))
        except (ValueError, TypeError):
            raw_score = 50
        raw_score = max(1, min(100, raw_score))
        original_score = raw_score

        acc_key = account.account_key
        categorized = self._categorize_signals(account.signals)

        critical_signals_count = len(categorized.critical)
        high_signals_count = len(categorized.high)
        medium_signals_count = len(categorized.medium)
        low_signals_count = len(categorized.low)

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
                self.context.logger.warning(
                    "Clamped hallucinated score to verified signal ceiling",
                    account_key=acc_key,
                    original_score=original_score,
                    clamped_score=raw_score,
                )

        if (
            critical_signals_count == 0
            and high_signals_count == 0
            and medium_signals_count == 0
        ):
            if raw_score > 45:
                raw_score = 30 if low_signals_count > 0 else 18
                self.context.logger.warning(
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
        with self.context.db_service.get_connection() as conn:
            saved = self.context.writer.save_score(conn, score)
            if conn is not None and hasattr(conn, "commit"):
                conn.commit()
            score.version = saved.get("version")

    def _format_signal_evidence_summary(
        self,
        signals: CategorizedSignals,
        max_sample: int = 15,
    ) -> Tuple[str, str, str]:
        crit_sample = signals.critical[:max_sample]
        high_sample = signals.high[:max_sample]
        other_sample = (signals.medium + signals.low)[:10]

        crit_text = (
            "\n".join(f"- {s.name}: {s.evidence}" for s in crit_sample)
            if crit_sample
            else "None"
        )
        if len(signals.critical) > max_sample:
            crit_text += f"\n- ... and {len(signals.critical) - max_sample} more critical signals"

        high_text = (
            "\n".join(f"- {s.name}: {s.evidence}" for s in high_sample)
            if high_sample
            else "None"
        )
        if len(signals.high) > max_sample:
            high_text += f"\n- ... and {len(signals.high) - max_sample} more high-severity signals"

        sample_signals = crit_sample + high_sample + other_sample
        all_signals_sample_text = "\n".join(
            f"- [{(s.severity.value if hasattr(s.severity, 'value') else str(s.severity)).upper()}] {s.name}: {s.evidence}"
            for s in sample_signals
        )
        if signals.total_count > len(sample_signals):
            all_signals_sample_text += (
                f"\n- ... ({signals.total_count} total signals detected: "
                f"{len(signals.critical)} critical, {len(signals.high)} high, "
                f"{len(signals.medium)} medium, {len(signals.low)} low)"
            )

        return crit_text, high_text, all_signals_sample_text
