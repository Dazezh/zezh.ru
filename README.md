# ZEZH.RU

![site](https://github.com/Dazezh/zezh.ru/raw/main/image/site.png)

ZEZH.RU is the simplest possible link shortener: paste a long URL, get a short code, share it. It also supports custom codes, multi-links, click counters, info pages, and QR codes.

The project is intentionally small and direct. Flask handles routing, Jinja renders pages, `sql_queries.json` keeps SQL out of Python code, and `db.py` provides a tiny MySQL access layer with short-lived connections and retries.

## Features

- Single short links with generated or custom codes.
- Multi-links: one short URL that opens a list of destinations.
- `+info` pages for checking where a short link leads.
- Click counting for ordinary short links.
- QR code generation for every resulting link.
- Minimal responsive interface with automatic light and dark theme.

## Project Structure

```text
.
├── short.py              # Flask application and business logic
├── db.py                 # Mini ORM / database layer
├── config.json           # Local runtime configuration
├── config.example.json   # Safe configuration template
├── db_init.sql           # Database bootstrap SQL
├── sql_queries.json      # Named SQL query registry
├── templates/            # Jinja templates
└── static/               # CSS, JS, logos
```

## Configuration

Create `config.json` from `config.example.json` and fill in your MySQL credentials.

```json
{
  "db_config": {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_USER": "shortener_user",
    "MYSQL_PASSWORD": "change-me",
    "MYSQL_DB": "shortener"
  },
  "SQL_QUERIES_FILE": "sql_queries.json",
  "SQL_CREATE_FILE": "db_init.sql",
  "CONFIG_FILE": "config.json",
  "MYSQL_RETRY_COUNT": 4,
  "MYSQL_RETRY_DELAY": 0.5,
  "sql_install": false
}
```

When `sql_install` is `false`, the database layer runs `db_init.sql` once, then writes the updated state back to `config.json`.

## Run

Install the Python dependencies, prepare MySQL, then start the app:

```bash
pip install -r requirements.txt
python short.py
```

By default Flask starts at:

```text
http://127.0.0.1:5000
```

## Notes

This is a small service by design. There are no background workers, admin panels, or heavy frameworks. The useful parts are plain: routes, templates, named SQL, and a compact DB layer.

## Branding & Licensing

* Licensing: Source code is licensed under GPL-3.0-or-later. Branding, logos, illustrations, mascots and other visual identity assets are protected by copyright and are not covered by the GPL. For more details, see the [COPYRIGHT.md](COPYRIGHT.md) file.
