from typing import List, Tuple, Dict, Any, Union
import os
import yaml
from client import Client
from client_short import ClientShort


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

    def get_by_id(self, target_id: int) -> Tuple[Union[Client, None], List[Dict[str, Any]]]:
        """
        Возвращает (Client | None, errors) по указанному id.
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
        except yaml.YAMLError as e:
            raise ValueError(f"Некорректный YAML в {clean_path}: {e}") from e

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

    def sort_by_last_name(self, ascending: bool = True) -> List[Client]:
        clean_path = self.derive_out_path(self.path, "_clean")
        try:
            records = self.read_array(clean_path)
            clients = [Client(rec) for rec in records]
        except FileNotFoundError:
            clients, _ = self.read_all(tolerant=True)
        return sorted(clients, key=lambda c: c.last_name, reverse=not ascending)


if __name__ == "__main__":
    repo = ClientsRepYaml("clients.yaml")
    clients, errs = repo.read_all(tolerant=True)
    print(f"Загружено клиентов: {len(clients)}; ошибок: {len(errs)}")

    out_file = repo.write_all_ok(clients)
    print(f"✓ Записано валидных записей в: {out_file}")

    # Пример получения страницы 1 по 3 элемента
    page = repo.get_k_n_short_list(1, 3)
    print("\nСтраница 1 по 3 элемента (short):")
    for s in page:
        print("-", s)

    print("\nОтсортировано по фамилии (ASC):")
    for c in repo.sort_by_last_name(ascending=True):
        print("-", c)

    print("\nОтсортировано по фамилии (DESC):")
    for c in repo.sort_by_last_name(ascending=False):
        print("-", c)
