#!/usr/bin/env python3
"""Bulk add domains (zones) to Cloudflare and export assigned nameservers."""

from __future__ import annotations

import argparse
import csv
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []


def _is_zone_quota_error(message: str) -> bool:
    msg = message.lower()
    return "exceeded the limit for adding zones" in msg


def _is_retryable_throttle_message(message: str) -> bool:
    msg = message.lower()
    if _is_zone_quota_error(msg):
        return False
    return (
        "please wait and consider throttling your request speed" in msg
        or "rate limit" in msg
        or "too many requests" in msg
    )


def _extract_retry_after_seconds(header_value: str | None) -> float | None:
    if not header_value:
        return None
    try:
        seconds = float(header_value.strip())
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _compute_backoff(attempt: int, base: float, max_backoff: float = 20.0) -> float:
    # Exponential backoff: base, 2*base, 4*base...
    delay = base * (2 ** max(0, attempt - 1))
    return min(delay, max_backoff)


def build_ssl_context(insecure: bool = False, ca_bundle: str | None = None) -> ssl.SSLContext:
    if insecure:
        return ssl._create_unverified_context()  # noqa: SLF001

    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def read_domains(path: str) -> list[str]:
    seen: set[str] = set()
    domains: list[str] = []

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            # Support comma/semicolon separated lists in one line.
            candidates = [c.strip().lower().rstrip(".") for c in line.replace(";", ",").split(",")]
            for domain in candidates:
                if not domain:
                    continue
                if domain not in seen:
                    seen.add(domain)
                    domains.append(domain)

    return domains


def _api_request(
    token: str,
    method: str,
    path: str,
    *,
    ssl_context: ssl.SSLContext,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    max_retries: int = 5,
    retry_base_delay: float = 1.0,
) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    if query:
        url += f"?{urllib.parse.urlencode(query)}"

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    for attempt in range(1, max_retries + 2):
        req = urllib.request.Request(url=url, data=data, method=method, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as resp:
                raw = resp.read().decode("utf-8")
                parsed = json.loads(raw)

                # Cloudflare can return throttling as success=false JSON payload.
                if isinstance(parsed, dict) and not parsed.get("success", True):
                    errors = parsed.get("errors", []) if isinstance(parsed.get("errors"), list) else []
                    detail = "; ".join(str(err.get("message", err)) for err in errors)
                    if _is_retryable_throttle_message(detail) and attempt <= max_retries:
                        time.sleep(_compute_backoff(attempt, retry_base_delay))
                        continue

                return parsed
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {}

            errors = parsed.get("errors", []) if isinstance(parsed, dict) else []
            detail = "; ".join(str(err.get("message", err)) for err in errors) if errors else body or str(e)

            retryable_http_429 = e.code == 429 and _is_retryable_throttle_message(detail)
            if retryable_http_429 and attempt <= max_retries:
                retry_after = _extract_retry_after_seconds(e.headers.get("Retry-After"))
                wait_seconds = retry_after if retry_after is not None else _compute_backoff(attempt, retry_base_delay)
                time.sleep(wait_seconds)
                continue

            raise CloudflareAPIError(
                f"HTTP {e.code}: {detail}",
                status_code=e.code,
                errors=errors,
            ) from e
        except urllib.error.URLError as e:
            raise CloudflareAPIError(f"Network error: {e}") from e

    raise CloudflareAPIError("Unexpected retry loop termination")


def list_zone_by_name(
    token: str,
    domain: str,
    ssl_context: ssl.SSLContext,
    *,
    max_retries: int = 5,
    retry_base_delay: float = 1.0,
) -> dict[str, Any] | None:
    response = _api_request(
        token,
        "GET",
        "/zones",
        ssl_context=ssl_context,
        max_retries=max_retries,
        retry_base_delay=retry_base_delay,
        query={"name": domain, "per_page": 1, "match": "all"},
    )

    if not response.get("success"):
        errors = response.get("errors", [])
        detail = "; ".join(str(err.get("message", err)) for err in errors)
        raise CloudflareAPIError(f"List zone failed: {detail}", errors=errors)

    result = response.get("result") or []
    return result[0] if result else None


def get_first_account_id(
    token: str,
    ssl_context: ssl.SSLContext,
    *,
    max_retries: int = 5,
    retry_base_delay: float = 1.0,
) -> str | None:
    response = _api_request(
        token,
        "GET",
        "/accounts",
        ssl_context=ssl_context,
        max_retries=max_retries,
        retry_base_delay=retry_base_delay,
        query={"per_page": 1, "page": 1},
    )

    if not response.get("success"):
        return None

    result = response.get("result") or []
    if not result:
        return None

    return result[0].get("id")


def create_zone(
    token: str,
    domain: str,
    account_id: str | None,
    ssl_context: ssl.SSLContext,
    *,
    max_retries: int = 5,
    retry_base_delay: float = 1.0,
) -> tuple[str, dict[str, Any], str]:
    payload: dict[str, Any] = {
        "name": domain,
        "type": "full",
    }
    if account_id:
        payload["account"] = {"id": account_id}

    try:
        response = _api_request(
            token,
            "POST",
            "/zones",
            ssl_context=ssl_context,
            payload=payload,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
        )
    except CloudflareAPIError as e:
        message = str(e).lower()
        already_exists = any(
            "already" in str(err.get("message", "")).lower() and "exists" in str(err.get("message", "")).lower()
            for err in e.errors
        ) or ("already" in message and "exists" in message)

        if already_exists:
            zone = list_zone_by_name(
                token,
                domain,
                ssl_context,
                max_retries=max_retries,
                retry_base_delay=retry_base_delay,
            )
            if zone:
                return "existing", zone, "Zone already exists in account"
            return "error", {}, "Zone already exists, but failed to read existing zone"

        return "error", {}, str(e)

    if not response.get("success"):
        errors = response.get("errors", [])
        missing_zone_create_permission = any(
            "com.cloudflare.api.account.zone.create" in str(err.get("message", ""))
            for err in errors
        )
        if missing_zone_create_permission:
            return (
                "error",
                {},
                (
                    "Missing permission to create zones "
                    "(com.cloudflare.api.account.zone.create). "
                    "Update API token permissions."
                ),
            )
        detail = "; ".join(str(err.get("message", err)) for err in errors) or "Unknown API error"
        return "error", {}, detail

    zone = response.get("result") or {}
    return "created", zone, "OK"


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "domain",
        "status",
        "zone_id",
        "ns1",
        "ns2",
        "name_servers",
        "message",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["name_servers"] = ", ".join(row.get("name_servers", []))
            writer.writerow(out)


def write_json(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk add domains to Cloudflare and export assigned nameservers.",
    )
    parser.add_argument("--domains-file", required=True, help="Path to txt/csv file with domains")
    parser.add_argument("--account-id", help="Cloudflare account ID (optional)")
    parser.add_argument("--token", help="Cloudflare API token (or use CLOUDFLARE_API_TOKEN / CF_API_TOKEN)")
    parser.add_argument("--out-csv", default="cloudflare_ns_results.csv", help="Output CSV file")
    parser.add_argument("--out-json", default="cloudflare_ns_results.json", help="Output JSON file")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between requests in seconds")
    parser.add_argument("--ca-bundle", help="Custom CA bundle path (PEM)")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification (not recommended)")
    parser.add_argument("--max-retries", type=int, default=5, help="Max retries for temporary 429 throttling")
    parser.add_argument("--retry-base-delay", type=float, default=1.0, help="Base retry delay for 429 (seconds)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = args.token or os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN")

    if not token:
        print("ERROR: API token is required. Pass --token or set CLOUDFLARE_API_TOKEN.", file=sys.stderr)
        return 2

    domains = read_domains(args.domains_file)
    if not domains:
        print("ERROR: No domains found in input file.", file=sys.stderr)
        return 2

    ssl_context = build_ssl_context(args.insecure, args.ca_bundle)
    account_id = args.account_id
    if not account_id:
        account_id = get_first_account_id(
            token,
            ssl_context,
            max_retries=args.max_retries,
            retry_base_delay=args.retry_base_delay,
        )
        if account_id:
            print(f"Using auto-detected account_id: {account_id}")
        else:
            print("WARNING: Could not auto-detect account_id; creating zones without account_id.")

    rows: list[dict[str, Any]] = []

    print(f"Processing {len(domains)} domains...")

    for i, domain in enumerate(domains, start=1):
        status, zone, message = create_zone(
            token,
            domain,
            account_id,
            ssl_context,
            max_retries=args.max_retries,
            retry_base_delay=args.retry_base_delay,
        )
        name_servers = zone.get("name_servers") or []
        row = {
            "domain": domain,
            "status": status,
            "zone_id": zone.get("id", ""),
            "ns1": name_servers[0] if len(name_servers) > 0 else "",
            "ns2": name_servers[1] if len(name_servers) > 1 else "",
            "name_servers": name_servers,
            "message": message,
        }
        rows.append(row)

        ns_text = ", ".join(name_servers) if name_servers else "-"
        print(f"[{i}/{len(domains)}] {domain} -> {status.upper()} | NS: {ns_text}")

        if args.delay > 0 and i < len(domains):
            time.sleep(args.delay)

    write_csv(args.out_csv, rows)
    write_json(args.out_json, rows)

    created = sum(1 for r in rows if r["status"] == "created")
    existing = sum(1 for r in rows if r["status"] == "existing")
    failed = sum(1 for r in rows if r["status"] == "error")

    print("\nDone.")
    print(f"Created: {created} | Existing: {existing} | Errors: {failed}")
    print(f"CSV: {args.out_csv}")
    print(f"JSON: {args.out_json}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
