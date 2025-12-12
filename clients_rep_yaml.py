# clients_rep_yaml.py
from __future__ import annotations

import os
from typing import Any

import yaml  # type: ignore[import-untyped]

from base_clients_repo import BaseClientsRepo
from client import Client


class ClientsRepYaml(BaseClientsRepo):
    def derive_out_path(self, base_path: str, suffix: str) -> str:
        root, ext = os.path.splitext(base_path)
        if ext.lower() in (".yaml", ".yml"):
            return f"{root}{suffix}{ext}"
        return f"{base_path}{suffix}.yaml"

    def _read_array(self, path: str) -> list[dict[str, Any]]:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError("YAML должен быть массивом объектов (списком).")
        # Гарантируем список словарей
        result: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                result.append(item)
            else:
                result.append({"__raw__": item})
        return result

    def _write_array(
        self,
        path: str,
        records: list[dict[str, Any]],
        pretty: bool,
    ) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                records,
                f,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
                default_flow_style=not pretty,
            )

    # Отчёт об ошибках в YAML
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
            yaml.safe_dump(
                payload,
                f,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
                default_flow_style=not pretty,
            )
        return out_path


if __name__ == "__main__":
    repo = ClientsRepYaml("clients.yaml")
    print("==== YAML ====")

    # a) Чтение всех значений
    ok, errs = repo.read_all(tolerant=True)
    print(repo.render_report(ok, errs, view="short"))

    # Бэкап исходника
    try:
        snap_path = repo.write_snapshot_all_records()
        print(f"\n✓ Снимок исходных данных: {snap_path}")
    except FileNotFoundError:
        print("\n! Файл clients.yaml не найден — пропускаю снимок исходных данных.")

    # b) Запись всех валидных значений в _clean
    clean_path = repo.write_all_ok(ok)
    print(f"✓ Очищенный файл (валидные записи): {clean_path}")

    # Запишем ошибки
    if errs:
        try:
            err_path = repo.write_errors(errs)
            print(f"✓ Отчёт об ошибках: {err_path}")
        except Exception as exc:
            print(f"! Не удалось записать отчёт об ошибках: {exc}")

    # i) get_count
    count_before = repo.get_count()
    print(f"\n✓ Количество элементов (get_count): {count_before}")

    # Если данных нет — добавить тестового клиента, чтобы проверить операции
    if not ok:
        seed = repo.add_client(
            {
                "last_name": "ТестовYAML",
                "first_name": "Иван",
                "middle_name": "Иванович",
                "passport_series": "1234",
                "passport_number": "567890",
                "birth_date": "01-01-1990",
                "phone": "+79990000002",
                "email": "yaml.seed.user@example.com",
                "address": "г. Санкт-Петербург, ул. Демонстрационная, д. 2",
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

    # f) Добавление (пример — оставлен закомментированным)
    # added = repo.add_client({...})
    # print(f"\n✓ Добавлен клиент id={added.id}: {added}")

    # g) Замена элемента по ID (меняем только адрес, чтобы не ловить дубликаты паспорта)
    if found is not None:
        found.address = "г. Нижний Новгород, ул. Ковалихинская, д. 7"
        updated: Client = repo.replace_by_id(search_id, found)
        print(f"✓ Обновлён клиент id={updated.id}: {updated}")
    else:
        print("! Нечего обновлять: клиент не найден.")

    # h) Удаление по ID (пример — закомментировано)
    # deleted, derrs = repo.delete_by_id(updated.id)  # type: ignore[arg-type]
    # if deleted:
    #     print(f"✓ Удалён клиент id={updated.id}: {deleted}")
    # else:
    #     print("✗ Ошибки при удалении:")
    # for err in derrs:
    #     hint = (
    #         f"id={err.get('id')}"
    #         if err.get('id') is not None
    #         else f"index={err.get('display_index')}"
    #     )
    #     print(f"- {hint}: {err['error_type']}: {err['message']}")

    # i) get_count после всего
    count_after = repo.get_count()
    print(f"\n✓ Количество элементов после операций (get_count): {count_after}")
