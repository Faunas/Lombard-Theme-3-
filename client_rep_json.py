from typing import List, Tuple, Dict, Any, Union
import json
import os
from client import Client
from client_short import ClientShort


class ClientsRepJson:
    def __init__(self, path: str) -> None:
        self.path = path

    @staticmethod
    def derive_out_path(base_path: str, suffix: str) -> str:
        root, ext = os.path.splitext(base_path)
        if ext.lower() == ".json":
            return f"{root}{suffix}{ext}"
        return f"{base_path}{suffix}.json"

    @staticmethod
    def client_to_dict(c: Client) -> Dict[str, Any]:
        return {
            "id": c.id,
            "last_name": c.last_name,
            "first_name": c.first_name,
            "middle_name": c.middle_name,
            "passport_series": c.passport_series,
            "passport_number": c.passport_number,
            "birth_date": c.birth_date,
            "phone": c.phone,
            "email": c.email,
            "address": c.address,
        }

    def read_array(self, path: str) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON должен быть массивом объектов (списком).")
        return data

    def read_all(self, tolerant: bool = False) -> Tuple[List[Client], List[Dict[str, Any]]]:
        records = self.read_array(self.path)

        ok: List[Client] = []
        errors: List[Dict[str, Any]] = []

        for idx, rec in enumerate(records):
            try:
                ok.append(Client(rec))
            except Exception as e:
                err = {
                    "index": idx,
                    "display_index": idx + 1,
                    "id": rec.get("id", None),
                    "error_type": type(e).__name__,
                    "message": str(e),
                }
                if not tolerant:
                    where = f"элемент #{err['display_index']}"
                    if err["id"] is not None:
                        where += f" (id={err['id']})"
                    raise ValueError(f"Ошибка чтения {self.path}: {where}: {err['message']}") from e
                errors.append(err)

        return ok, errors

    def write_snapshot_all_records(self, out_path: str | None = None, *, pretty: bool = True) -> str:
        """
        Снимок исходного файла: читаем массив целиком и сохраняем как есть (массив).
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_snapshot")

        records = self.read_array(self.path)
        with open(out_path, "w", encoding="utf-8") as fout:
            json.dump(records, fout, ensure_ascii=False, indent=2 if pretty else None)

        return out_path

    def write_all_ok(self, clients: List[Client], out_path: str | None = None, *, pretty: bool = True) -> str:
        """
        Пишет только валидные записи (список clients) в новый файл как массив объектов.
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_clean")

        records = [self.client_to_dict(c) for c in clients]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2 if pretty else None)

        return out_path

    def write_errors(self, errors: List[Dict[str, Any]], out_path: str | None = None, *, pretty: bool = True) -> str:
        """
        Пишет подробный отчёт об ошибках в файл.
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_errors")
        payload = {"errors": errors, "source": os.path.basename(self.path)}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)
        return out_path

    def render_report(self, ok: List[Client], errors: List[Dict[str, Any]], *, view: str = "short") -> str:
        lines: List[str] = []
        lines.append(f"Загружено клиентов: {len(ok)}; ошибок: {len(errors)}")

        if ok:
            lines.append("Успешно загружены:")
            if view == "full":
                for c in ok:
                    cid = c.id if c.id is not None else "—"
                    lines.append(f"- id={cid}:\n{c.to_full_string()}")
            else:
                for c in ok:
                    cid = c.id if c.id is not None else "—"
                    lines.append(f"- id={cid}: {c}")

        if errors:
            lines.append("Ошибки:")
            for e in errors:
                hint = f"id={e['id']}" if e['id'] is not None else f"index={e['display_index']}"
                lines.append(f"- {hint}: {e['error_type']}: {e['message']}")

        return "\n".join(lines)

    def get_by_id(self, target_id: int) -> Tuple[Union[Client, None], List[Dict[str, Any]]]:
        """
        Возвращает (Client | None, errors) по указанному id.
        Сначала ищем в <path>_clean.json; если его нет — валидируем исходный файл в памяти и ищем среди ok.
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        clean_path = self.derive_out_path(self.path, "_clean")
        errors: List[Dict[str, Any]] = []

        try:
            records = self.read_array(clean_path)
        except FileNotFoundError:
            ok, _ = self.read_all(tolerant=True)
            matches = [c for c in ok if c.id == target_id]
            if not matches:
                errors.append({
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": f"Клиент с id={target_id} не найден (clean-файл отсутствует)"
                })
                return None, errors
            if len(matches) > 1:
                errors.append({
                    "id": target_id,
                    "error_type": "DuplicateId",
                    "message": f"Несколько записей с id={target_id}; возвращаю первую"
                })
            return matches[0], errors
        except json.JSONDecodeError as e:
            raise ValueError(f"Некорректный JSON в {clean_path}: {e}") from e

        matches: list[dict] = []
        for rec in records:
            rec_id = rec.get("id", None)
            try:
                rec_id_norm = int(rec_id) if rec_id is not None else None
            except Exception:
                rec_id_norm = None
            if rec_id_norm == target_id:
                matches.append(rec)

        if not matches:
            errors.append({
                "id": target_id,
                "error_type": "NotFound",
                "message": f"Клиент с id={target_id} не найден в валидированном наборе"
            })
            return None, errors

        if len(matches) > 1:
            errors.append({
                "id": target_id,
                "error_type": "DuplicateId",
                "message": f"Несколько записей с id={target_id} в валидированном наборе; возвращаю первую"
            })

        return Client(matches[0]), errors

    def get_k_n_short_list(self, k: int, n: int, *, prefer_contact: str = "phone") -> List[ClientShort]:
        """
        Возвращает страницу k размером n из валидированных записей в виде объектов ClientShort.
        """
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k и n должны быть положительными целыми числами")

        clean_path = self.derive_out_path(self.path, "_clean")

        try:
            records = self.read_array(clean_path)
        except FileNotFoundError:
            ok, _ = self.read_all(tolerant=True)
            records = [self.client_to_dict(c) for c in ok]

        shorts = [ClientShort(rec, prefer_contact=prefer_contact) for rec in records]

        start = (k - 1) * n
        end = start + n
        return shorts[start:end]


if __name__ == '__main__':
    repo = ClientsRepJson("clients.json")
    clients, errs = repo.read_all(tolerant=True)

    print(repo.render_report(clients, errs, view="short"))

    snap_path = repo.write_snapshot_all_records()
    print(f"\n✓ Снимок исходных данных: {snap_path}")

    clean_path = repo.write_all_ok(clients)
    print(f"✓ Очищенный файл с валидными клиентами: {clean_path}")

    if errs:
        err_path = repo.write_errors(errs)
        print(f"✓ Отчёт об ошибках: {err_path}")

    SEARCH_ID = 4
    found, ferrs = repo.get_by_id(SEARCH_ID)

    if found:
        print(f"\n✓ Найден по id={SEARCH_ID}:")
        print(found.to_full_string())

    if ferrs:
        print("\nЗамечания/ошибки при поиске:")
        for e in ferrs:
            hint = f"id={e.get('id')}" if e.get('id') is not None else f"index={e.get('display_index')}"
            print(f"- {hint}: {e['error_type']}: {e['message']}")

    try:
        total = len(repo.read_array(repo.derive_out_path(repo.path, "_clean")))
    except FileNotFoundError:
        total = len(repo.read_all(tolerant=True)[0])

    elements_on_sheet = 3 # Кол-во элементов на странице
    find_sheet_number = 1 # Страница

    total_pages = (total + elements_on_sheet - 1) // elements_on_sheet

    print("\nВсего элементов:", total, "Всего страниц:", total_pages)

    page = repo.get_k_n_short_list(find_sheet_number, elements_on_sheet)
    print(f"Страница {find_sheet_number} по {elements_on_sheet} элемента (short):")
    for s in page:
        print("-", s)
