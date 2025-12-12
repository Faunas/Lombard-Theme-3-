# clients_rep_db.py
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, TypedDict

import psycopg2
from psycopg2 import errorcodes

from client import Client
from client_short import ClientShort
from db_singleton import PgDB


class ImportSummary(TypedDict):
    total: int
    inserted: int
    skipped_conflict: int
    invalid: int
    errors: list[dict[str, Any]]


class ClientsRepDB:
    """
    Класс для работы с клиентами через PostgreSQL (делегирует SQL в PgDB).
    """

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "lucky_db",
        user: str = "postgres",
        password: str = "123",
        auto_migrate: bool = True,
    ) -> None:
        PgDB.init(host=host, port=port, dbname=dbname, user=user, password=password)
        if auto_migrate:
            self.ensure_schema()

    def connect(self):
        # Делегируем создание соединения Singleton'у
        return PgDB.get().connect()

    def ensure_schema(self) -> None:
        """
        Создаёт таблицу и индексы, если их ещё нет.
        """
        ddl_table = """
        CREATE TABLE IF NOT EXISTS clients (
            id               BIGSERIAL PRIMARY KEY,
            last_name        TEXT    NOT NULL,
            first_name       TEXT    NOT NULL,
            middle_name      TEXT    NOT NULL,
            passport_series  CHAR(4) NOT NULL
                CHECK (passport_series ~ '^[0-9]{4}$'),
            passport_number  CHAR(6) NOT NULL
                CHECK (passport_number ~ '^[0-9]{6}$'),
            birth_date       DATE    NOT NULL,
            phone            TEXT    NOT NULL,
            email            TEXT    NOT NULL,
            address          TEXT    NOT NULL,
            CONSTRAINT uq_passport
                UNIQUE (passport_series, passport_number)
        );
        """
        ddl_index_last_name = (
            "CREATE INDEX IF NOT EXISTS idx_clients_last_name " "ON clients(last_name);"
        )

        db = PgDB.get()
        db.execute(ddl_table)
        db.execute(ddl_index_last_name)

    # -------------------- утилиты конвертации дат/строк --------------------

    @staticmethod
    def _date_to_dd_mm_yyyy(d: date | None) -> str | None:
        return d.strftime("%d-%m-%Y") if d else None

    @staticmethod
    def _dd_mm_yyyy_to_date(s: str) -> date:
        return datetime.strptime(s, "%d-%m-%Y").date()

    @staticmethod
    def _row_to_client_payload(row: dict[str, Any]) -> dict[str, Any]:
        """
        Преобразуем строку БД (dict) в payload для Client().
        """
        return {
            "id": row["id"],
            "last_name": row["last_name"],
            "first_name": row["first_name"],
            "middle_name": row["middle_name"],
            "passport_series": (row["passport_series"] or "").strip(),
            "passport_number": (row["passport_number"] or "").strip(),
            "birth_date": ClientsRepDB._date_to_dd_mm_yyyy(row["birth_date"]),
            "phone": row["phone"],
            "email": row["email"],
            "address": row["address"],
        }

    # ------------------------------- 4(a) get_by_id -------------------------------

    def get_by_id(
        self,
        target_id: int,
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        """
        Возвращает (Client | None, errors) по id из PostgreSQL.
        Ошибки формата (как в файловых репозиториях):
          - NotFound — если записи нет
          - ValidationError — если поля не проходят валидацию Client(...)
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: list[dict[str, Any]] = []
        db = PgDB.get()

        sql = """
        SELECT
            id,
            last_name,
            first_name,
            middle_name,
            passport_series,
            passport_number,
            birth_date,
            phone,
            email,
            address
        FROM clients
        WHERE id = %s;
        """
        try:
            row = db.fetch_one(sql, (target_id,))
        except psycopg2.Error:
            # пробрасываем дальше реальную ошибку psycopg2
            raise

        if row is None:
            errors.append(
                {
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": f"Клиент с id={target_id} не найден",
                }
            )
            return None, errors

        payload = self._row_to_client_payload(row)
        try:
            return Client(payload), errors
        except Exception as exc:
            errors.append(
                {
                    "id": target_id,
                    "error_type": type(exc).__name__,
                    "message": f"Данные в БД невалидны: {str(exc)}",
                }
            )
            return None, errors

    # ------------------------ 4(b) пагинация ClientShort ------------------------

    def get_k_n_short_list(
        self,
        k: int,
        n: int,
        *,
        prefer_contact: str = "phone",
    ) -> list[ClientShort]:
        """
        Возвращает страницу k (нумерация с 1) размером n в виде ClientShort.
        Порядок фиксированный: ORDER BY id ASC.
        """
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k и n должны быть положительными целыми числами")

        offset = (k - 1) * n
        db = PgDB.get()

        sql = """
        SELECT
            id,
            last_name,
            first_name,
            middle_name,
            passport_series,
            passport_number,
            birth_date,
            phone,
            email
        FROM clients
        ORDER BY id ASC
        LIMIT %s OFFSET %s;
        """
        rows = db.fetch_all(sql, (n, offset))

        result: list[ClientShort] = []
        for r in rows:
            payload = {
                "id": r["id"],
                "last_name": r["last_name"],
                "first_name": r["first_name"],
                "middle_name": r["middle_name"],
                "passport_series": (r["passport_series"] or "").strip(),
                "passport_number": (r["passport_number"] or "").strip(),
                "birth_date": self._date_to_dd_mm_yyyy(r["birth_date"]),
                "phone": r["phone"],
                "email": r["email"],
            }
            result.append(ClientShort(payload, prefer_contact=prefer_contact))
        return result

    # ----------------------------- 4(c) вставка клиента -----------------------------

    def add_client(self, data: Client | dict[str, Any] | str) -> Client:
        """
        Вставляет клиента в БД, ID генерируется.
        Возвращает объект Client с присвоенным id.
        Защищено уникальным ключом (серия+номер паспорта).
        """
        if isinstance(data, Client):
            c = data
        elif isinstance(data, (dict, str)):
            c = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str")

        bd = self._dd_mm_yyyy_to_date(c.birth_date)
        db = PgDB.get()

        sql = """
        INSERT INTO clients
            (last_name, first_name, middle_name,
             passport_series, passport_number,
             birth_date, phone, email, address)
        VALUES
            (%s, %s, %s,
             %s, %s,
             %s, %s, %s, %s)
        RETURNING id;
        """
        params = (
            c.last_name,
            c.first_name,
            c.middle_name,
            c.passport_series,
            c.passport_number,
            bd,
            c.phone,
            c.email,
            c.address,
        )

        try:
            row = db.execute_returning(sql, params)
        except psycopg2.IntegrityError as exc:
            if getattr(exc, "pgcode", None) == errorcodes.UNIQUE_VIOLATION:
                raise ValueError(
                    "DuplicateClient: клиент с таким паспортом уже существует"
                ) from exc
            raise

        if not row or "id" not in row:
            raise RuntimeError("INSERT вернул пустой результат (RETURNING id).")

        c.id = row["id"]
        return c

    # ----------------------------- 4(d) обновление по id -----------------------------

    def replace_by_id(self, target_id: int, data: Client | dict[str, Any] | str) -> Client:
        """
        Обновляет запись по id в PostgreSQL.
          - запись с id должна существовать (иначе NotFound);
          - защита от дубля по паспорту (уникальный ключ).
        Возвращает обновлённый Client (c id=target_id).
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        if isinstance(data, Client):
            c = data
        elif isinstance(data, (dict, str)):
            c = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str")

        if c.id is not None and c.id != target_id:
            raise ValueError(f"Несоответствие ID: payload id={c.id} != target id={target_id}")

        bd = self._dd_mm_yyyy_to_date(c.birth_date)
        db = PgDB.get()

        sql = """
        UPDATE clients
        SET
            last_name       = %s,
            first_name      = %s,
            middle_name     = %s,
            passport_series = %s,
            passport_number = %s,
            birth_date      = %s,
            phone           = %s,
            email           = %s,
            address         = %s
        WHERE id = %s
        RETURNING id;
        """
        params = (
            c.last_name,
            c.first_name,
            c.middle_name,
            c.passport_series,
            c.passport_number,
            bd,
            c.phone,
            c.email,
            c.address,
            target_id,
        )

        try:
            row = db.execute_returning(sql, params)
        except psycopg2.IntegrityError as exc:
            if getattr(exc, "pgcode", None) == errorcodes.UNIQUE_VIOLATION:
                raise ValueError(
                    "DuplicateClient: клиент с таким паспортом уже существует"
                ) from exc
            raise

        if not row:
            # либо UPDATE не затронул строк, либо RETURNING ничего не вернул
            raise ValueError(f"NotFound: Клиент с id={target_id} не найден")

        c.id = target_id
        return c

    # ------------------------------ 4(e) удаление по id ------------------------------

    def delete_by_id(
        self,
        target_id: int,
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        """
        Удаляет запись по id и возвращает (удалённый Client | None, errors).
        Ошибки:
          - NotFound: если записи нет
          - Если данные строки невалидны: "Удалено, но запись невалидна"
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: list[dict[str, Any]] = []
        db = PgDB.get()

        select_sql = """
        SELECT
            id,
            last_name,
            first_name,
            middle_name,
            passport_series,
            passport_number,
            birth_date,
            phone,
            email,
            address
        FROM clients
        WHERE id = %s;
        """
        delete_sql = "DELETE FROM clients WHERE id = %s;"

        row = db.fetch_one(select_sql, (target_id,))
        if row is None:
            errors.append(
                {
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": f"Клиент с id={target_id} не найден",
                }
            )
            return None, errors

        db.execute(delete_sql, (target_id,))

        try:
            payload = self._row_to_client_payload(row)
            return Client(payload), errors
        except Exception as exc:
            errors.append(
                {
                    "id": target_id,
                    "error_type": type(exc).__name__,
                    "message": f"Удалено, но запись невалидна: {str(exc)}",
                }
            )
            return None, errors

    # ------------------------------ 4(f) get_count ------------------------------

    def get_count(self) -> int:
        """
        Возвращает общее количество записей в таблице clients.
        """
        db = PgDB.get()
        row = db.fetch_one("SELECT COUNT(*) AS cnt FROM clients;")
        return int(row["cnt"]) if row and "cnt" in row else 0

    # ---------------------- массовая загрузка из clean.json ----------------------

    def import_from_clean_json(
        self,
        json_path: str = "clients_clean.json",
        *,
        replace: bool = True,
        preserve_ids: bool = True,
    ) -> ImportSummary:
        """
        Импортирует клиентов из JSON-файла.
        - replace=True: перед импортом очищает таблицу.
        - preserve_ids=True: пытается сохранить id из файла; при конфликтах — пропускает.
        Возвращает сводку: {total, inserted, skipped_conflict, invalid, errors}
        """
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("clean JSON должен быть массивом объектов")

        summary: ImportSummary = {
            "total": len(data),
            "inserted": 0,
            "skipped_conflict": 0,
            "invalid": 0,
            "errors": [],
        }

        db = PgDB.get()
        if replace:
            db.execute("TRUNCATE TABLE clients RESTART IDENTITY;")

        for i, rec in enumerate(data):
            try:
                c = Client(rec)
            except Exception as exc:
                summary["invalid"] += 1
                summary["errors"].append({"index": i, "error": f"Invalid payload: {exc}"})
                continue

            bd = self._dd_mm_yyyy_to_date(c.birth_date)
            vals_common = (
                c.last_name,
                c.first_name,
                c.middle_name,
                c.passport_series,
                c.passport_number,
                bd,
                c.phone,
                c.email,
                c.address,
            )

            if preserve_ids and c.id is not None:
                sql = """
                INSERT INTO clients
                    (id, last_name, first_name, middle_name,
                     passport_series, passport_number,
                     birth_date, phone, email, address)
                VALUES
                    (%s, %s, %s, %s,
                     %s, %s,
                     %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """
                params = (c.id,) + vals_common
            else:
                sql = """
                INSERT INTO clients
                    (last_name, first_name, middle_name,
                     passport_series, passport_number,
                     birth_date, phone, email, address)
                VALUES
                    (%s, %s, %s,
                     %s, %s,
                     %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """
                params = vals_common

            row = db.execute_returning(sql, params)
            if row and row.get("id") is not None:
                summary["inserted"] += 1
            else:
                summary["skipped_conflict"] += 1

        seqname_row = db.fetch_one("SELECT pg_get_serial_sequence('clients', 'id') AS seqname;")
        seqname = seqname_row["seqname"] if seqname_row else None
        if seqname:
            max_id_row = db.fetch_one("SELECT COALESCE(MAX(id), 0) AS mx FROM clients;")
            max_id = int(max_id_row["mx"]) if max_id_row and "mx" in max_id_row else 0
            db.execute(f"SELECT setval('{seqname}', %s)", (max_id,))

        return summary


if __name__ == "__main__":
    # Инициализация Singleton и репозитория (делегация всех SQL в PgDB)
    repo = ClientsRepDB(
        host="127.0.0.1",
        port=5432,
        dbname="lucky_db",
        user="postgres",
        password="123",
        auto_migrate=True,
    )

    print("Импорт из clients_clean.json ...")
    summary = repo.import_from_clean_json(
        "clients_clean.json",
        replace=True,
        preserve_ids=True,
    )
    print(
        "✓ Импорт завершён: "
        f"total={summary['total']}, "
        f"inserted={summary['inserted']}, "
        f"skipped={summary['skipped_conflict']}, "
        f"invalid={summary['invalid']}"
    )
    if summary["errors"]:
        print("Ошибки валидации при импорте:")
        for err in summary["errors"][:5]:
            print("-", err)

    # Берём минимальный id для показа get_by_id (если таблица не пуста)
    db = PgDB.get()
    row = db.fetch_one("SELECT MIN(id) AS min_id FROM clients;")
    min_id = row["min_id"] if row and "min_id" in row else None

    if min_id is not None:
        client_obj, errs = repo.get_by_id(int(min_id))
        if client_obj:
            print("\n✓ Найден клиент (минимальный id):")
            print(client_obj.to_full_string())
        if errs:
            print("\nЗамечания/ошибки:")
            for err in errs:
                msg = f"- id={err.get('id')}: {err['error_type']}: {err['message']}"
                print(msg)

        # Пагинация: первые 2 страницы по 3 элемента
        print("\nСтраница 1 (по 3 элемента):")
        for s in repo.get_k_n_short_list(1, 3, prefer_contact="phone"):
            print("-", s)

        print("\nСтраница 2 (по 3 элемента):")
        for s in repo.get_k_n_short_list(2, 3, prefer_contact="email"):
            print("-", s)

        # c) Добавление нового клиента
        print("\nДобавляем нового клиента...")
        try:
            added = repo.add_client(
                {
                    "last_name": "Троевой",
                    "first_name": "Антон",
                    "middle_name": "Игоревич",
                    "passport_series": "1234",
                    "passport_number": "999000",
                    "birth_date": "15-03-1993",
                    "phone": "+79990001234",
                    "email": "anton.polevoy@example.com",
                    "address": "г. Казань, ул. Баумана, д. 5",
                }
            )
            print(f"✓ Добавлен: id={added.id} — {added}")
        except ValueError as exc:
            print(f"✗ Не удалось добавить: {exc}")

        # d) Обновление по ID
        print("\nОбновляем добавленного клиента (сменим ФИО и email)")
        try:
            updated = repo.replace_by_id(
                int(added.id) if added.id is not None else -1,
                {
                    "last_name": "Романов",
                    "first_name": "Роман",
                    "middle_name": "Сергеевич",
                    "passport_series": added.passport_series,
                    "passport_number": added.passport_number,
                    "birth_date": added.birth_date,
                    "phone": added.phone,
                    "email": "romanov.updated@example.com",
                    "address": added.address,
                },
            )
            print(f"✓ Обновлён: id={updated.id} — {updated}")
        except ValueError as exc:
            print(f"✗ Не удалось обновить: {exc}")

        # e) Удаление по ID
        print("\nУдаляем обновлённого клиента...")
        deleted, derrs = repo.delete_by_id(int(updated.id))
        if deleted:
            print(f"✓ Удалён: id={deleted.id} — {deleted}")
        else:
            print("✗ Ошибки при удалении:")
        for err in derrs:
            hint = f"id={err.get('id')}" if err.get("id") is not None else "?"
            print(f"- {hint}: {err['error_type']}: {err['message']}")
    else:
        print("\nТаблица пуста: пропускаю демонстрацию get_by_id/пагинации/CRUD.")

    # f) get_count
    total = repo.get_count()
    print(f"\n✓ Количество элементов (get_count): {total}")
