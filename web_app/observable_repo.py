# observable_repo.py
from __future__ import annotations
from typing import Any, Optional

from mvc_observer import Subject
from base_clients_repo import BaseClientsRepo
from client import Client
from client_short import ClientShort


class ObservableClientsRepo(Subject):
    """
    Обёртка-Subject над любым BaseClientsRepo.
    Делегирует вызовы внутрь базового репо и генерирует события:
      - "list_ready"        -> payload: list[ClientShort]
      - "client_selected"   -> payload: Client
    """
    def __init__(self, base: BaseClientsRepo) -> None:
        super().__init__()
        self._base = base

    def list_all_short(self, *, prefer_contact: str = "phone") -> list[ClientShort]:
        try:
            shorts = self._base.get_k_n_short_list(1, 10**9, prefer_contact=prefer_contact)
        except Exception:
            ok, _ = self._base.read_all(tolerant=True)
            shorts = [ClientShort(self._base.client_to_dict(c), prefer_contact=prefer_contact) for c in ok]

        self.notify("list_ready", shorts)
        return shorts

    def select_client(self, cid: int) -> Client:
        obj, errs = self._base.get_by_id(cid, allow_raw_fallback=True)
        if not obj:
            raise ValueError(errs[0]["message"] if errs else f"Клиент id={cid} не найден")
        self.notify("client_selected", obj)
        return obj

    def get_by_id(self, cid: int) -> tuple[Client | None, list[dict[str, Any]]]:
        return self._base.get_by_id(cid, allow_raw_fallback=True)
