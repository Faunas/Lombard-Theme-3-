# base_clients_repo.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from client import Client
from client_short import ClientShort


class BaseClientsRepo(ABC):
    """
    Базовый репозиторий с общей логикой (чтение/запись массивов клиентов).
    Конкретные реализации (JSON/YAML/DB-адаптер) переопределяют
    методы _read_array/_write_array/derive_out_path.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    # ---------- НИЗКИЙ УРОВЕНЬ: абстракции формата/хранилища ----------

    @abstractmethod
    def derive_out_path(self, base_path: str, suffix: str) -> str:
        """
        Вернуть путь для вывода с учётом расширения формата и суффикса.
        """
        raise NotImplementedError

    @abstractmethod
    def _read_array(self, path: str) -> list[dict[str, Any]]:
        """
        Прочитать массив записей (list[dict]) из файла/источника `path`.

        Должен:
          - вернуть list[dict]
          - кидать FileNotFoundError если файла/источника нет
          - кидать ValueError при некорректном формате/структуре
        """
        raise NotImplementedError

    @abstractmethod
    def _write_array(
        self,
        path: str,
        records: list[dict[str, Any]],
        pretty: bool,
    ) -> None:
        """
        Записать массив записей (list[dict]) в файл/источник `path`.
        """
        raise NotImplementedError

    # ---------------------- Утилиты уровня домена ----------------------

    @staticmethod
    def client_to_dict(c: Client) -> dict[str, Any]:
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

    # -------------------------- Операции чтения ------------------------

    def read_all(
        self,
        tolerant: bool = False,
    ) -> tuple[list[Client], list[dict[str, Any]]]:
        """
        Читает исходный массив записей, валидирует в Client.
        Возвращает (ok_clients, errors).
        Если tolerant=False — при первой ошибке кидает ValueError.
        """
        try:
            records = self._read_array(self.path)
        except FileNotFoundError:
            records = []

        ok: list[Client] = []
        errors: list[dict[str, Any]] = []

        for idx, rec in enumerate(records):
            try:
                ok.append(Client(rec))
            except Exception as exc:
                err: dict[str, Any] = {
                    "index": idx,
                    "display_index": idx + 1,
                    "id": (rec or {}).get("id", None) if isinstance(rec, dict) else None,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
                if not tolerant:
                    where = f"элемент #{err['display_index']}"
                    if err["id"] is not None:
                        where += f" (id={err['id']})"
                    raise ValueError(
                        f"Ошибка чтения {self.path}: {where}: {err['message']}"
                    ) from exc
                errors.append(err)

        return ok, errors

    # ------------------------ Вспомогательные записи -------------------

    def write_snapshot_all_records(
        self,
        out_path: str | None = None,
        *,
        pretty: bool = True,
    ) -> str:
        """
        Снимок исходного файла: читаем массив целиком и сохраняем как есть (массив).
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_snapshot")

        records = self._read_array(self.path)
        self._write_array(out_path, records, pretty)
        return out_path

    def write_all_ok(
        self,
        clients: list[Client],
        out_path: str | None = None,
        *,
        pretty: bool = True,
    ) -> str:
        """
        Пишет только валидные записи (список clients) в новый файл как массив объектов.
        """
        if out_path is None:
            out_path = self.derive_out_path(self.path, "_clean")

        records = [self.client_to_dict(c) for c in clients]
        self._write_array(out_path, records, pretty)
        return out_path

    def render_report(
        self,
        ok: list[Client],
        errors: list[dict[str, Any]],
        *,
        view: str = "short",
    ) -> str:
        lines: list[str] = []
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
            for err in errors:
                hint = (
                    f"id={err['id']}" if err["id"] is not None else f"index={err['display_index']}"
                )
                lines.append(f"- {hint}: {err['error_type']}: {err['message']}")

        return "\n".join(lines)

    # ---------------------- Поиск/пагинация/сортировка -----------------

    def get_by_id(
        self,
        target_id: int,
        *,
        allow_raw_fallback: bool = True,
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        """
        Возвращает (Client | None, errors) по id.
        1) Ищем в _clean (как dict -> Client).
        2) При необходимости — в сыром файле через read_all(tolerant=True).
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: list[dict[str, Any]] = []
        clean_path = self.derive_out_path(self.path, "_clean")

        try:
            # 1) Ищем в _clean
            records = self._read_array(clean_path)
            matches_dicts: list[dict[str, Any]] = []
            for rec in records:
                rec_id = (rec or {}).get("id", None)
                try:
                    rec_id_norm = int(rec_id) if rec_id is not None else None
                except Exception:
                    rec_id_norm = None
                if rec_id_norm == target_id:
                    matches_dicts.append(rec)

            if matches_dicts:
                if len(matches_dicts) > 1:
                    errors.append(
                        {
                            "id": target_id,
                            "error_type": "DuplicateId",
                            "message": (
                                "Несколько записей с "
                                f"id={target_id} в валидированном наборе; "
                                "возвращаю первую"
                            ),
                        }
                    )
                return Client(matches_dicts[0]), errors

            # 2) Если _clean есть, но записи нет — опционально падаем в raw
            if allow_raw_fallback:
                ok, _ = self.read_all(tolerant=True)
                matches_clients = [c for c in ok if c.id == target_id]
                if matches_clients:
                    if len(matches_clients) > 1:
                        errors.append(
                            {
                                "id": target_id,
                                "error_type": "DuplicateId",
                                "message": (
                                    "Несколько записей с id="
                                    f"{target_id} в исходном наборе; "
                                    "возвращаю первую"
                                ),
                            }
                        )
                    return matches_clients[0], errors

            errors.append(
                {
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": (
                        "Клиент с id=" f"{target_id} не найден ни в clean, ни в исходном файле"
                    ),
                }
            )
            return None, errors

        except FileNotFoundError:
            # _clean отсутствует — используем raw-валидацию как раньше
            ok, _ = self.read_all(tolerant=True)
            matches = [c for c in ok if c.id == target_id]
            if not matches:
                errors.append(
                    {
                        "id": target_id,
                        "error_type": "NotFound",
                        "message": (
                            "Клиент с id=" f"{target_id} не найден (clean-файл отсутствует)"
                        ),
                    }
                )
                return None, errors
            if len(matches) > 1:
                errors.append(
                    {
                        "id": target_id,
                        "error_type": "DuplicateId",
                        "message": (f"Несколько записей с id={target_id}; " "возвращаю первую"),
                    }
                )
            return matches[0], errors

    def get_k_n_short_list(
        self,
        k: int,
        n: int,
        *,
        prefer_contact: str = "phone",
    ) -> list[ClientShort]:
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

    def sort_by_last_name(self, ascending: bool = True) -> list[Client]:
        clean_path = self.derive_out_path(self.path, "_clean")
        try:
            records = self._read_array(clean_path)
            clients = [Client(rec) for rec in records]
        except FileNotFoundError:
            clients, _ = self.read_all(tolerant=True)
        return sorted(
            clients,
            key=lambda c: c.last_name,
            reverse=not ascending,
        )

    # -------------------------- Мутации набора -------------------------

    def add_client(
        self,
        data: Client | dict[str, Any] | str,
        *,
        pretty: bool = True,
    ) -> Client:
        try:
            records = self._read_array(self.path)
        except FileNotFoundError:
            records = []

        if isinstance(data, Client):
            new_client = data
        elif isinstance(data, (dict, str)):
            new_client = Client(data)
        else:
            raise TypeError("data должен быть Client, dict или str " "(JSON/YAML/строка с полями)")

        # Проверка дубликата по Client.__eq__ среди уже валидных записей
        existing_ok, _ = self.read_all(tolerant=True)
        dup_ids = [c.id for c in existing_ok if c == new_client]
        if dup_ids:
            raise ValueError(
                "DuplicateClient: такой клиент уже существует "
                f"(id={', '.join(map(str, dup_ids))})"
            )

        # Назначаем новый id = max(id) + 1 по исходному файлу
        existing_ids: list[int] = []
        for r in records:
            rid = (r or {}).get("id")
            try:
                if rid is not None:
                    existing_ids.append(int(rid))
            except Exception:
                # пропускаем нечисловые id
                pass
        new_id = (max(existing_ids) if existing_ids else 0) + 1

        new_client.id = new_id
        records.append(self.client_to_dict(new_client))
        self._write_array(self.path, records, pretty)
        return new_client

    def replace_by_id(
        self,
        target_id: int,
        data: Client | dict[str, Any] | str,
        *,
        pretty: bool = False,
    ) -> Client:
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
            raise TypeError("data должен быть Client, dict или str " "(JSON/YAML/строка с полями)")

        if new_client.id is not None and new_client.id != target_id:
            raise ValueError(f"MismatchedId: payload id={new_client.id} != target id={target_id}")

        existing_ok, _ = self.read_all(tolerant=True)
        dup_ids = [c.id for c in existing_ok if c.id != target_id and c == new_client]
        if dup_ids:
            raise ValueError(
                "DuplicateClient: такой клиент уже существует "
                f"(id={', '.join(map(str, dup_ids))})"
            )

        records = self._read_array(self.path)
        idxs: list[int] = []
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
            raise ValueError(
                "DuplicateId: найдено несколько записей с " f"id={target_id}; обновление отменено"
            )

        new_client.id = target_id
        records[idxs[0]] = self.client_to_dict(new_client)
        self._write_array(self.path, records, pretty)
        return new_client

    def delete_by_id(
        self,
        target_id: int,
        *,
        pretty: bool = True,
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        """
        Удаляет запись с указанным id из исходного файла (JSON/YAML).
        Возвращает (удалённый Client | None, errors).
        """
        if not isinstance(target_id, int):
            raise TypeError("id должен быть целым числом")

        errors: list[dict[str, Any]] = []

        try:
            records = self._read_array(self.path)
        except FileNotFoundError:
            errors.append(
                {
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": f"Файл {self.path} не найден",
                }
            )
            return None, errors

        idxs: list[int] = []
        for i, rec in enumerate(records):
            rec_id = (rec or {}).get("id", None)
            try:
                rec_id_norm = int(rec_id) if rec_id is not None else None
            except Exception:
                rec_id_norm = None
            if rec_id_norm == target_id:
                idxs.append(i)

        if not idxs:
            errors.append(
                {
                    "id": target_id,
                    "error_type": "NotFound",
                    "message": f"Клиент с id={target_id} не найден",
                }
            )
            return None, errors

        if len(idxs) > 1:
            errors.append(
                {
                    "id": target_id,
                    "error_type": "DuplicateId",
                    "message": (
                        "Найдено несколько записей с " f"id={target_id}; удаление отменено"
                    ),
                }
            )
            return None, errors

        idx = idxs[0]
        rec = records.pop(idx)
        self._write_array(self.path, records, pretty)

        try:
            deleted_client = Client(rec)
            return deleted_client, errors
        except Exception as exc:
            errors.append(
                {
                    "id": target_id,
                    "error_type": type(exc).__name__,
                    "message": f"Удалено, но запись невалидна: {str(exc)}",
                }
            )
            return None, errors

    def get_count(self) -> int:
        clean_path = self.derive_out_path(self.path, "_clean")
        try:
            return len(self._read_array(clean_path))
        except FileNotFoundError:
            ok, _ = self.read_all(tolerant=True)
            return len(ok)
