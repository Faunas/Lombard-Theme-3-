from typing import Tuple, List, Dict, Optional, Any
from datetime import date, datetime
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from psycopg2 import errorcodes
from client import Client
from client_short import ClientShort


class ClientsRepDB:
    """
    Класс для работы с клиентами через PostgreSQL
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
        self._conn_params = dict(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        if auto_migrate:
            self.ensure_schema()

    def _connect(self):
        return psycopg2.connect(**self._conn_params)

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
            passport_series  CHAR(4) NOT NULL CHECK (passport_series ~ '^[0-9]{4}$'),
            passport_number  CHAR(6) NOT NULL CHECK (passport_number ~ '^[0-9]{6}$'),
            birth_date       DATE    NOT NULL,
            phone            TEXT    NOT NULL,
            email            TEXT    NOT NULL,
            address          TEXT    NOT NULL,
            CONSTRAINT uq_passport UNIQUE (passport_series, passport_number)
        );
        """
        ddl_index_last_name = "CREATE INDEX IF NOT EXISTS idx_clients_last_name ON clients(last_name);"

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(ddl_table)
            cur.execute(ddl_index_last_name)
            # commit произойдёт автоматически при выходе из with

    @staticmethod
    def _date_to_dd_mm_yyyy(d: date) -> str | None:
        return d.strftime("%d-%m-%Y") if d else None

    @staticmethod
    def _dd_mm_yyyy_to_date(s: str) -> date:
        # Нужно для insert/update
        return datetime.strptime(s, "%d-%m-%Y").date()

    @staticmethod
    def _row_to_client_payload(row: Dict[str, Any]) -> Dict[str, Any]:
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

    # ===== 4(a) Получить объект по ID =====
    def get_by_id(self, target_id: int) -> Tuple[Optional[Client], List[Dict[str, Any]]]:
        """
        Возвращает (Client | None, errors) по id из PostgreSQL.
        Ошибки формата (список словарей, как в файловых репозиториях):
          - NotFound: если записи нет
          - ValidationError: если прочитанные из БД поля не проходят валидацию Client(...)
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: List[Dict[str, Any]] = []

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
            with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (target_id,))
                row = cur.fetchone()
        except psycopg2.Error as e:
            # Поднимаем дальше, чтобы сразу увидеть реальную причину ошибки
            raise

        if row is None:
            errors.append({
                "id": target_id,
                "error_type": "NotFound",
                "message": f"Клиент с id={target_id} не найден"
            })
            return None, errors

        payload = self._row_to_client_payload(row)
        try:
            return Client(payload), errors
        except Exception as e:
            errors.append({
                "id": target_id,
                "error_type": type(e).__name__,
                "message": f"Данные в БД невалидны: {str(e)}"
            })
            return None, errors

    # ===== 4(b) Получить страницу k размером n объектов класса short =====
    def get_k_n_short_list(self, k: int, n: int, *, prefer_contact: str = "phone") -> List[ClientShort]:
        """
        Возвращает страницу k (нумерация с 1) размером n в виде объектов ClientShort.
        Порядок фиксированный: ORDER BY id ASC.
        """
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k и n должны быть положительными целыми числами")

        offset = (k - 1) * n

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
        with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (n, offset))
            rows = cur.fetchall()

        result: List[ClientShort] = []
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

    # ===== 4(c) Добавить объект в таблицу (формируется новый ID) =====
    def add_client(self, data: "Client | dict | str") -> Client:
        """
        Вставляет клиента в БД, ID генерируется.
        Возвращает объект Client с присвоенным id.
        Проверяем уникальность по (passport_series, passport_number).
        """
        # Валидация и нормализация входа в единый Client
        if isinstance(data, Client):
            c = data
        elif isinstance(data, (dict, str)):
            c = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str")

        # Преобразуем дату для INSERT
        bd = self._dd_mm_yyyy_to_date(c.birth_date)

        sql = """
            INSERT INTO clients
            (last_name, first_name, middle_name, passport_series, passport_number, birth_date, phone, email, address)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id;
        """
        params = (
            c.last_name, c.first_name, c.middle_name,
            c.passport_series, c.passport_number,
            bd, c.phone, c.email, c.address
        )

        try:
            with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                new_id = cur.fetchone()["id"]
        except psycopg2.IntegrityError as e:
            # Ловим нарушение уникальности по паспорту
            if getattr(e, "pgcode", None) == errorcodes.UNIQUE_VIOLATION:
                raise ValueError(
                    "DuplicateClient: клиент с таким паспортом уже существует"
                ) from e
            raise

        # Возвращаем тот же объект с присвоенным id
        c.id = new_id
        return c


    # ===== 4(d) Заменить элемент списка по ID =====
    def replace_by_id(self, target_id: int, data: "Client | dict | str") -> Client:
        """
        Обновляет запись по id в PostgreSQL.
          - запись с id должна существовать (иначе NotFound);
          - защита от дубля по паспорту: DuplicateClient (уникальный ключ).
        Возвращает обновлённый Client (c id=target_id).
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        # Валидация через Client
        if isinstance(data, Client):
            c = data
        elif isinstance(data, (dict, str)):
            c = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str")

        # id в payload, если задан, должен совпадать с target_id
        if c.id is not None and c.id != target_id:
            raise ValueError(f"Несоответствие ID: payload id={c.id} != target id={target_id}")

        bd = self._dd_mm_yyyy_to_date(c.birth_date)

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
            c.last_name, c.first_name, c.middle_name,
            c.passport_series, c.passport_number,
            bd, c.phone, c.email, c.address,
            target_id,
        )

        try:
            with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        except psycopg2.IntegrityError as e:
            # Проверка уникальности по паспорту
            if getattr(e, "pgcode", None) == errorcodes.UNIQUE_VIOLATION:
                raise ValueError("DuplicateClient: клиент с таким паспортом уже существует") from e
            raise

        if not row:
            raise ValueError(f"NotFound: Клиент с id={target_id} не найден")

        c.id = target_id
        return c

    # ===== 4(e) Удалить элемент списка по ID =====
    def delete_by_id(self, target_id: int) -> tuple[Optional[Client], list[dict[str, Any]]]:
        """
        Удаляет запись по id и возвращает (удалённый Client | None, errors).
        Ошибки (как в файловых репозиториях):
          - NotFound: если записи нет
          - Если данные строки невалидны для Client(...): "Удалено, но запись невалидна"
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: list[dict[str, Any]] = []

        # Сначала читаем строку - чтобы получить клиента, которого будет удалять
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

        with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(select_sql, (target_id,))
            row = cur.fetchone()

            if row is None:
                errors.append({
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": f"Клиент с id={target_id} не найден"
                })
                return None, errors

            # Удаляем
            cur.execute(delete_sql, (target_id,))

        # Пробуем вернуть как Client
        try:
            payload = self._row_to_client_payload(row)
            return Client(payload), errors
        except Exception as e:
            errors.append({
                "id": target_id,
                "error_type": type(e).__name__,
                "message": f"Удалено, но запись невалидна: {str(e)}"
            })
            return None, errors


    # Массовая загрузка из clients_clean.json
    def import_from_clean_json(
            self,
            json_path: str = "clients_clean.json",
            *,
            replace: bool = True,
            preserve_ids: bool = True
    ) -> Dict[str, Any]:
        """
        Импортирует клиентов из JSON-файла.
        - replace=True: перед импортом очищает таблицу.
        - preserve_ids=True: пытается сохранить id из файла; при конфликтах/повторах — пропускает.
        Возвращает сводку: {total, inserted, skipped_conflict, invalid, errors}
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("clean JSON должен быть массивом объектов")

        summary = {
            "total": len(data),
            "inserted": 0,
            "skipped_conflict": 0,
            "invalid": 0,
            "errors": []
        }

        with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            if replace:
                # Полная замена набора
                cur.execute("TRUNCATE TABLE clients RESTART IDENTITY;")

            for i, rec in enumerate(data):
                # Валидация через Client
                try:
                    c = Client(rec)
                except Exception as e:
                    summary["invalid"] += 1
                    summary["errors"].append({"index": i, "error": f"Invalid payload: {e}"})
                    continue

                # Готовим поля к вставке
                bd = self._dd_mm_yyyy_to_date(c.birth_date)
                vals_common = (
                    c.last_name, c.first_name, c.middle_name,
                    c.passport_series, c.passport_number,
                    bd, c.phone, c.email, c.address
                )

                if preserve_ids and c.id is not None:
                    sql = """
                        INSERT INTO clients
                        (id, last_name, first_name, middle_name, passport_series, passport_number, birth_date, phone, email, address)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                        RETURNING id;
                    """
                    params = (c.id,) + vals_common
                else:
                    sql = """
                        INSERT INTO clients
                        (last_name, first_name, middle_name, passport_series, passport_number, birth_date, phone, email, address)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                        RETURNING id;
                    """
                    params = vals_common

                cur.execute(sql, params)
                row = cur.fetchone()
                if row and row.get("id") is not None:
                    summary["inserted"] += 1
                else:
                    summary["skipped_conflict"] += 1

            cur.execute("SELECT pg_get_serial_sequence('clients', 'id') AS seqname;")
            seqname = cur.fetchone()["seqname"]
            if seqname:
                cur.execute("SELECT COALESCE(MAX(id), 0) AS mx FROM clients;")
                max_id = cur.fetchone()["mx"]
                cur.execute(f"SELECT setval('{seqname}', %s)", (max_id,))

        return summary


if __name__ == "__main__":
    repo = ClientsRepDB(
        host="127.0.0.1",
        port=5432,
        dbname="lucky_db",
        user="postgres",
        password="123",
        auto_migrate=True,
    )

    # Заполняем таблицу клиентами из clients_clean
    print("Импорт из clients_clean.json ...")
    summary = repo.import_from_clean_json("clients_clean.json", replace=True, preserve_ids=True)
    print(f"✓ Импорт завершён: total={summary['total']}, inserted={summary['inserted']}, "
          f"skipped={summary['skipped_conflict']}, invalid={summary['invalid']}")
    if summary["errors"]:
        print("Ошибки валидации при импорте:")
        for e in summary["errors"][:5]:  # только первые 5
            print("-", e)

    # Берём минимальный id для показа get_by_id
    with repo._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT MIN(id) AS min_id FROM clients;")
        row = cur.fetchone()
    target_id = row["min_id"]

    client_obj, errs = repo.get_by_id(target_id)
    if client_obj:
        print("\n✓ Найден клиент (минимальный id):")
        print(client_obj.to_full_string())
    if errs:
        print("\nЗамечания/ошибки:")
        for e in errs:
            print(f"- id={e.get('id')}: {e['error_type']}: {e['message']}")

    # Пагинация: покажем первые 2 страницы по 3 элемента
    print("\nСтраница 1 (по 3 элемента):")
    for s in repo.get_k_n_short_list(1, 3, prefer_contact="phone"):
        print("-", s)

    print("\nСтраница 2 (по 3 элемента):")
    for s in repo.get_k_n_short_list(2, 3, prefer_contact="email"):
        print("-", s)

    # c) Добавление нового клиента
    print("\nДобавляем нового клиента...")
    try:
        added = repo.add_client({
            "last_name": "Троевой",
            "first_name": "Антон",
            "middle_name": "Игоревич",
            "passport_series": "1234",
            "passport_number": "999000",
            "birth_date": "15-03-1993",
            "phone": "+79990001234",
            "email": "anton.polevoy@example.com",
            "address": "г. Казань, ул. Баумана, д. 5"
        })
        print(f"✓ Добавлен: id={added.id} — {added}")
    except ValueError as e:
        print(f"✗ Не удалось добавить: {e}")

    # d) Обновление по ID
    print("\nОбновляем добавленного клиента (сменим ФИО и email)")
    try:
        updated = repo.replace_by_id(added.id, {
            "last_name": "Романов",
            "first_name": "Роман",
            "middle_name": "Сергеевич",
            "passport_series": added.passport_series,   # оставим прежний паспорт
            "passport_number": added.passport_number,
            "birth_date": added.birth_date,
            "phone": added.phone,
            "email": "romanov.updated@example.com",
            "address": added.address,
        })
        print(f"✓ Обновлён: id={updated.id} — {updated}")
    except ValueError as e:
        print(f"✗ Не удалось обновить: {e}")

    # e) Удаление по ID
    print("\nУдаляем обновлённого клиента...")
    deleted, derrs = repo.delete_by_id(updated.id)
    if deleted:
        print(f"✓ Удалён: id={deleted.id} — {deleted}")
    else:
        print("✗ Ошибки при удалении:")
    for e in derrs:
        hint = f"id={e.get('id')}" if e.get('id') is not None else "?"
        print(f"- {hint}: {e['error_type']}: {e['message']}")


