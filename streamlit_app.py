#!/usr/bin/env python3
"""Streamlit UI for Cloudflare bulk import and ID lookup."""

from __future__ import annotations

import csv
import io
import time
from typing import Any

import streamlit as st

import cf_bulk_add_zones as cf

st.set_page_config(page_title="Cloudflare Domain Toolkit", layout="wide")


def parse_domains_from_text(raw: str) -> list[str]:
    seen: set[str] = set()
    domains: list[str] = []

    for line in raw.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue

        for part in clean.replace(";", ",").split(","):
            domain = part.strip().lower().rstrip(".")
            if not domain or domain in seen:
                continue
            seen.add(domain)
            domains.append(domain)

    return domains


def rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in columns})
    return output.getvalue()


def rows_to_tsv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(str(row.get(c, "")) for c in columns))
    return "\n".join(lines)


def run_bulk_import(token: str, domains_text: str, account_id: str | None, delay: float) -> dict[str, Any]:
    domains = parse_domains_from_text(domains_text)
    if not domains:
        return {"ok": False, "error": "No domains provided"}

    ssl_context = cf.build_ssl_context(False, None)

    account_id_used = account_id or cf.get_first_account_id(token, ssl_context)
    rows: list[dict[str, Any]] = []

    for i, domain in enumerate(domains):
        status, zone, message = cf.create_zone(token, domain, account_id_used, ssl_context)
        name_servers = zone.get("name_servers") or []
        rows.append(
            {
                "domain": domain,
                "status": status,
                "zone_id": zone.get("id", ""),
                "ns1": name_servers[0] if len(name_servers) > 0 else "",
                "ns2": name_servers[1] if len(name_servers) > 1 else "",
                "message": message,
            }
        )
        if delay > 0 and i < len(domains) - 1:
            time.sleep(delay)

    return {
        "ok": True,
        "rows": rows,
        "summary": {
            "total": len(rows),
            "created": sum(1 for r in rows if r["status"] == "created"),
            "existing": sum(1 for r in rows if r["status"] == "existing"),
            "errors": sum(1 for r in rows if r["status"] == "error"),
        },
        "account_id_used": account_id_used,
    }


def run_lookup_ids(token: str, domains_text: str, delay: float) -> dict[str, Any]:
    domains = parse_domains_from_text(domains_text)
    if not domains:
        return {"ok": False, "error": "No domains provided"}

    ssl_context = cf.build_ssl_context(False, None)
    rows: list[dict[str, Any]] = []

    for i, domain in enumerate(domains):
        try:
            zone = cf.list_zone_by_name(token, domain, ssl_context)
            if zone:
                account_obj = zone.get("account") or {}
                name_servers = zone.get("name_servers") or []
                rows.append(
                    {
                        "domain": domain,
                        "status": "found",
                        "zone_id": zone.get("id", ""),
                        "account_id": account_obj.get("id", ""),
                        "account_name": account_obj.get("name", ""),
                        "ns1": name_servers[0] if len(name_servers) > 0 else "",
                        "ns2": name_servers[1] if len(name_servers) > 1 else "",
                        "message": "OK",
                    }
                )
            else:
                rows.append(
                    {
                        "domain": domain,
                        "status": "not_found",
                        "zone_id": "",
                        "account_id": "",
                        "account_name": "",
                        "ns1": "",
                        "ns2": "",
                        "message": "Zone not found for this token",
                    }
                )
        except cf.CloudflareAPIError as e:
            rows.append(
                {
                    "domain": domain,
                    "status": "error",
                    "zone_id": "",
                    "account_id": "",
                    "account_name": "",
                    "ns1": "",
                    "ns2": "",
                    "message": str(e),
                }
            )

        if delay > 0 and i < len(domains) - 1:
            time.sleep(delay)

    return {
        "ok": True,
        "rows": rows,
        "summary": {
            "total": len(rows),
            "found": sum(1 for r in rows if r["status"] == "found"),
            "not_found": sum(1 for r in rows if r["status"] == "not_found"),
            "errors": sum(1 for r in rows if r["status"] == "error"),
        },
    }


st.title("Cloudflare Domain Toolkit")
st.caption("Стабільний Streamlit-інтерфейс: Add Domains + NS та Lookup Zone/Account IDs")

tab1, tab2 = st.tabs(["1) Add Domains + NS", "2) Lookup Zone/Account IDs"])

with tab1:
    c1, c2 = st.columns([1.2, 1])
    with c1:
        token = st.text_input("Cloudflare API Token", type="password", key="import_token")
        account_id = st.text_input("Account ID (опційно)", key="import_account_id")
        delay = st.number_input("Затримка між запитами (сек)", min_value=0.0, max_value=5.0, value=0.2, step=0.1, key="import_delay")
        domains_text = st.text_area("Список доменів", height=260, key="import_domains", placeholder="example.com\nexample.net\nfoo.org, bar.io")

        if st.button("Додати домени і отримати NS", type="primary", key="run_import"):
            if not token.strip():
                st.error("Додай API токен")
            elif not domains_text.strip():
                st.error("Встав список доменів")
            else:
                with st.spinner("Обробляю домени..."):
                    result = run_bulk_import(token.strip(), domains_text, account_id.strip() or None, float(delay))
                st.session_state["import_result"] = result

    with c2:
        result = st.session_state.get("import_result")
        if result:
            if not result.get("ok"):
                st.error(result.get("error", "Unknown error"))
            else:
                s = result["summary"]
                st.success(
                    f"Готово. total={s['total']}, created={s['created']}, "
                    f"existing={s['existing']}, errors={s['errors']}"
                    + (f", account_id={result.get('account_id_used')}" if result.get("account_id_used") else "")
                )
                rows = result["rows"]
                st.dataframe(rows, use_container_width=True, height=420)

                csv_data = rows_to_csv(rows, ["domain", "status", "zone_id", "ns1", "ns2", "message"])
                tsv_data = rows_to_tsv(rows, ["domain", "status", "ns1", "ns2", "message"])
                ns_tsv = rows_to_tsv(rows, ["domain", "ns1", "ns2"])

                st.download_button("Завантажити CSV", csv_data, file_name="cloudflare_ns_results_ui.csv", mime="text/csv", key="dl_import_csv")
                st.text_area("Копіювати TSV таблицю", value=tsv_data, height=120, key="import_tsv")
                st.text_area("Копіювати domain + NS", value=ns_tsv, height=120, key="import_ns_tsv")

with tab2:
    c1, c2 = st.columns([1.2, 1])
    with c1:
        lookup_token = st.text_input("Cloudflare API Token", type="password", key="lookup_token")
        lookup_delay = st.number_input("Затримка між запитами (сек)", min_value=0.0, max_value=5.0, value=0.2, step=0.1, key="lookup_delay")
        lookup_domains = st.text_area("Список доменів", height=260, key="lookup_domains", placeholder="example.com\nexample.net\nfoo.org, bar.io")

        if st.button("Знайти zone/account IDs", type="primary", key="run_lookup"):
            if not lookup_token.strip():
                st.error("Додай API токен")
            elif not lookup_domains.strip():
                st.error("Встав список доменів")
            else:
                with st.spinner("Шукаю zone_id/account_id..."):
                    result = run_lookup_ids(lookup_token.strip(), lookup_domains, float(lookup_delay))
                st.session_state["lookup_result"] = result

    with c2:
        result = st.session_state.get("lookup_result")
        if result:
            if not result.get("ok"):
                st.error(result.get("error", "Unknown error"))
            else:
                s = result["summary"]
                st.success(f"Готово. total={s['total']}, found={s['found']}, not_found={s['not_found']}, errors={s['errors']}")
                rows = result["rows"]
                st.dataframe(rows, use_container_width=True, height=420)

                csv_data = rows_to_csv(rows, ["domain", "status", "zone_id", "account_id", "account_name", "ns1", "ns2", "message"])
                tsv_data = rows_to_tsv(rows, ["domain", "status", "zone_id", "account_id", "account_name", "ns1", "ns2", "message"])
                ids_tsv = rows_to_tsv(rows, ["domain", "zone_id", "account_id"])

                st.download_button("Завантажити CSV", csv_data, file_name="cloudflare_zone_account_lookup.csv", mime="text/csv", key="dl_lookup_csv")
                st.text_area("Копіювати TSV таблицю", value=tsv_data, height=120, key="lookup_tsv")
                st.text_area("Копіювати domain + IDs", value=ids_tsv, height=120, key="lookup_ids_tsv")
