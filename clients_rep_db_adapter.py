from __future__ import annotations

from typing import Any

from base_clients_repo import BaseClientsRepo
from client import Client
from client_short import ClientShort
from clients_rep_db import ClientsRepDB
from db_singleton import PgDB


class ClientsRepDBAdapter(BaseClientsRepo):
    """
    Адаптер: делает ClientsRepDB совместимым с интерфейсом BaseClientsRepo.
    Методы BaseClientsRepo делегируются внутрь ClientsRepDB.
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
        # path базовому классу не нужен для БД, но по сигнатуре обязателен — ставим маркер
        super().__init__(path=":db:")
        self._db = ClientsRepDB(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            auto_migrate=auto_migrate,
        )

    # --- файловые операции в адаптере не поддерживаются ---

    def derive_out_path(self, base_path: str, suffix: str) -> str:  # noqa: ARG002
        return f":db:{suffix}"

    def _read_array(self, path: str) -> list[dict[str, Any]]:  # noqa: ARG002
        raise NotImplementedError("DB adapter не поддерживает чтение/запись массивов.")

    def _write_array(  # noqa: ARG002
        self,
        path: str,
        records: list[dict[str, Any]],
        pretty: bool,
    ) -> None:
        raise NotImplementedError("DB adapter не поддерживает чтение/запись массивов.")

    # --- реализация интерфейса BaseClientsRepo (делегирование в ClientsRepDB) ---

    def get_by_id(
        self,
        target_id: int,
        *,
        allow_raw_fallback: bool = True,  # совместимость с базовым интерфейсом
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        # Параметр allow_raw_fallback не используется для БД.
        return self._db.get_by_id(target_id)

    def get_k_n_short_list(
        self,
        k: int,
        n: int,
        *,
        prefer_contact: str = "phone",
    ) -> list[ClientShort]:
        return self._db.get_k_n_short_list(k, n, prefer_contact=prefer_contact)

    def add_client(
        self,
        data: Client | dict | str,
        *,
        pretty: bool = True,  # совместимость с базовым интерфейсом
    ) -> Client:
        return self._db.add_client(data)

    def replace_by_id(
        self,
        target_id: int,
        data: Client | dict | str,
        *,
        pretty: bool = True,  # совместимость с базовым интерфейсом
    ) -> Client:
        return self._db.replace_by_id(target_id, data)

    def delete_by_id(
        self,
        target_id: int,
        *,
        pretty: bool = True,  # совместимость с базовым интерфейсом
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        return self._db.delete_by_id(target_id)

    def get_count(self) -> int:
        return self._db.get_count()

    def sort_by_last_name(self, ascending: bool = True) -> list[Client]:
        """
        Возвращает все записи, отсортированные по last_name (и id для детерминизма).
        Реализовано напрямую через БД, далее собираем Client, как в файловых репозиториях.
        """
        order = "ASC" if ascending else "DESC"
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
                email,
                address
            FROM clients
            ORDER BY last_name {order}, id ASC;
        """
        rows = PgDB.get().fetch_all(sql)
        out: list[Client] = []
        for r in rows:
            payload = self._db._row_to_client_payload(r)
            out.append(Client(payload))
        return out


if __name__ == "__main__":
    # 1) Импортируем данные (однократно)
    db_raw = ClientsRepDB(
        host="127.0.0.1",
        port=5432,
        dbname="lucky_db",
        user="postgres",
        password="123",
    )
    print("Импорт из clients_clean.json ...")
    summary = db_raw.import_from_clean_json(
        "clients_clean.json",
        replace=True,
        preserve_ids=True,
    )
    print(
        f"✓ Импорт завершён: total={summary['total']}, "
        f"inserted={summary['inserted']}, "
        f"skipped={summary['skipped_conflict']}, "
        f"invalid={summary['invalid']}"
    )
    if summary["errors"]:
        print("Ошибки валидации при импорте (первые 5):")
        for e in summary["errors"][:5]:
            print("-", e)

    # 2) Работаем через адаптер (единый интерфейс BaseClientsRepo)
    repo = ClientsRepDBAdapter(
        host="127.0.0.1",
        port=5432,
        dbname="lucky_db",
        user="postgres",
        password="123",
    )

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
    added = repo.add_client(
        {
            "last_name": "Адаптеров",
            "first_name": "Сергей",
            "middle_name": "Игоревич",
            "passport_series": "7410",
            "passport_number": "258369",
            "birth_date": "12-04-1994",
            "phone": "+79990007711",
            "email": "adapter.sergey@example.com",
            "address": "г. Пермь, ул. Ленина, д. 7",
        }
    )
    print(f"✓ Добавлен: id={added.id} — {added}")

    # 2.4) Получение по id
    obj, errs = repo.get_by_id(added.id)  # allow_raw_fallback игнорируется для БД
    print(f"\nПоиск по id={added.id}:")
    if obj:
        print(obj.to_full_string())
    if errs:
        for e in errs:
            print(f"- id={e.get('id')}: {e['error_type']}: {e['message']}")

    # 2.5) Обновление по id
    print("\nОбновление (сменим только адрес и email)...")
    updated = repo.replace_by_id(
        added.id,
        {
            "last_name": added.last_name,
            "first_name": added.first_name,
            "middle_name": added.middle_name,
            "passport_series": added.passport_series,
            "passport_number": added.passport_number,
            "birth_date": added.birth_date,
            "phone": added.phone,
            "email": "adapter.sergey.updated@example.com",
            "address": "г. Пермь, пр-т Молодёжный, д. 12",
        },
    )
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
        hint = f"id={e.get('id')}" if e.get("id") is not None else "?"
        print(f"- {hint}: {e['error_type']}: {e['message']}")

    # 2.8) Итого
    print(f"\n✓ Количество элементов после операций (get_count): {repo.get_count()}")
