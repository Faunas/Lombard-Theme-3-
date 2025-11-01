from typing import List, Tuple, Dict, Any, Union
import json
import os
from client import Client

class ClientsRepJson:
    def __init__(self, path: str, wrapper_key: str | None = None) -> None:
        self.path = path
        self.wrapper_key = wrapper_key

    def _unwrap(self, data: Union[list, dict]) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            key = self.wrapper_key or "items"
            if key in data and isinstance(data[key], list):
                return data[key]
        raise ValueError("Некорректный JSON: нужен массив объектов или объект с ключом 'items'.")

    def _client_to_dict(self, c: Client) -> Dict[str, Any]:
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

    def _detect_wrapper(self) -> str | None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return self.wrapper_key
        except json.JSONDecodeError:
            return self.wrapper_key

        if isinstance(raw, list):
            return None
        if isinstance(raw, dict):
            if self.wrapper_key and self.wrapper_key in raw and isinstance(raw[self.wrapper_key], list):
                return self.wrapper_key
            if "items" in raw and isinstance(raw["items"], list):
                return "items"
        return self.wrapper_key

    def _wrap(self, records: list, wrapper: str | None) -> Union[list, dict]:
        return {wrapper: records} if wrapper else records

    def _derive_out_path(self, base_path: str, suffix: str) -> str:
        """Возвращаем корректный путь .json"""
        root, ext = os.path.splitext(base_path)
        if ext.lower() == ".json":
            return f"{root}{suffix}{ext}"
        return f"{base_path}{suffix}.json"

    def read_all(self, tolerant: bool = False) -> Tuple[List[Client], List[Dict[str, Any]]]:
        """Читает файл и возвращает (ok, errors)."""
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        records = self._unwrap(raw)

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

    def write_snapshot_all_records(self, out_path: str | None = None, *, pretty: bool = True,
                                   preserve_wrapper: bool = True) -> str:
        """
        Делает снимок исходного файла
        """
        if out_path is None:
            out_path = self._derive_out_path(self.path, "_snapshot")

        with open(self.path, "r", encoding="utf-8") as fin:
            raw = json.load(fin)

        records = self._unwrap(raw)
        wrapper_to_use = self._detect_wrapper() if preserve_wrapper else self.wrapper_key
        data_to_write = self._wrap(records, wrapper_to_use)

        with open(out_path, "w", encoding="utf-8") as fout:
            json.dump(data_to_write, fout, ensure_ascii=False, indent=2 if pretty else None)

        return out_path

    def write_all_ok(self, clients: List[Client], out_path: str | None = None,
                     *, pretty: bool = True, preserve_wrapper: bool = True) -> str:
        """
        Пишет только валидные записи (список clients) в файл с суффиксом _clean.
        """
        if out_path is None:
            out_path = self._derive_out_path(self.path, "_clean")

        records = [self._client_to_dict(c) for c in clients]
        wrapper_to_use = self._detect_wrapper() if preserve_wrapper else self.wrapper_key
        data_to_write = self._wrap(records, wrapper_to_use)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data_to_write, f, ensure_ascii=False, indent=2 if pretty else None)

        return out_path

    def write_errors(self, errors: List[Dict[str, Any]], out_path: str | None = None,
                     *, pretty: bool = True) -> str:
        """
        Пишет подробный отчёт об ошибках в файл с суффикстом _errors.
        """
        if out_path is None:
            out_path = self._derive_out_path(self.path, "_errors")
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

if __name__ == '__main__':
    repo = ClientsRepJson("clients.json")
    clients, errs = repo.read_all(tolerant=True)

    print(repo.render_report(clients, errs, view="short"))

    snap_path = repo.write_snapshot_all_records(preserve_wrapper=True)
    print(f"\n✓ Снимок исходных данных: {snap_path}")

    clean_path = repo.write_all_ok(clients, preserve_wrapper=True)
    print(f"✓ Очищенный файл с валидными клиентами: {clean_path}")

    if errs:
        err_path = repo.write_errors(errs)
        print(f"✓ Отчёт об ошибках: {err_path}")
