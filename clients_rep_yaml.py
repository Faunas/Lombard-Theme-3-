from typing import List, Tuple, Dict, Any, Union
import os
import yaml
from client import Client


class ClientsRepYaml:
    def __init__(self, path: str) -> None:
        self.path = path

    @staticmethod
    def derive_out_path(base_path: str, suffix: str) -> str:
        root, ext = os.path.splitext(base_path)
        if ext.lower() in (".yaml", ".yml"):
            return f"{root}{suffix}{ext}"
        return f"{base_path}{suffix}.yaml"

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
            data = yaml.safe_load(f)
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError("YAML должен быть массивом объектов (списком).")
        return data

    def read_all(self, tolerant: bool = False) -> Tuple[List[Client], List[Dict[str, Any]]]:
        try:
            records = self.read_array(self.path)
        except FileNotFoundError:
            records = []

        ok: List[Client] = []
        errors: List[Dict[str, Any]] = []

        for idx, rec in enumerate(records):
            try:
                ok.append(Client(rec))
            except Exception as e:
                err = {
                    "index": idx,
                    "display_index": idx + 1,
                    "id": (rec or {}).get("id", None) if isinstance(rec, dict) else None,
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

    def write_all_ok(self, clients: List[Client], out_path: str | None = None, *, pretty: bool = True) -> str:
        """
        Пишет только валидные записи (список clients) в новый YAML-файл как массив объектов.
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_clean")

        records = [self.client_to_dict(c) for c in clients]

        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                records,
                f,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
                default_flow_style=not pretty
            )

        return out_path


if __name__ == "__main__":
    repo = ClientsRepYaml("clients.yaml")
    clients, errs = repo.read_all(tolerant=True)
    print(f"Загружено клиентов: {len(clients)}; ошибок: {len(errs)}")

    out_file = repo.write_all_ok(clients)
    print(f"✓ Записано валидных записей в: {out_file}")
