#!/usr/bin/env python3
"""Local web UI for bulk Cloudflare actions: add zones and lookup IDs."""

from __future__ import annotations

import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import cf_bulk_add_zones as cf

HOST = "127.0.0.1"
PORT = 8787

HTML = """<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cloudflare Domain Toolkit</title>
  <style>
    :root {
      --bg: #f3efe7;
      --ink: #1f1f1f;
      --muted: #6a6762;
      --panel: #fffaf2;
      --line: #d8cfc0;
      --ok: #0f7b44;
      --warn: #9b6510;
      --err: #b4261a;
      --accent: #0f766e;
      --accent-2: #d97706;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 10%, #ffd89a 0, transparent 22%),
        radial-gradient(circle at 88% 20%, #8ad5c4 0, transparent 24%),
        radial-gradient(circle at 40% 100%, #f6b5aa 0, transparent 25%),
        var(--bg);
      min-height: 100vh;
    }

    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }

    .hero {
      background: linear-gradient(120deg, #fff6e8 0%, #e8f8f4 100%);
      border: 2px solid #ead9bd;
      border-radius: 20px;
      padding: 22px;
      box-shadow: 0 9px 0 #d9c6a5;
    }

    h1 {
      margin: 0;
      font-size: clamp(1.4rem, 2.4vw, 2.1rem);
      line-height: 1.15;
      letter-spacing: 0.01em;
    }

    .sub {
      color: var(--muted);
      margin-top: 8px;
      font-size: 0.98rem;
    }

    .tabs {
      margin-top: 16px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .tab-btn {
      border: 1px solid #d8c3a4;
      border-radius: 999px;
      padding: 10px 14px;
      background: #f6ecdd;
      color: #5f492e;
      font-weight: 700;
      cursor: pointer;
    }

    .tab-btn.active {
      background: linear-gradient(90deg, var(--accent), #10968c);
      color: #fff;
      border-color: #0f766e;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    .grid {
      margin-top: 18px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
    }

    @media (min-width: 980px) {
      .grid { grid-template-columns: 1.1fr 0.9fr; }
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 4px 0 #ebe0cf;
    }

    label {
      font-weight: 600;
      display: block;
      margin-bottom: 6px;
      font-size: 0.92rem;
    }

    input, textarea {
      width: 100%;
      border: 1.8px solid #d7c8b2;
      border-radius: 12px;
      padding: 11px 12px;
      font-size: 0.95rem;
      background: #fffefb;
      color: var(--ink);
      outline: none;
      transition: border-color 0.14s ease, box-shadow 0.14s ease;
      margin-bottom: 12px;
    }

    input:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.18);
    }

    textarea {
      min-height: 260px;
      resize: vertical;
      font-family: "IBM Plex Mono", "SFMono-Regular", Menlo, monospace;
      line-height: 1.35;
    }

    .row {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }

    @media (min-width: 620px) {
      .row.two { grid-template-columns: 1fr 1fr; }
      .row.three { grid-template-columns: 1fr 1fr 1fr; }
    }

    button {
      border: none;
      border-radius: 11px;
      padding: 11px 14px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.08s ease, opacity 0.14s ease;
    }

    button:active { transform: translateY(1px); }

    .btn-main {
      background: linear-gradient(90deg, var(--accent), #10968c);
      color: white;
    }

    .btn-warn {
      background: linear-gradient(90deg, var(--accent-2), #e48f1c);
      color: white;
    }

    .btn-light {
      background: #f6ecdd;
      color: #5f492e;
      border: 1px solid #d8c3a4;
    }

    .actions { display: flex; gap: 8px; flex-wrap: wrap; }

    .status {
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 0.93rem;
      border: 1px solid #d9c7ad;
      background: #fff7ea;
      color: #6f5838;
      min-height: 42px;
      display: flex;
      align-items: center;
    }

    .summary {
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
    }

    .kpi {
      border-radius: 11px;
      border: 1px solid #d8cfc0;
      background: #fffef9;
      padding: 10px;
    }

    .kpi .label { font-size: 0.76rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .kpi .value { font-size: 1.24rem; font-weight: 800; margin-top: 4px; }

    .table-wrap {
      margin-top: 14px;
      border-radius: 12px;
      overflow: auto;
      border: 1px solid #d7ccbc;
      background: #fffdf8;
      max-height: 55vh;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 940px;
      font-size: 0.91rem;
    }

    th, td {
      padding: 9px 10px;
      border-bottom: 1px solid #ebe0d0;
      text-align: left;
      vertical-align: top;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f9f2e5;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: #6f634f;
    }

    .tag {
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 700;
      display: inline-block;
    }

    .tag.created { background: #daf4e6; color: var(--ok); }
    .tag.existing, .tag.found { background: #fde9c9; color: var(--warn); }
    .tag.error { background: #ffe0de; color: var(--err); }
    .tag.not_found { background: #eef1f3; color: #66737e; }

    .foot {
      margin-top: 10px;
      color: #72634f;
      font-size: 0.84rem;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Cloudflare Domain Toolkit</h1>
      <p class="sub">Дві вкладки: масове додавання доменів з NS або пошук zone_id/account_id для пачки доменів.</p>
    </section>

    <div class="tabs">
      <button class="tab-btn active" data-tab="importTab">1) Add Domains + NS</button>
      <button class="tab-btn" data-tab="lookupTab">2) Lookup Zone/Account IDs</button>
    </div>

    <section id="importTab" class="tab-content active">
      <div class="grid">
        <section class="panel">
          <label for="token">Cloudflare API Token</label>
          <input id="token" type="password" placeholder="cfut_..." autocomplete="off" />

          <div class="row two">
            <div>
              <label for="accountId">Account ID (опційно)</label>
              <input id="accountId" type="text" placeholder="eab493064820c..." />
            </div>
            <div>
              <label for="delay">Затримка між запитами (сек)</label>
              <input id="delay" type="number" min="0" step="0.1" value="0.2" />
            </div>
          </div>

          <label for="domains">Список доменів</label>
          <textarea id="domains" placeholder="example.com\nexample.net\nfoo.org, bar.io"></textarea>

          <div class="actions">
            <button id="runBtn" class="btn-main">Додати домени і отримати NS</button>
            <button id="copyTsvBtn" class="btn-light">Скопіювати таблицю (TSV)</button>
            <button id="copyNsBtn" class="btn-warn">Скопіювати domain + NS</button>
            <button id="downloadCsvBtn" class="btn-light">Завантажити CSV</button>
          </div>

          <div id="status" class="status">Готово до запуску.</div>
        </section>

        <section class="panel">
          <div class="summary">
            <div class="kpi"><div class="label">Всього</div><div id="kpiTotal" class="value">0</div></div>
            <div class="kpi"><div class="label">Created</div><div id="kpiCreated" class="value">0</div></div>
            <div class="kpi"><div class="label">Existing</div><div id="kpiExisting" class="value">0</div></div>
            <div class="kpi"><div class="label">Errors</div><div id="kpiErrors" class="value">0</div></div>
          </div>

          <div class="table-wrap">
            <table id="resultsTable">
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Status</th>
                  <th>NS1</th>
                  <th>NS2</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody></tbody>
            </table>
          </div>

          <p class="foot">Порада: для реєстратора зазвичай потрібні тільки NS1 і NS2.</p>
        </section>
      </div>
    </section>

    <section id="lookupTab" class="tab-content">
      <div class="grid">
        <section class="panel">
          <label for="lookupToken">Cloudflare API Token</label>
          <input id="lookupToken" type="password" placeholder="cfut_..." autocomplete="off" />

          <div class="row two">
            <div>
              <label for="lookupDelay">Затримка між запитами (сек)</label>
              <input id="lookupDelay" type="number" min="0" step="0.1" value="0.2" />
            </div>
            <div>
              <label for="lookupReserved">Пакетний lookup</label>
              <input id="lookupReserved" type="text" value="zone_id + account_id" disabled />
            </div>
          </div>

          <label for="lookupDomains">Список доменів</label>
          <textarea id="lookupDomains" placeholder="example.com\nexample.net\nfoo.org, bar.io"></textarea>

          <div class="actions">
            <button id="lookupRunBtn" class="btn-main">Знайти zone/account IDs</button>
            <button id="lookupCopyTsvBtn" class="btn-light">Скопіювати таблицю (TSV)</button>
            <button id="lookupCopyIdsBtn" class="btn-warn">Скопіювати domain + IDs</button>
            <button id="lookupDownloadCsvBtn" class="btn-light">Завантажити CSV</button>
          </div>

          <div id="lookupStatus" class="status">Готово до lookup.</div>
        </section>

        <section class="panel">
          <div class="summary">
            <div class="kpi"><div class="label">Всього</div><div id="lookupKpiTotal" class="value">0</div></div>
            <div class="kpi"><div class="label">Found</div><div id="lookupKpiFound" class="value">0</div></div>
            <div class="kpi"><div class="label">Not Found</div><div id="lookupKpiNotFound" class="value">0</div></div>
            <div class="kpi"><div class="label">Errors</div><div id="lookupKpiErrors" class="value">0</div></div>
          </div>

          <div class="table-wrap">
            <table id="lookupTable">
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Status</th>
                  <th>Zone ID</th>
                  <th>Account ID</th>
                  <th>Account</th>
                  <th>NS1</th>
                  <th>NS2</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody></tbody>
            </table>
          </div>

          <p class="foot">Ця вкладка не створює зони. Вона тільки читає дані по існуючих зонах.</p>
        </section>
      </div>
    </section>
  </div>

  <script>
    (function () {
      var state = { rows: [], lookupRows: [] };

      var el = {
        tabButtons: document.querySelectorAll('.tab-btn'),
        tabContents: document.querySelectorAll('.tab-content'),

        token: document.getElementById('token'),
        accountId: document.getElementById('accountId'),
        delay: document.getElementById('delay'),
        domains: document.getElementById('domains'),
        runBtn: document.getElementById('runBtn'),
        copyTsvBtn: document.getElementById('copyTsvBtn'),
        copyNsBtn: document.getElementById('copyNsBtn'),
        downloadCsvBtn: document.getElementById('downloadCsvBtn'),
        status: document.getElementById('status'),
        tbody: document.querySelector('#resultsTable tbody'),
        kpiTotal: document.getElementById('kpiTotal'),
        kpiCreated: document.getElementById('kpiCreated'),
        kpiExisting: document.getElementById('kpiExisting'),
        kpiErrors: document.getElementById('kpiErrors'),

        lookupToken: document.getElementById('lookupToken'),
        lookupDelay: document.getElementById('lookupDelay'),
        lookupDomains: document.getElementById('lookupDomains'),
        lookupRunBtn: document.getElementById('lookupRunBtn'),
        lookupCopyTsvBtn: document.getElementById('lookupCopyTsvBtn'),
        lookupCopyIdsBtn: document.getElementById('lookupCopyIdsBtn'),
        lookupDownloadCsvBtn: document.getElementById('lookupDownloadCsvBtn'),
        lookupStatus: document.getElementById('lookupStatus'),
        lookupTbody: document.querySelector('#lookupTable tbody'),
        lookupKpiTotal: document.getElementById('lookupKpiTotal'),
        lookupKpiFound: document.getElementById('lookupKpiFound'),
        lookupKpiNotFound: document.getElementById('lookupKpiNotFound'),
        lookupKpiErrors: document.getElementById('lookupKpiErrors')
      };

      function setStatus(text) {
        el.status.textContent = text;
      }

      function setLookupStatus(text) {
        el.lookupStatus.textContent = text;
      }

      function replaceAllSafe(value, search, replacement) {
        return String(value).split(search).join(replacement);
      }

      function escapeHtml(value) {
        var out = String(value);
        out = replaceAllSafe(out, '&', '&amp;');
        out = replaceAllSafe(out, '<', '&lt;');
        out = replaceAllSafe(out, '>', '&gt;');
        out = replaceAllSafe(out, '"', '&quot;');
        out = replaceAllSafe(out, "'", '&#039;');
        return out;
      }

      function statusTag(status) {
        var safe = String(status || '').toLowerCase();
        return '<span class="tag ' + safe + '">' + (safe || '-') + '</span>';
      }

      function renderRows(rows) {
        state.rows = rows || [];
        var html = '';
        var i;
        for (i = 0; i < state.rows.length; i++) {
          var r = state.rows[i];
          html += '<tr>' +
            '<td>' + escapeHtml(r.domain || '') + '</td>' +
            '<td>' + statusTag(r.status) + '</td>' +
            '<td>' + escapeHtml(r.ns1 || '') + '</td>' +
            '<td>' + escapeHtml(r.ns2 || '') + '</td>' +
            '<td>' + escapeHtml(r.message || '') + '</td>' +
            '</tr>';
        }
        el.tbody.innerHTML = html;

        var created = 0;
        var existing = 0;
        var errors = 0;
        for (i = 0; i < state.rows.length; i++) {
          if (state.rows[i].status === 'created') created++;
          if (state.rows[i].status === 'existing') existing++;
          if (state.rows[i].status === 'error') errors++;
        }
        el.kpiTotal.textContent = String(state.rows.length);
        el.kpiCreated.textContent = String(created);
        el.kpiExisting.textContent = String(existing);
        el.kpiErrors.textContent = String(errors);
      }

      function renderLookupRows(rows) {
        state.lookupRows = rows || [];
        var html = '';
        var i;
        for (i = 0; i < state.lookupRows.length; i++) {
          var r = state.lookupRows[i];
          html += '<tr>' +
            '<td>' + escapeHtml(r.domain || '') + '</td>' +
            '<td>' + statusTag(r.status) + '</td>' +
            '<td>' + escapeHtml(r.zone_id || '') + '</td>' +
            '<td>' + escapeHtml(r.account_id || '') + '</td>' +
            '<td>' + escapeHtml(r.account_name || '') + '</td>' +
            '<td>' + escapeHtml(r.ns1 || '') + '</td>' +
            '<td>' + escapeHtml(r.ns2 || '') + '</td>' +
            '<td>' + escapeHtml(r.message || '') + '</td>' +
            '</tr>';
        }
        el.lookupTbody.innerHTML = html;

        var found = 0;
        var notFound = 0;
        var errors = 0;
        for (i = 0; i < state.lookupRows.length; i++) {
          if (state.lookupRows[i].status === 'found') found++;
          if (state.lookupRows[i].status === 'not_found') notFound++;
          if (state.lookupRows[i].status === 'error') errors++;
        }
        el.lookupKpiTotal.textContent = String(state.lookupRows.length);
        el.lookupKpiFound.textContent = String(found);
        el.lookupKpiNotFound.textContent = String(notFound);
        el.lookupKpiErrors.textContent = String(errors);
      }

      function rowsToTsv(rows) {
        var lines = ['domain\tstatus\tns1\tns2\tmessage'];
        var i;
        for (i = 0; i < rows.length; i++) {
          var r = rows[i];
          lines.push([
            r.domain || '',
            r.status || '',
            r.ns1 || '',
            r.ns2 || '',
            replaceAllSafe((r.message || ''), '\t', ' ')
          ].join('\t'));
        }
        return lines.join('\n');
      }

      function rowsToNsPairs(rows) {
        var lines = ['domain\tns1\tns2'];
        var i;
        for (i = 0; i < rows.length; i++) {
          var r = rows[i];
          if (!r.ns1 && !r.ns2) continue;
          lines.push([r.domain || '', r.ns1 || '', r.ns2 || ''].join('\t'));
        }
        return lines.join('\n');
      }

      function lookupRowsToTsv(rows) {
        var lines = ['domain\tstatus\tzone_id\taccount_id\taccount_name\tns1\tns2\tmessage'];
        var i;
        for (i = 0; i < rows.length; i++) {
          var r = rows[i];
          lines.push([
            r.domain || '',
            r.status || '',
            r.zone_id || '',
            r.account_id || '',
            r.account_name || '',
            r.ns1 || '',
            r.ns2 || '',
            replaceAllSafe((r.message || ''), '\t', ' ')
          ].join('\t'));
        }
        return lines.join('\n');
      }

      function lookupRowsToIdPairs(rows) {
        var lines = ['domain\tzone_id\taccount_id'];
        var i;
        for (i = 0; i < rows.length; i++) {
          var r = rows[i];
          if (!r.zone_id && !r.account_id) continue;
          lines.push([r.domain || '', r.zone_id || '', r.account_id || ''].join('\t'));
        }
        return lines.join('\n');
      }

      function copyText(text, successMessage, statusSetter) {
        if (!text || !String(text).trim()) {
          statusSetter('Немає даних для копіювання.');
          return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            statusSetter(successMessage);
          }).catch(function () {
            statusSetter('Не вдалося скопіювати автоматично.');
          });
          return;
        }

        var ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try {
          document.execCommand('copy');
          statusSetter(successMessage);
        } catch (e) {
          statusSetter('Не вдалося скопіювати автоматично.');
        }
        document.body.removeChild(ta);
      }

      function toCsv(rows, headers, fields) {
        var lines = [headers.join(',')];
        var i;
        var j;
        for (i = 0; i < rows.length; i++) {
          var out = [];
          for (j = 0; j < fields.length; j++) {
            var key = fields[j];
            var value = rows[i][key] || '';
            var safe = replaceAllSafe(String(value), '"', '""');
            out.push('"' + safe + '"');
          }
          lines.push(out.join(','));
        }
        return lines.join('\n');
      }

      function downloadCsv(csvContent, filename, statusSetter) {
        if (!csvContent || !String(csvContent).trim()) {
          statusSetter('Немає даних для CSV.');
          return;
        }
        var blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        statusSetter('CSV збережено.');
      }

      function postJson(url, payload, onDone) {
        var xhr = new XMLHttpRequest();
        xhr.open('POST', url, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onreadystatechange = function () {
          if (xhr.readyState !== 4) return;
          var data = {};
          try {
            data = JSON.parse(xhr.responseText || '{}');
          } catch (e) {
            onDone(new Error('Invalid JSON response'), null);
            return;
          }
          if (xhr.status < 200 || xhr.status >= 300 || !data.ok) {
            onDone(new Error(data.error || ('HTTP ' + xhr.status)), data);
            return;
          }
          onDone(null, data);
        };
        xhr.onerror = function () {
          onDone(new Error('Network error'), null);
        };
        xhr.send(JSON.stringify(payload));
      }

      function runImport() {
        var token = (el.token.value || '').trim();
        var domainsText = el.domains.value || '';
        var accountId = (el.accountId.value || '').trim();
        var delay = parseFloat(el.delay.value || '0.2');
        if (isNaN(delay) || delay < 0) delay = 0;
        if (delay > 5) delay = 5;

        if (!token) {
          setStatus('Додай API токен.');
          return;
        }
        if (!domainsText.trim()) {
          setStatus('Встав список доменів.');
          return;
        }

        el.runBtn.disabled = true;
        setStatus('Обробляю домени, зачекай...');

        postJson('/api/run', {
          token: token,
          domains_text: domainsText,
          account_id: accountId || null,
          delay: delay
        }, function (err, data) {
          el.runBtn.disabled = false;
          if (err) {
            setStatus('Помилка: ' + err.message);
            return;
          }
          renderRows(data.rows || []);
          var sum = data.summary || {};
          var text = 'Готово. Всього: ' + (sum.total || 0) +
            ', created: ' + (sum.created || 0) +
            ', existing: ' + (sum.existing || 0) +
            ', errors: ' + (sum.errors || 0);
          if (data.account_id_used) {
            text += '. account_id: ' + data.account_id_used;
          }
          setStatus(text);
        });
      }

      function runLookup() {
        var token = (el.lookupToken.value || '').trim();
        var domainsText = el.lookupDomains.value || '';
        var delay = parseFloat(el.lookupDelay.value || '0.2');
        if (isNaN(delay) || delay < 0) delay = 0;
        if (delay > 5) delay = 5;

        if (!token) {
          setLookupStatus('Додай API токен.');
          return;
        }
        if (!domainsText.trim()) {
          setLookupStatus('Встав список доменів.');
          return;
        }

        el.lookupRunBtn.disabled = true;
        setLookupStatus('Шукаю zone_id/account_id, зачекай...');

        postJson('/api/lookup-ids', {
          token: token,
          domains_text: domainsText,
          delay: delay
        }, function (err, data) {
          el.lookupRunBtn.disabled = false;
          if (err) {
            setLookupStatus('Помилка: ' + err.message);
            return;
          }
          renderLookupRows(data.rows || []);
          var sum = data.summary || {};
          setLookupStatus(
            'Готово. Всього: ' + (sum.total || 0) +
            ', found: ' + (sum.found || 0) +
            ', not_found: ' + (sum.not_found || 0) +
            ', errors: ' + (sum.errors || 0)
          );
        });
      }

      function switchTab(targetId) {
        var i;
        for (i = 0; i < el.tabButtons.length; i++) {
          var b = el.tabButtons[i];
          if (b.getAttribute('data-tab') === targetId) {
            b.classList.add('active');
          } else {
            b.classList.remove('active');
          }
        }
        for (i = 0; i < el.tabContents.length; i++) {
          var c = el.tabContents[i];
          if (c.id === targetId) {
            c.classList.add('active');
          } else {
            c.classList.remove('active');
          }
        }
      }

      var i;
      for (i = 0; i < el.tabButtons.length; i++) {
        (function (btn) {
          btn.addEventListener('click', function () {
            switchTab(btn.getAttribute('data-tab'));
          });
        })(el.tabButtons[i]);
      }

      el.runBtn.addEventListener('click', runImport);
      el.lookupRunBtn.addEventListener('click', runLookup);

      el.copyTsvBtn.addEventListener('click', function () {
        copyText(rowsToTsv(state.rows), 'Таблицю скопійовано (TSV).', setStatus);
      });
      el.copyNsBtn.addEventListener('click', function () {
        copyText(rowsToNsPairs(state.rows), 'Domain + NS скопійовано.', setStatus);
      });
      el.lookupCopyTsvBtn.addEventListener('click', function () {
        copyText(lookupRowsToTsv(state.lookupRows), 'Lookup-таблицю скопійовано (TSV).', setLookupStatus);
      });
      el.lookupCopyIdsBtn.addEventListener('click', function () {
        copyText(lookupRowsToIdPairs(state.lookupRows), 'Domain + IDs скопійовано.', setLookupStatus);
      });

      el.downloadCsvBtn.addEventListener('click', function () {
        var csv = toCsv(state.rows, ['domain', 'status', 'ns1', 'ns2', 'message'], ['domain', 'status', 'ns1', 'ns2', 'message']);
        downloadCsv(csv, 'cloudflare_ns_results_ui.csv', setStatus);
      });
      el.lookupDownloadCsvBtn.addEventListener('click', function () {
        var csv = toCsv(
          state.lookupRows,
          ['domain', 'status', 'zone_id', 'account_id', 'account_name', 'ns1', 'ns2', 'message'],
          ['domain', 'status', 'zone_id', 'account_id', 'account_name', 'ns1', 'ns2', 'message']
        );
        downloadCsv(csv, 'cloudflare_zone_account_lookup.csv', setLookupStatus);
      });

      if (!el.lookupToken.value.trim()) {
        el.lookupToken.value = el.token.value || '';
      }
    })();
  </script>
</body>
</html>
"""


def parse_domains_from_text(raw: str) -> list[str]:
    seen: set[str] = set()
    domains: list[str] = []

    for line in raw.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue

        for part in clean.replace(";", ",").split(","):
            domain = part.strip().lower().rstrip(".")
            if not domain:
                continue
            if domain in seen:
                continue
            seen.add(domain)
            domains.append(domain)

    return domains


def run_bulk_import(token: str, domains_text: str, account_id: str | None, delay: float) -> dict[str, Any]:
    domains = parse_domains_from_text(domains_text)
    if not domains:
        return {"ok": False, "error": "No domains provided"}

    ssl_context = cf.build_ssl_context(False, None)

    account_id_used = account_id
    if not account_id_used:
        account_id_used = cf.get_first_account_id(token, ssl_context)

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

    summary = {
        "total": len(rows),
        "created": sum(1 for r in rows if r["status"] == "created"),
        "existing": sum(1 for r in rows if r["status"] == "existing"),
        "errors": sum(1 for r in rows if r["status"] == "error"),
    }

    return {
        "ok": True,
        "rows": rows,
        "summary": summary,
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
                name_servers = zone.get("name_servers") or []
                account_obj = zone.get("account") or {}
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

    summary = {
        "total": len(rows),
        "found": sum(1 for r in rows if r["status"] == "found"),
        "not_found": sum(1 for r in rows if r["status"] == "not_found"),
        "errors": sum(1 for r in rows if r["status"] == "error"),
    }

    return {
        "ok": True,
        "rows": rows,
        "summary": summary,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default access logs
        return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(HTML)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/api/run", "/api/lookup-ids"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json({"ok": False, "error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return

        token = str(data.get("token") or "").strip()
        domains_text = str(data.get("domains_text") or "")
        account_id_raw = data.get("account_id")
        account_id = str(account_id_raw).strip() if account_id_raw else None

        try:
            delay = float(data.get("delay", 0.2))
        except (TypeError, ValueError):
            delay = 0.2

        if delay < 0:
            delay = 0.0
        if delay > 5:
            delay = 5.0

        if not token:
            self._send_json({"ok": False, "error": "API token is required"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            if self.path == "/api/run":
                result = run_bulk_import(token, domains_text, account_id, delay)
            else:
                result = run_lookup_ids(token, domains_text, delay)
        except cf.CloudflareAPIError as e:
            self._send_json({"ok": False, "error": str(e)}, status=HTTPStatus.BAD_GATEWAY)
            return
        except Exception as e:
            self._send_json({"ok": False, "error": f"Unexpected error: {e}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        status_code = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        self._send_json(result, status=status_code)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Open http://{HOST}:{PORT} in your browser")
    server.serve_forever()


if __name__ == "__main__":
    main()
