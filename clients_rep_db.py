from typing import Tuple, List, Dict, Optional, Any
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor

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


    # Функция для добавления первого тестового клиента в таблицу
    def _seed_if_empty(self) -> Optional[int]:
        """
        Если таблица пуста - добавим одну запись, вернём её id.
        """
        check_sql = "SELECT COUNT(*) AS cnt FROM clients;"
        insert_sql = """
            INSERT INTO clients
            (last_name, first_name, middle_name, passport_series, passport_number, birth_date, phone, email, address)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id;
        """
        with self._connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(check_sql)
            if cur.fetchone()["cnt"] > 0:
                return None
            cur.execute(
                insert_sql,
                (
                    "Иванов", "Иван", "Петрович",
                    "1234", "567890",
                    date(1990, 1, 1),
                    "+79991234567",
                    "ivanov.i@example.ru",
                    "г. Москва, ул. Пушкина, д. 1",
                ),
            )
            new_id = cur.fetchone()["id"]
            return new_id


if __name__ == "__main__":
    repo = ClientsRepDB(
        host="127.0.0.1",
        port=5432,
        dbname="lucky_db",
        user="postgres",
        password="123",
        auto_migrate=True,
    )

    # если нет записи в таблице, функция ниже добавит одного клиента
    seeded_id = repo._seed_if_empty()
    target_id = seeded_id if seeded_id is not None else 1

    client_obj, errs = repo.get_by_id(target_id)

    if client_obj:
        print("✓ Найден клиент:")
        print(client_obj.to_full_string())
    else:
        print("✗ Не найден.")
    if errs:
        print("\nЗамечания/ошибки:")
        for e in errs:
            print(f"- id={e.get('id')}: {e['error_type']}: {e['message']}")

    # Пагинация: страница 1 по 3 элемента
    print("\nСтраница 1 (по 3 элемента):")
    page = repo.get_k_n_short_list(1, 3, prefer_contact="phone")
    for s in page:
        print("-", s)

    # Пагинация: страница 2 по 3 элемента
    print("\nСтраница 2 (по 3 элемента):")
    page2 = repo.get_k_n_short_list(2, 3, prefer_contact="email")
    for s in page2:
        print("-", s)

