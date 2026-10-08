"""Usage collection: Anthropic Admin API (org usage + cost) and llama-server metrics."""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
from typing import Any, AsyncIterator, Callable
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger("watch-bridge.usage")
ANTHROPIC_ORG = "https://api.anthropic.com/v1/organizations"
PROM_RE = re.compile(
    r"^llamacpp:(?:prompt_tokens_total|tokens_predicted_total)(?:\{[^}]*\})?\s+([0-9.eE+-]+)",
    re.M,
)


def iso_z(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class UsageCollector:
    def __init__(self, kv_get: Callable[..., Any], kv_set: Callable[[str, Any], None]):
        self.kv_get, self.kv_set = kv_get, kv_set
        self.admin_key = os.environ.get("ANTHROPIC_ADMIN_KEY", "")
        self.tz = ZoneInfo(os.environ.get("LOCAL_TZ", "America/New_York"))
        self.budget = float(os.environ.get("MONTHLY_BUDGET_USD", "0") or 0)
        # Cost report amounts: confirm units with one manual curl, then adjust.
        self.cost_divisor = float(os.environ.get("COST_AMOUNT_DIVISOR", "100"))
        self.metrics_urls = [
            u.strip() for u in os.environ.get("LLAMA_METRICS_URLS", "").split(",") if u.strip()
        ]

    async def collect(self) -> dict:
        out: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=15) as client:
            if self.admin_key:
                try:
                    out["tok"] = await self._claude_tokens(client)
                    today, mtd = await self._claude_cost(client)
                    out["usd"], out["mtd"] = round(today, 2), round(mtd, 2)
                    if self.budget > 0:
                        out["bud"] = int(round(100 * mtd / self.budget))
                except Exception as exc:
                    log.warning("anthropic usage fetch failed: %s", exc)
            if self.metrics_urls:
                out["ltk"] = await self._local_tokens(client)
        if "ltk" in out and "tok" in out:
            total = out["ltk"] + out["tok"]
            out["lsh"] = int(round(100 * out["ltk"] / total)) if total else 0
        return out

    async def _pages(self, client: httpx.AsyncClient, path: str,
                     params: dict) -> AsyncIterator[dict]:
        headers = {"x-api-key": self.admin_key, "anthropic-version": "2023-06-01"}
        params = dict(params)
        while True:
            resp = await client.get(f"{ANTHROPIC_ORG}{path}", params=params, headers=headers)
            resp.raise_for_status()
            body = resp.json()
            for bucket in body.get("data", []):
                yield bucket
            if not body.get("has_more") or not body.get("next_page"):
                break
            params["page"] = body["next_page"]

    async def _claude_tokens(self, client: httpx.AsyncClient) -> int:
        start = dt.datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        params = {"starting_at": iso_z(start), "bucket_width": "1h", "limit": 48}
        total = 0
        async for bucket in self._pages(client, "/usage_report/messages", params):
            for r in bucket.get("results", []):
                total += int(r.get("uncached_input_tokens") or 0)
                total += int(r.get("cache_read_input_tokens") or 0)
                total += int(r.get("output_tokens") or 0)
                cache = r.get("cache_creation") or {}
                total += sum(int(v or 0) for v in cache.values()
                             if isinstance(v, (int, float)))
        return total

    async def _claude_cost(self, client: httpx.AsyncClient) -> tuple[float, float]:
        # Cost buckets are daily and UTC-aligned, so "today" here is the UTC day.
        now = dt.datetime.now(dt.timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        params = {"starting_at": iso_z(start), "bucket_width": "1d", "limit": 31}
        today_key = now.date().isoformat()
        today = mtd = 0.0
        async for bucket in self._pages(client, "/cost_report", params):
            amount = sum(float(r.get("amount") or 0) for r in bucket.get("results", []))
            amount /= self.cost_divisor
            mtd += amount
            if str(bucket.get("starting_at", "")).startswith(today_key):
                today += amount
        return today, mtd

    async def _local_tokens(self, client: httpx.AsyncClient) -> int:
        """llama-server counters are cumulative since process start; keep a daily delta."""
        state = self.kv_get("local_counters", {})
        day = dt.datetime.now(self.tz).date().isoformat()
        total = 0.0
        for url in self.metrics_urls:
            s = state.get(url)
            try:
                text = (await client.get(url)).text
                raw = sum(float(v) for v in PROM_RE.findall(text))
                if s is None:
                    s = {"last": raw, "today": 0.0, "day": day}
                if s["day"] != day:
                    s = {"last": s["last"], "today": 0.0, "day": day}
                s["today"] += raw - s["last"] if raw >= s["last"] else raw  # restart
                s["last"] = raw
                state[url] = s
            except Exception as exc:
                log.warning("metrics fetch failed for %s: %s", url, exc)
            if s and s.get("day") == day:
                total += s["today"]
        self.kv_set("local_counters", state)
        return int(total)
