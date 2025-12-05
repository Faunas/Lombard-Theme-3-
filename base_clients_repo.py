from __future__ import annotations

from typing import List, Tuple, Dict, Any, Union, Optional
from abc import ABC, abstractmethod
import os

from client import Client
from client_short import ClientShort


class BaseClientsRepo(ABC):
    """
    Базовый репозиторий с общей логикой
    """
    def __init__(self, path: str) -> None:
        self.path = path


    @abstractmethod
    def derive_out_path(self, base_path: str, suffix: str) -> str:
        """
        Вернуть путь для вывода с учётом расширения формата и суффикса.
        """
        raise NotImplementedError

    @abstractmethod
    def _read_array(self, path: str) -> list:
        """
        Прочитать массив записей (list[dict]) из файла `path`.
        Должен:
          - вернуть list
          - кидать FileNotFoundError если файла нет
          - кидать ValueError при некорректном формате/структуре
        """
        raise NotImplementedError

    @abstractmethod
    def _write_array(self, path: str, records: list, pretty: bool) -> None:
        """
        Записать массив записей (list[dict]) в файл `path`.
        """
        raise NotImplementedError

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

    def read_all(self, tolerant: bool = False) -> Tuple[List[Client], List[Dict[str, Any]]]:
        try:
            records = self._read_array(self.path)
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

    def write_snapshot_all_records(self, out_path: Optional[str] = None, *, pretty: bool = True) -> str:
        """
        Снимок исходного файла: читаем массив целиком и сохраняем как есть (массив).
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_snapshot")

        records = self._read_array(self.path)
        self._write_array(out_path, records, pretty)
        return out_path

    def write_all_ok(self, clients: List[Client], out_path: Optional[str] = None, *, pretty: bool = True) -> str:
        """
        Пишет только валидные записи (список clients) в новый файл как массив объектов.
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_clean")

        records = [self.client_to_dict(c) for c in clients]
        self._write_array(out_path, records, pretty)
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

    def get_by_id(self, target_id: int, *, allow_raw_fallback: bool = True) -> Tuple[
        Optional[Client], List[Dict[str, Any]]]:
        """
        Возвращает (Client | None, errors) по id.
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: List[Dict[str, Any]] = []
        clean_path = self.derive_out_path(self.path, "_clean")

        # 1) Пытаемся искать в _clean
        try:
            records = self._read_array(clean_path)
            matches: List[dict] = []
            for rec in records:
                rec_id = (rec or {}).get("id", None)
                try:
                    rec_id_norm = int(rec_id) if rec_id is not None else None
                except Exception:
                    rec_id_norm = None
                if rec_id_norm == target_id:
                    matches.append(rec)

            if matches:
                if len(matches) > 1:
                    errors.append({
                        "id": target_id,
                        "error_type": "DuplicateId",
                        "message": f"Несколько записей с id={target_id} в валидированном наборе; возвращаю первую"
                    })
                return Client(matches[0]), errors

            # если _clean есть, но запись не найдена — опционально падаем в raw
            if allow_raw_fallback:
                ok, _ = self.read_all(tolerant=True)  # валидирует сырой файл
                matches2 = [c for c in ok if c.id == target_id]
                if matches2:
                    if len(matches2) > 1:
                        errors.append({
                            "id": target_id,
                            "error_type": "DuplicateId",
                            "message": f"Несколько записей с id={target_id} в исходном наборе; возвращаю первую"
                        })
                    return matches2[0], errors

            errors.append({
                "id": target_id,
                "error_type": "NotFound",
                "message": f"Клиент с id={target_id} не найден ни в clean, ни в исходном файле"
            })
            return None, errors

        except FileNotFoundError:
            # _clean отсутствует — используем raw-валидацию как раньше
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

    def get_k_n_short_list(self, k: int, n: int, *, prefer_contact: str = "phone") -> List[ClientShort]:
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k и n должны быть положительными целыми числами")

        clean_path = self.derive_out_path(self.path, "_clean")

        try:
            records = self._read_array(clean_path)
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
            records = self._read_array(clean_path)
            clients = [Client(rec) for rec in records]
        except FileNotFoundError:
            clients, _ = self.read_all(tolerant=True)
        return sorted(clients, key=lambda c: c.last_name, reverse=not ascending)

    def add_client(self, data: Union[Client, dict, str], *, pretty: bool = True) -> Client:
        try:
            records = self._read_array(self.path)
        except FileNotFoundError:
            records = []

        if isinstance(data, Client):
            new_client = data
        elif isinstance(data, (dict, str)):
            new_client = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str (JSON/YAML/строка с полями)")

        # Проверка дубликата по Client.__eq__ среди уже валидных записей
        existing_ok, _ = self.read_all(tolerant=True)
        dup_ids = [c.id for c in existing_ok if c == new_client]
        if dup_ids:
            raise ValueError(f"DuplicateClient: такой клиент уже существует (id={', '.join(map(str, dup_ids))})")

        # Назначаем новый id = max(id) + 1 по исходному файлу
        existing_ids: List[int] = []
        for r in records:
            rid = (r or {}).get("id")
            try:
                if rid is not None:
                    existing_ids.append(int(rid))
            except Exception:
                pass
        new_id = (max(existing_ids) if existing_ids else 0) + 1

        new_client.id = new_id
        records.append(self.client_to_dict(new_client))
        self._write_array(self.path, records, pretty)

        return new_client

    def replace_by_id(self, target_id: int, data: Union[Client, dict, str], *, pretty: bool = True) -> Client:
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        found, errs = self.get_by_id(target_id)
        if not found:
            msg = errs[0]["message"] if errs else f"Клиент с id={target_id} не найден"
            raise ValueError(f"NotFound: {msg}")

        if isinstance(data, Client):
            new_client = data
        elif isinstance(data, (dict, str)):
            new_client = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str (JSON/YAML/строка с полями)")

        if new_client.id is not None and new_client.id != target_id:
            raise ValueError(f"MismatchedId: payload id={new_client.id} != target id={target_id}")

        existing_ok, _ = self.read_all(tolerant=True)
        dup_ids = [c.id for c in existing_ok if c.id != target_id and c == new_client]
        if dup_ids:
            raise ValueError(f"DuplicateClient: такой клиент уже существует (id={', '.join(map(str, dup_ids))})")

        records = self._read_array(self.path)
        idxs: List[int] = []
        for i, rec in enumerate(records):
            rec_id = (rec or {}).get("id", None)
            try:
                rec_id_norm = int(rec_id) if rec_id is not None else None
            except Exception:
                rec_id_norm = None
            if rec_id_norm == target_id:
                idxs.append(i)

        if not idxs:
            raise ValueError(f"NotFound: id={target_id}")
        if len(idxs) > 1:
            raise ValueError(f"DuplicateId: найдено несколько записей с id={target_id}; обновление отменено")

        new_client.id = target_id
        records[idxs[0]] = self.client_to_dict(new_client)
        self._write_array(self.path, records, pretty)

        return new_client

    def delete_by_id(self, target_id: int, *, pretty: bool = True) -> Tuple[Union[Client, None], List[Dict[str, Any]]]:
        """
        Удаляет запись с указанным id из исходного файла (JSON/YAML).
        Возвращает (удалённый Client | None, errors).
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: List[Dict[str, Any]] = []

        try:
            records = self._read_array(self.path)
        except FileNotFoundError:
            errors.append({
                "id": target_id,
                "error_type": "NotFound",
                "message": f"Файл {self.path} не найден"
            })
            return None, errors

        idxs: List[int] = []
        for i, rec in enumerate(records):
            rec_id = (rec or {}).get("id", None)
            try:
                rec_id_norm = int(rec_id) if rec_id is not None else None
            except Exception:
                rec_id_norm = None
            if rec_id_norm == target_id:
                idxs.append(i)

        if not idxs:
            errors.append({
                "id": target_id,
                "error_type": "NotFound",
                "message": f"Клиент с id={target_id} не найден"
            })
            return None, errors

        if len(idxs) > 1:
            errors.append({
                "id": target_id,
                "error_type": "DuplicateId",
                "message": f"Найдено несколько записей с id={target_id}; удаление отменено"
            })
            return None, errors

        idx = idxs[0]
        rec = records.pop(idx)

        self._write_array(self.path, records, pretty)

        try:
            deleted_client = Client(rec)
            return deleted_client, errors
        except Exception as e:
            errors.append({
                "id": target_id,
                "error_type": type(e).__name__,
                "message": f"Удалено, но запись невалидна: {str(e)}"
            })
            return None, errors

    def get_count(self) -> int:
        clean_path = self.derive_out_path(self.path, "_clean")
        try:
            return len(self._read_array(clean_path))
        except FileNotFoundError:
            return len(self.read_all(tolerant=True)[0])
