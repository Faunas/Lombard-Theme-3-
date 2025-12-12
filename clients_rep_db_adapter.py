from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple, Union
from base_clients_repo import BaseClientsRepo
from client import Client
from client_short import ClientShort
from clients_rep_db import ClientsRepDB


class ClientsRepDBAdapter(BaseClientsRepo):
    """
    Адаптер: делает ClientsRepDB совместимым с интерфейсом BaseClientsRepo.
    Методы BaseClientsRepo делегируются в ClientsRepDB
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
        # path базовому классу не нужен для БД, но требуется по сигнатуре - ставим маркер-заглушку
        super().__init__(path=":db:")
        self._db = ClientsRepDB(
            host=host, port=port, dbname=dbname, user=user, password=password, auto_migrate=auto_migrate
        )

    def derive_out_path(self, base_path: str, suffix: str) -> str:
        return f":db:{suffix}"

    def _read_array(self, path: str) -> list:
        # В адаптере БД не поддерживаем запись
        raise NotImplementedError("DB adapter не поддерживает чтение/запись.")

    def _write_array(self, path: str, records: list, pretty: bool) -> None:
        # В адаптере БД не поддерживаем запись
        raise NotImplementedError("DB adapter не поддерживает чтение/запись.")

    # --- BaseClientsRepo (делегирование в ClientsRepDB) ---

    def get_by_id(self, target_id: int) -> Tuple[Optional[Client], List[Dict[str, Any]]]:
        return self._db.get_by_id(target_id)

    def get_k_n_short_list(self, k: int, n: int, *, prefer_contact: str = "phone") -> List[ClientShort]:
        return self._db.get_k_n_short_list(k, n, prefer_contact=prefer_contact)

    def add_client(self, data: Union[Client, dict, str], *, pretty: bool = True) -> Client:
        return self._db.add_client(data)

    def replace_by_id(self, target_id: int, data: Union[Client, dict, str], *, pretty: bool = True) -> Client:
        return self._db.replace_by_id(target_id, data)

    def delete_by_id(self, target_id: int, *, pretty: bool = True) -> Tuple[Optional[Client], List[Dict[str, Any]]]:
        return self._db.delete_by_id(target_id)

    def get_count(self) -> int:
        return self._db.get_count()

    def sort_by_last_name(self, ascending: bool = True) -> List[Client]:
        """
        Возвращает все записи, отсортированные по last_name.
        Реализовано напрямую через БД для эффективности и совместимости.
        """
        # Снимем все записи и построим Client — так же, как делают файловые репозитории.
        order = "ASC" if ascending else "DESC"
        sql = f"""
            SELECT
                id, last_name, first_name, middle_name,
                passport_series, passport_number, birth_date,
                phone, email, address
            FROM clients
            ORDER BY last_name {order}, id ASC;
        """
        from psycopg2.extras import RealDictCursor
        with self._db.connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        out: List[Client] = []
        for r in rows:
            payload = self._db._row_to_client_payload(r)
            out.append(Client(payload))
        return out


if __name__ == "__main__":
    from psycopg2.extras import RealDictCursor

    # 1) Один раз импортнём clients_clean.json в таблицу
    db_raw = ClientsRepDB(host="127.0.0.1", port=5432, dbname="lucky_db", user="postgres", password="123")
    print("Импорт из clients_clean.json ...")
    summary = db_raw.import_from_clean_json("clients_clean.json", replace=True, preserve_ids=True)
    print(f"✓ Импорт завершён: total={summary['total']}, inserted={summary['inserted']}, "
          f"skipped={summary['skipped_conflict']}, invalid={summary['invalid']}")
    if summary["errors"]:
        print("Ошибки валидации при импорте (первые 5):")
        for e in summary["errors"][:5]:
            print("-", e)

    # 2) Создаём адаптер и работаем с ним по интерфейсу BaseClientsRepo
    repo = ClientsRepDBAdapter(host="127.0.0.1", port=5432, dbname="lucky_db", user="postgres", password="123")

    # 2.1) Кол-во элементов
    total = repo.get_count()
    print(f"\n✓ Количество элементов (get_count): {total}")

    # 2.2) Пагинация (k, n)
    k, n = 1, 3
    page = repo.get_k_n_short_list(k, n, prefer_contact="phone")
    print(f"\nСтраница {k} (по {n} элемента):")
    for s in page:
        print("-", s)

    # 2.3) Добавление
    print("\nДобавляем нового клиента (через Adapter)...")
    added = repo.add_client({
        "last_name": "Адаптеров",
        "first_name": "Сергей",
        "middle_name": "Игоревич",
        "passport_series": "7410",
        "passport_number": "258369",
        "birth_date": "12-04-1994",
        "phone": "+79990007711",
        "email": "adapter.sergey@example.com",
        "address": "г. Пермь, ул. Ленина, д. 7"
    })
    print(f"✓ Добавлен: id={added.id} — {added}")

    # 2.4) Получение по id
    obj, errs = repo.get_by_id(added.id)
    print(f"\nПоиск по id={added.id}:")
    if obj:
        print(obj.to_full_string())
    if errs:
        for e in errs:
            print(f"- id={e.get('id')}: {e['error_type']}: {e['message']}")

    # 2.5) Обновление по id
    print("\nОбновление (сменим только адрес и email)...")
    updated = repo.replace_by_id(added.id, {
        "last_name": added.last_name,
        "first_name": added.first_name,
        "middle_name": added.middle_name,
        "passport_series": added.passport_series,
        "passport_number": added.passport_number,
        "birth_date": added.birth_date,
        "phone": added.phone,
        "email": "adapter.sergey.updated@example.com",
        "address": "г. Пермь, пр-т Молодёжный, д. 12"
    })
    print(f"✓ Обновлён: id={updated.id} — {updated}")

    # 2.6) Сортировка по фамилии
    print("\nСортировка по фамилии (ASC) — первые 5:")
    for c in repo.sort_by_last_name(ascending=True)[:5]:
        print("-", c)

    # 2.7) Удаление
    print("\nУдаляем добавленного (через Adapter)...")
    deleted, derrs = repo.delete_by_id(updated.id)
    if deleted:
        print(f"✓ Удалён: id={deleted.id} — {deleted}")
    else:
        print("✗ Ошибки при удалении:")
    for e in derrs:
        hint = f"id={e.get('id')}" if e.get('id') is not None else "?"
        print(f"- {hint}: {e['error_type']}: {e['message']}")

    # 2.8) Итого
    print(f"\n✓ Количество элементов после операций (get_count): {repo.get_count()}")
