# client_rep_json.py
from __future__ import annotations

import json
import os
from typing import Any

from base_clients_repo import BaseClientsRepo
from client import Client


class ClientsRepJson(BaseClientsRepo):
    def derive_out_path(self, base_path: str, suffix: str) -> str:
        root, ext = os.path.splitext(base_path)
        if ext.lower() == ".json":
            return f"{root}{suffix}{ext}"
        return f"{base_path}{suffix}.json"

    def _read_array(self, path: str) -> list[dict[str, Any]]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON должен быть массивом объектов (списком).")
        # Гарантируем список словарей (валидные элементы дальше отфильтруются/валидируются)
        result: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                result.append(item)
            else:
                # допустим негладкие данные — пусть обработка дальше пометит ошибку
                result.append({"__raw__": item})
        return result

    def _write_array(self, path: str, records: list[dict[str, Any]], pretty: bool) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2 if pretty else None)

    # Отчёт об ошибках в JSON
    def write_errors(
        self,
        errors: list[dict[str, Any]],
        out_path: str | None = None,
        *,
        pretty: bool = True,
    ) -> str:
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_errors")
        payload = {"errors": errors, "source": os.path.basename(self.path)}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)
        return out_path


if __name__ == "__main__":
    repo = ClientsRepJson("clients.json")
    print("==== JSON  ====")

    # a) Чтение всех значений
    ok, errs = repo.read_all(tolerant=True)
    print(repo.render_report(ok, errs, view="short"))

    # Бэкап исходника
    try:
        snap_path = repo.write_snapshot_all_records()
        print(f"\n✓ Снимок исходных данных: {snap_path}")
    except FileNotFoundError:
        print("\n! Файл clients.json не найден — пропускаю снимок исходных данных.")

    # b) Запись всех валидных значений в _clean
    clean_path = repo.write_all_ok(ok)
    print(f"✓ Очищенный файл (валидные записи): {clean_path}")

    # Запишем ошибки
    if errs:
        try:
            err_path = repo.write_errors(errs)
            print(f"✓ Отчёт об ошибках: {err_path}")
        except Exception as exc:  # не 'e', чтобы не конфликтовать дальше с mypy
            print(f"! Не удалось записать отчёт об ошибках: {exc}")

    # i) get_count
    count_before = repo.get_count()
    print(f"\n✓ Количество элементов (get_count): {count_before}")

    # Если данных нет — добавить тестового клиента, чтобы проверить остальные операции
    if not ok:
        seed = repo.add_client(
            {
                "last_name": "ТестовJSON",
                "first_name": "Иван",
                "middle_name": "Иванович",
                "passport_series": "1234",
                "passport_number": "567890",
                "birth_date": "01-01-1990",
                "phone": "+79990000001",
                "email": "json.seed.user@example.com",
                "address": "г. Москва, ул. Демонстрационная, д. 1",
            }
        )
        print(f"✓ Добавлен тестовый клиент (seed) id={seed.id}")
        ok, errs = repo.read_all(tolerant=True)

    # c) Получить объект по ID
    search_id: int = ok[0].id if ok and ok[0].id is not None else 1  # type: ignore[assignment]
    found, ferrs = repo.get_by_id(search_id)
    print(f"\nПоиск по id={search_id}:")
    if found:
        print(found.to_full_string())
    if ferrs:
        for err in ferrs:
            print(f"- id={err.get('id')}: {err['error_type']}: {err['message']}")

    # d) get_k_n_short_list (листалка)
    elements_on_sheet = 3
    total = repo.get_count()
    total_pages = (total + elements_on_sheet - 1) // elements_on_sheet
    find_sheet_number = 1
    print(f"\nВсего элементов: {total}; страниц по {elements_on_sheet}: {total_pages}")
    page = repo.get_k_n_short_list(find_sheet_number, elements_on_sheet)
    print(f"Страница {find_sheet_number} (по {elements_on_sheet} элемента):")
    for s in page:
        print("-", s)

    # e) Сортировка
    print("\nСортировка по фамилии (ASC) — первые 5:")
    for c in repo.sort_by_last_name(ascending=True)[:5]:
        print("-", c)
    print("\nСортировка по фамилии (DESC) — первые 5:")
    for c in repo.sort_by_last_name(ascending=False)[:5]:
        print("-", c)

    # f) Добавление нового клиента
    added: Client = repo.add_client(
        {
            "last_name": "НовиковJSON",
            "first_name": "Никита",
            "middle_name": "Сергеевич",
            "passport_series": "8888",
            "passport_number": "112233",
            "birth_date": "05-05-1995",
            "phone": "+79995551122",
            "email": "novikov.json@example.com",
            "address": "г. Самара, ул. Молодогвардейская, д. 10",
        }
    )
    print(f"\n✓ Добавлен клиент id={added.id}: {added}")

    # g) Замена элемента по ID
    updated: Client = repo.replace_by_id(
        added.id,  # type: ignore[arg-type]
        {
            "last_name": added.last_name,
            "first_name": added.first_name,
            "middle_name": added.middle_name,
            "passport_series": added.passport_series,
            "passport_number": added.passport_number,
            "birth_date": added.birth_date,
            "phone": added.phone,
            "email": added.email,
            "address": "г. Нижний Новгород, ул. Большая Покровская, д. 12",
        },
    )
    print(f"✓ Обновлён клиент id={updated.id}: {updated}")

    # h) Удаление по ID
    deleted, derrs = repo.delete_by_id(updated.id)  # type: ignore[arg-type]
    if deleted:
        print(f"✓ Удалён клиент id={updated.id}: {deleted}")
    else:
        print("✗ Ошибки при удалении:")
    for err in derrs:
        hint = (
            f"id={err.get('id')}"
            if err.get("id") is not None
            else f"index={err.get('display_index')}"
        )
        print(f"- {hint}: {err['error_type']}: {err['message']}")

    # i) get_count после всего
    count_after = repo.get_count()
    print(f"\n✓ Количество элементов после операций (get_count): {count_after}")
