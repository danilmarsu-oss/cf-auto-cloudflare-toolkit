# Cloudflare bulk zone add + NS export

Скрипт масово додає домени в Cloudflare через API (`POST /zones`) і повертає NS (`result.name_servers`) для кожного домену.

## 1) Підготуй список доменів

Створи файл `domains.txt` (1 домен на рядок). Також підтримуються рядки через кому або `;`.

Приклад:

```txt
example.com
example.net
foo.org, bar.io
```

## 2) Токен Cloudflare

Потрібен API token з правами:

- `Zone:Edit` (або `Zone DNS:Edit`)
- право створювати зони (permission `com.cloudflare.api.account.zone.create`)

Експортуй токен:

```bash
export CLOUDFLARE_API_TOKEN='твій_токен'
```

## 3) Запуск

```bash
python3 cf_bulk_add_zones.py --domains-file domains.txt
```

Опційно, якщо треба явно вказати акаунт:

```bash
python3 cf_bulk_add_zones.py --domains-file domains.txt --account-id <CLOUDFLARE_ACCOUNT_ID>
```

Якщо в системі є проблеми з TLS-сертифікатами, можна вказати свій CA bundle:

```bash
python3 cf_bulk_add_zones.py --domains-file domains.txt --ca-bundle /path/to/cacert.pem
```

Або (лише як аварійний варіант) вимкнути перевірку TLS:

```bash
python3 cf_bulk_add_zones.py --domains-file domains.txt --insecure
```

## 4) Результат

Скрипт створює:

- `cloudflare_ns_results.csv`
- `cloudflare_ns_results.json`

У файлах буде мапа:

- `domain`
- `status` (`created` / `existing` / `error`)
- `ns1`, `ns2`
- `message`

## Web інтерфейс (зручний режим)

Запуск:

```bash
python3 web_ui.py
```

Відкрий у браузері:

```txt
http://127.0.0.1:8787
```

Що вміє:

- вкладка `1) Add Domains + NS`:
  - вставити список доменів у textarea
  - вказати API токен (і опційно `account_id`)
  - отримати таблицю `domain / status / ns1 / ns2 / message`
  - скопіювати результат як TSV
  - скопіювати тільки `domain + ns1 + ns2`
  - завантажити CSV
- вкладка `2) Lookup Zone/Account IDs`:
  - вставити список доменів
  - отримати `zone_id` та `account_id` для кожного домену
  - таблиця: `domain / status / zone_id / account_id / account_name / ns1 / ns2 / message`
  - окрема кнопка копіювання `domain + zone_id + account_id`

## Streamlit інтерфейс

Встановлення залежностей:

```bash
pip install -r requirements.txt
```

Запуск:

```bash
streamlit run streamlit_app.py
```

Вкладки такі самі:

- `1) Add Domains + NS`
- `2) Lookup Zone/Account IDs`
