# observable_repo.py
from __future__ import annotations
from typing import Any

from mvc_observer import Subject
from base_clients_repo import BaseClientsRepo
from client import Client
from client_short import ClientShort


class ObservableClientsRepo(Subject):
    """
    Обёртка-Subject над любым BaseClientsRepo.
    Делегирует вызовы внутрь базового репозитория и шлёт события наблюдателям.

    События:
      - "list_ready"      payload: list[ClientShort]  (когда готовы данные для таблицы)
      - "client_selected" payload: Client             (когда открыта карточка)
      - "client_added"    payload: Client
      - "client_updated"  payload: Client
      - "client_deleted"  payload: dict(id=..., ok=bool, errors=list)
    """

    def __init__(self, base: BaseClientsRepo) -> None:
        super().__init__()
        self._base = base

    # ===== служебные =====
    def base_repo(self) -> BaseClientsRepo:
        """Возвращает исходный (ненаблюдаемый) репозиторий."""
        return self._base

    # ===== Чтение списка для главной (без фильтра) =====
    def list_all_short(self, *, prefer_contact: str = "phone") -> list[ClientShort]:
        """
        Возвращает весь список (short) для таблицы и уведомляет "list_ready".
        """
        try:
            shorts = self._base.get_k_n_short_list(1, 10**9, prefer_contact=prefer_contact)
        except Exception:
            ok, _ = self._base.read_all(tolerant=True)  # для файловых репозиториев
            shorts = [
                ClientShort(self._base.client_to_dict(c), prefer_contact=prefer_contact)
                for c in ok
            ]

        self.notify("list_ready", shorts)
        return shorts

    # ===== Детальная карточка =====
    def select_client(self, cid: int) -> Client:
        """
        Возвращает клиента по id и уведомляет "client_selected".
        Совместимо и с файловыми репо, и с DB-адаптером.
        """
        try:
            obj, errs = self._base.get_by_id(cid, allow_raw_fallback=True)
        except TypeError:
            obj, errs = self._base.get_by_id(cid)

        if not obj:
            raise ValueError(errs[0]["message"] if errs else f"Клиент id={cid} не найден")

        self.notify("client_selected", obj)
        return obj

    # ===== CRUD =====
    def add_client(self, data: Client | dict | str, *, pretty: bool = True) -> Client:
        obj = self._base.add_client(data, pretty=pretty)
        self.notify("client_added", obj)
        self.notify("list_ready", self.list_all_short())
        return obj

    def replace_by_id(
        self, target_id: int, data: Client | dict | str, *, pretty: bool = True
    ) -> Client:
        obj = self._base.replace_by_id(target_id, data, pretty=pretty)
        self.notify("client_updated", obj)
        self.notify("list_ready", self.list_all_short())
        return obj

    def delete_by_id(
        self, target_id: int, *, pretty: bool = True
    ) -> tuple[Client | None, list[dict[str, Any]]]:
        deleted, errors = self._base.delete_by_id(target_id, pretty=pretty)
        self.notify("client_deleted", {"id": target_id, "ok": bool(deleted), "errors": errors})
        self.notify("list_ready", self.list_all_short())
        return deleted, errors

    # ===== Методы с фильтрацией/сортировкой (важно для ЛР3-6/7) =====
    def get_count(self, *, filter: Any | None = None) -> int:
        """
        Делегирует в базовый репозиторий. Если базовый не поддерживает filter,
        падаем обратно на вариант без фильтра.
        """
        try:
            return self._base.get_count(filter=filter)  # декораторы ЛР2/БД
        except TypeError:
            # Базовый адаптер без фильтра — считаем без него
            return self._base.get_count()

    def get_k_n_short_list(
        self,
        k: int,
        n: int,
        *,
        filter: Any | None = None,
        sort: Any | None = None,
        prefer_contact: str = "phone",
    ) -> list[ClientShort]:
        """
        Делегирует страницу списка в базовый репо. Если базовый не поддерживает filter/sort,
        отдаём без них (на практике мы оборачиваем адаптер в декоратор, см. web_app.py).
        """
        try:
            return self._base.get_k_n_short_list(
                k, n, filter=filter, sort=sort, prefer_contact=prefer_contact
            )
        except TypeError:
            return self._base.get_k_n_short_list(k, n, prefer_contact=prefer_contact)

    # ===== Прокси =====
    def get_by_id(self, cid: int) -> tuple[Client | None, list[dict[str, Any]]]:
        try:
            return self._base.get_by_id(cid, allow_raw_fallback=True)
        except TypeError:
            return self._base.get_by_id(cid)
