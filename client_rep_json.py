from typing import List, Dict, Any, Optional
import os
import json

from base_clients_repo import BaseClientsRepo


class ClientsRepJson(BaseClientsRepo):
    def derive_out_path(self, base_path: str, suffix: str) -> str:
        root, ext = os.path.splitext(base_path)
        if ext.lower() == ".json":
            return f"{root}{suffix}{ext}"
        return f"{base_path}{suffix}.json"

    def _read_array(self, path: str) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON должен быть массивом объектов (списком).")
        return data

    def _write_array(self, path: str, records: list, pretty: bool) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2 if pretty else None)

    # Отчёт об ошибках в JSON
    def write_errors(self, errors: List[Dict[str, Any]], out_path: Optional[str] = None, *, pretty: bool = True) -> str:
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_errors")
        payload = {"errors": errors, "source": os.path.basename(self.path)}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)
        return out_path

if __name__ == "__main__":
    from typing import List

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
        except Exception as e:
            print(f"! Не удалось записать отчёт об ошибках: {e}")

    # i) get_count
    count_before = repo.get_count()
    print(f"\n✓ Количество элементов (get_count): {count_before}")

    # Если данных нет — добавить тестового клиента, чтобы проверить остальные операции
    if not ok:
        seed = repo.add_client({
            "last_name": "ТестовJSON",
            "first_name": "Иван",
            "middle_name": "Иванович",
            "passport_series": "1234",
            "passport_number": "567890",
            "birth_date": "01-01-1990",
            "phone": "+79990000001",
            "email": "json.seed.user@example.com",
            "address": "г. Москва, ул. Демонстрационная, д. 1"
        })
        print(f"✓ Добавлен тестовый клиент (seed) id={seed.id}")
        ok, errs = repo.read_all(tolerant=True)

    # c) Получить объект по ID
    search_id = ok[0].id if ok and ok[0].id is not None else 1
    found, ferrs = repo.get_by_id(search_id)
    print(f"\nПоиск по id={search_id}:")
    if found:
        print(found.to_full_string())
    if ferrs:
        for e in ferrs:
            print(f"- id={e.get('id')}: {e['error_type']}: {e['message']}")

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
    added = repo.add_client({
        "last_name": "НовиковJSON",
        "first_name": "Никита",
        "middle_name": "Сергеевич",
        "passport_series": "8888",
        "passport_number": "112233",
        "birth_date": "05-05-1995",
        "phone": "+79995551122",
        "email": "novikov.json@example.com",
        "address": "г. Самара, ул. Молодогвардейская, д. 10"
    })
    print(f"\n✓ Добавлен клиент id={added.id}: {added}")

    # g) Замена элемента по ID
    updated = repo.replace_by_id(added.id, {
        "last_name": "РомановJSON",
        "first_name": "Роман",
        "middle_name": "Сергеевич",
        "passport_series": "5555",
        "passport_number": "666777",
        "birth_date": "20-07-1988",
        "phone": "+79997654321",
        "email": "romanov.json.updated@example.com",
        "address": "г. Нижний Новгород, ул. Большая Покровская, д. 12"
    })
    print(f"✓ Обновлён клиент id={updated.id}: {updated}")

    # h) Удаление по ID
    deleted, derrs = repo.delete_by_id(updated.id)
    if deleted:
        print(f"✓ Удалён клиент id={updated.id}: {deleted}")
    else:
        print("✗ Ошибки при удалении:")
    for e in derrs:
        hint = f"id={e.get('id')}" if e.get('id') is not None else f"index={e.get('display_index')}"
        print(f"- {hint}: {e['error_type']}: {e['message']}")

    # i) get_count после всего
    count_after = repo.get_count()
    print(f"\n✓ Количество элементов после операций (get_count): {count_after}")
