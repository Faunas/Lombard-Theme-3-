# db_filter_sort_decorator.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from client import Client
from client_short import ClientShort
from clients_rep_db_adapter import ClientsRepDBAdapter
from db_singleton import PgDB


@dataclass
class ClientFilter:
    last_name_substr: str | None = None
    first_name_substr: str | None = None
    middle_name_substr: str | None = None
    phone_substr: str | None = None
    email_substr: str | None = None

    # точные совпадения (паспорт)
    passport_series: str | None = None  # "1234"
    passport_number: str | None = None  # "567890"

    # диапазон дат рождения (dd-mm-YYYY)
    birth_date_from: str | None = None
    birth_date_to: str | None = None


@dataclass
class SortSpec:
    by: str = "id"           # id | last_name | birth_date (строго из белого списка)
    asc: bool = True


class ClientsRepDBFilterSortDecorator:
    """
    Декоратор, добавляющий фильтрацию и сортировку к get_k_n_short_list/get_count
    при работе с БД (через PgDB). Для совместимости с остальным кодом ПРОКСИРУЕТ
    все остальные операции базовому репозиторию (get_by_id/replace_by_id/...).
    """

    _ALLOWED_SORT = {
        "id": "id",
        "last_name": "last_name",
        "birth_date": "birth_date",
    }

    def __init__(self, base_db_repo: Any = None) -> None:
        """
        base_db_repo — обычно ClientsRepDBAdapter. Декоратор не меняет объект,
        а лишь берёт на себя методы списка/счётчика.
        """
        self._base = base_db_repo

    def get_by_id(
        self,
        target_id: int,
        *,
        allow_raw_fallback: bool = True,
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        return self._base.get_by_id(target_id, allow_raw_fallback=allow_raw_fallback)

    def replace_by_id(
        self,
        target_id: int,
        data: Client | dict | str,
        *,
        pretty: bool = True,
    ) -> Client:
        return self._base.replace_by_id(target_id, data, pretty=pretty)

    def add_client(
        self,
        data: Client | dict | str,
        *,
        pretty: bool = True,
    ) -> Client:
        return self._base.add_client(data, pretty=pretty)

    def delete_by_id(
        self,
        target_id: int,
        *,
        pretty: bool = True,
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        return self._base.delete_by_id(target_id, pretty=pretty)

    def get_count_plain(self) -> int:
        """На случай если где-то вызывается get_count без фильтра — отдаём базовый."""
        return self._base.get_count()

    # ---------- утилиты преобразования дат ----------

    @staticmethod
    def _to_date(s: str | None) -> date | None:
        if not s:
            return None
        return datetime.strptime(s, "%d-%m-%Y").date()

    @staticmethod
    def _date_to_dd_mm_yyyy(d: date | None) -> str | None:
        return d.strftime("%d-%m-%Y") if d else None

    # ---------- построение SQL фрагментов ----------

    def _build_where(self, flt: ClientFilter | None) -> tuple[str, list[Any]]:
        if not flt:
            return "", []

        conds: list[str] = []
        params: list[Any] = []

        def add_ilike(col: str, value: str | None) -> None:
            if value:
                conds.append(f"{col} ILIKE %s")
                params.append(f"%{value}%")

        add_ilike("last_name", flt.last_name_substr)
        add_ilike("first_name", flt.first_name_substr)
        add_ilike("middle_name", flt.middle_name_substr)
        add_ilike("phone", flt.phone_substr)
        add_ilike("email", flt.email_substr)

        # точные по паспорту
        if flt.passport_series:
            conds.append("TRIM(passport_series) = %s")
            params.append(flt.passport_series)
        if flt.passport_number:
            conds.append("TRIM(passport_number) = %s")
            params.append(flt.passport_number)

        # диапазон дат (birth_date в БД — date)
        d_from = self._to_date(flt.birth_date_from)
        d_to = self._to_date(flt.birth_date_to)

        if d_from and d_to:
            conds.append("birth_date BETWEEN %s AND %s")
            params += [d_from, d_to]
        elif d_from:
            conds.append("birth_date >= %s")
            params.append(d_from)
        elif d_to:
            conds.append("birth_date <= %s")
            params.append(d_to)

        if not conds:
            return "", []

        return "WHERE " + " AND ".join(conds), params

    def _build_order_by(self, sort: SortSpec | None) -> str:
        if not sort:
            return "ORDER BY id ASC"
        col = self._ALLOWED_SORT.get((sort.by or "").lower(), "id")
        direction = "ASC" if sort.asc else "DESC"
        return f"ORDER BY {col} {direction}"

    # ---------- публичные методы с фильтрацией/сортировкой ----------

    def get_k_n_short_list(  # noqa: A003 (имя из задания)
        self,
        k: int,
        n: int,
        *,
        filter: ClientFilter | None = None,  # noqa: A001
        sort: SortSpec | None = None,
        prefer_contact: str = "phone",
    ) -> list[ClientShort]:
        """
        Возвращает страницу k (1..), размером n с учётом фильтра и сортировки.
        """
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k и n должны быть положительными целыми числами")

        db = PgDB.get()

        where_sql, params = self._build_where(filter)
        order_sql = self._build_order_by(sort)

        offset = (k - 1) * n
        sql = f"""
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
            {where_sql}
            {order_sql}
            LIMIT %s OFFSET %s;
        """
        rows = db.fetch_all(sql, params + [n, offset])

        out: list[ClientShort] = []
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
            out.append(ClientShort(payload, prefer_contact=prefer_contact))
        return out

    def get_count(self, *, filter: ClientFilter | None = None) -> int:  # noqa: A001
        """
        Считает количество записей по тому же фильтру.
        """
        db = PgDB.get()
        where_sql, params = self._build_where(filter)
        sql = f"SELECT COUNT(*) AS cnt FROM clients {where_sql};"
        row = db.fetch_one(sql, params)
        return int(row["cnt"]) if row else 0


if __name__ == "__main__":
    # 1) Инициализация соединения (Singleton)
    PgDB.init(
        host="127.0.0.1",
        port=5432,
        dbname="lucky_db",
        user="postgres",
        password="123",
    )

    # 2) базовый адаптер и декоратор
    base = ClientsRepDBAdapter()
    repo = ClientsRepDBFilterSortDecorator(base)

    # 3) примеры
    flt = ClientFilter(last_name_substr="ов")
    sort = SortSpec(by="last_name", asc=True)
    page = repo.get_k_n_short_list(1, 5, filter=flt, sort=sort, prefer_contact="email")
    for s in page:
        print("-", s)
    print("count:", repo.get_count(filter=flt))
