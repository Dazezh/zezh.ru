from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterable


class DBError(Exception):
    """Базовая ошибка слоя БД."""


class DBQueryNotFoundError(DBError):
    """Запрос не найден в sql_queries.json."""


class DBOperationError(DBError):
    """Операция с БД не удалась после всех попыток."""


class mysql_db:
    """
    Мини-слой доступа к MySQL для WatchPoint.

    Да, имя класса оставлено старым специально. Переименовать в MysqlDB красиво,
    но потом половина приложения начинает орать, а мы вроде не устраиваем пожарную тревогу.
    """

    def __init__(self, config: dict, logger) -> None:
        global pymysql
        import pymysql

        self.config = config['db_config']
        self.system_config = config
        self.logger = logger

        self.sql_queries_file = config.get("SQL_QUERIES_FILE", "sql_queries.json")
        self.create_db_file = config.get("SQL_CREATE_FILE", "create_bd.sql")
        self.config_file = config.get("CONFIG_FILE", "config.json")

        self.retry_count = int(config.get("MYSQL_RETRY_COUNT", 4))
        self.retry_delay = float(config.get("MYSQL_RETRY_DELAY", 0.5))

        with open(self.sql_queries_file, encoding="utf8") as file:
            self.sql_queries = json.load(file)["mysql"]

        if not config.get("sql_install"):
            self._install_schema()
            self.config["sql_install"] = True
            self._save_config()

    # ---------------------------------------------------------------------
    # Connection management
    # ---------------------------------------------------------------------

    def _connect_kwargs(self) -> dict[str, Any]:
        """Параметры подключения. Одно место, где собирается connect()."""
        kwargs = {
            "host": self.config.get("MYSQL_HOST"),
            "user": self.config.get("MYSQL_USER"),
            "password": self.config.get("MYSQL_PASSWORD"),
            "db": self.config.get("MYSQL_DB"),
            "charset": self.config.get("MYSQL_CHARSET", "utf8mb4"),
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": int(self.config.get("MYSQL_CONNECT_TIMEOUT", 5)),
            "read_timeout": int(self.config.get("MYSQL_READ_TIMEOUT", 30)),
            "write_timeout": int(self.config.get("MYSQL_WRITE_TIMEOUT", 30)),
        }

        port = self.config.get("MYSQL_PORT")
        if port:
            kwargs["port"] = int(port)

        return kwargs

    @contextmanager
    def _connection(self, *, autocommit: bool):
        """
        Короткоживущее соединение на одну операцию.

        В старой версии соединение висело в self.db и пыталось воскресать через __reconnect().
        Для 24/7 сервиса это превращается в болото из полумёртвых TCP-сессий.
        Здесь соединение открывается, используется и закрывается.
        """
        conn = pymysql.connect(autocommit=autocommit, **self._connect_kwargs())
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                # Закрытие соединения не должно ломать основной сценарий.
                pass

    def _save_config(self) -> None:
        with open(self.config_file, "w", encoding="utf8") as file:
            self.system_config["db_config"] = self.config
            json.dump(self.system_config, file, ensure_ascii=False, indent=2)

    def _install_schema(self) -> None:
        """Первичная установка схемы. Поведение сохранено, но без вечного self.db."""
        with open(self.create_db_file, encoding="utf8") as file:
            create_db_query = file.read()

        def op() -> bool:
            with self._connection(autocommit=False) as conn:
                with conn.cursor() as cursor:
                    self._execute_multi(cursor, create_db_query)
                conn.commit()
            return True

        self._run_with_retry(
            op,
            message="База данных дала сбой при первичной установке схемы",
            event="db_schema_install_failed",
        )

    # ---------------------------------------------------------------------
    # SQL registry and execution
    # ---------------------------------------------------------------------

    def _get_sql(self, querie: str) -> str:
        """
        Получает SQL по имени из sql_queries.json.

        Параметр называется querie намеренно: сохранена совместимость с существующим кодом.
        Да, английский тихо плачет в углу, но менять публичный интерфейс сейчас дороже.
        """
        try:
            return self.sql_queries[querie]
        except KeyError as ex:
            self.logger.error(
                "Некорректный запрос к базе данных",
                extra={
                    "component": "core",
                    "category": "db",
                    "event": "db_query_not_found",
                    "details": {"query": str(querie)},
                },
            )
            raise DBQueryNotFoundError(f"SQL query not found: {querie}") from ex

    def _execute_multi(self, cursor, sql: str, args: tuple = ()):  # noqa: ANN001
        """
        Выполняет SQL-строку, которая может содержать несколько инструкций через ';'.

        Поведение в целом сохранено:
        - один запрос выполняется как есть;
        - несколько запросов делятся по ';';
        - параметры распределяются по числу %s в каждой инструкции.

        Это не полноценный SQL parser. И слава богу, иначе мы бы тут писали MySQL,
        а не WatchPoint. Для твоего query registry этого достаточно.
        """
        non_empty_parts = [p for p in sql.split(";") if p.strip()]
        if len(non_empty_parts) < 2:
            if args:
                return cursor.execute(sql, args)
            return cursor.execute(sql)

        parts = [p.strip() for p in sql.split(";") if p.strip()]
        args = tuple(args) if args else ()

        placeholders_total = sum(p.count("%s") for p in parts)
        if placeholders_total != len(args) and placeholders_total != 0 and len(args) != 0:
            raise ValueError(
                f"Количество параметров ({len(args)}) не соответствует количеству "
                f"плейсхолдеров ({placeholders_total}) в многозапросе"
            )

        arg_index = 0
        last_result = None
        for part in parts:
            count = part.count("%s")
            if count == 0:
                last_result = cursor.execute(part)
            else:
                slice_args = args[arg_index : arg_index + count]
                last_result = cursor.execute(part, slice_args)
                arg_index += count

        return last_result

    def _run_with_retry(
        self,
        operation: Callable[[], Any],
        *,
        message: str,
        event: str,
        details: dict[str, Any] | None = None,
    ) -> Any:
        """
        Общая retry-обёртка.

        Сохраняет твою старую идею: DB-класс сам пытается пережить сбой.
        Отличие: больше нет self.db и переподключения. Каждая попытка сама открывает
        новое короткоживущее соединение.
        """
        details = details or {}
        last_error: Exception | None = None

        for attempt in range(1, self.retry_count + 1):
            try:
                return operation()
            except DBQueryNotFoundError:
                # Повторять бессмысленно: если запроса нет в JSON, он не появится через 0.5 секунды.
                raise
            except Exception as ex:  # намеренно широко: старое поведение тоже ретраило почти всё
                last_error = ex
                log_details = dict(details)
                log_details.update({"error": str(ex), "attempt": attempt, "retry_count": self.retry_count})

                self.logger.error(
                    message,
                    extra={
                        "component": "core",
                        "category": "db",
                        "event": event,
                        "details": log_details,
                    },
                )

                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)

        raise DBOperationError(str(last_error) if last_error else "Unknown database error")

    # ---------------------------------------------------------------------
    # New clean API
    # ---------------------------------------------------------------------

    def fetch_all(self, querie: str, *args) -> list[dict[str, Any]]:
        """
        Новый чистый метод для SELECT.

        Контракт:
        - данные найдены -> list[dict]
        - данных нет -> []
        - ошибка -> исключение DBError
        """
        sql = self._get_sql(querie)

        def op() -> list[dict[str, Any]]:
            with self._connection(autocommit=True) as conn:
                with conn.cursor() as cursor:
                    self._execute_multi(cursor, sql, args)
                    rows = cursor.fetchall()
                    return list(rows) if rows else []

        return self._run_with_retry(
            op,
            message="База данных дала сбой при обычном запросе",
            event="db_select_failed",
            details={"query": querie},
        )

    def fetch_page(self, page_number: int, querie: str, items_per_page: int = 10) -> list[dict[str, Any]]:
        """
        Новый чистый метод для постраничного SELECT.

        Контракт такой же, как у fetch_all.
        """
        if page_number < 1:
            page_number = 1
        if items_per_page < 1:
            items_per_page = 10

        offset = (page_number - 1) * items_per_page
        sql = self._get_sql(querie)

        def op() -> list[dict[str, Any]]:
            with self._connection(autocommit=True) as conn:
                with conn.cursor() as cursor:
                    self._execute_multi(cursor, sql, (items_per_page, offset))
                    rows = cursor.fetchall()
                    return list(rows) if rows else []

        return self._run_with_retry(
            op,
            message="База данных дала сбой при постраничном запросе",
            event="db_paginated_select_failed",
            details={"query": querie, "page_number": page_number, "items_per_page": items_per_page},
        )

    def execute_write(self, querie: str, *args, return_id: bool | None = None) -> int | bool | None:
        """
        Новый чистый метод для INSERT/UPDATE/DELETE/DDL.

        Контракт:
        - INSERT по умолчанию возвращает lastrowid;
        - UPDATE/DELETE/DDL по умолчанию возвращают True;
        - ошибка -> исключение DBError.

        return_id можно задать явно, если SQL начинается не с INSERT, но ID всё равно нужен.
        """
        sql = self._get_sql(querie)
        sql_stripped = sql.lstrip().lower()
        if return_id is None:
            return_id = sql_stripped.startswith("insert")

        def op() -> int | bool | None:
            with self._connection(autocommit=False) as conn:
                try:
                    with conn.cursor() as cursor:
                        self._execute_multi(cursor, sql, args)
                        lastrowid = getattr(cursor, "lastrowid", None)
                    conn.commit()
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise

            if return_id:
                return lastrowid
            return True

        return self._run_with_retry(
            op,
            message="База данных дала сбой при сохранении данных",
            event="db_write_failed",
            details={"query": querie},
        )