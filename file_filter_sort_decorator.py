from dataclasses import dataclass
from typing import Optional, List, Tuple, Any
from datetime import datetime, date

from base_clients_repo import BaseClientsRepo
from client import Client
from client_rep_json import ClientsRepJson
from client_short import ClientShort
from clients_rep_yaml import ClientsRepYaml


@dataclass
class FileClientFilter:
    # подстроковые
    last_name_substr: Optional[str] = None
    first_name_substr: Optional[str] = None
    middle_name_substr: Optional[str] = None
    phone_substr: Optional[str] = None
    email_substr: Optional[str] = None

    # точные совпадения
    passport_series: Optional[str] = None   # "1234"
    passport_number: Optional[str] = None   # "567890"

    # диапазон дат рождения (dd-mm-YYYY)
    birth_date_from: Optional[str] = None
    birth_date_to: Optional[str] = None


@dataclass
class SortSpec:
    by: str = "id"          # id | last_name | birth_date
    asc: bool = True


class ClientsRepFileFilterSortDecorator:
    """
    Декоратор, добавляющий фильтр и сортировку к методам:
      - get_k_n_short_list
      - get_count
    Поверх любого наследника BaseClientsRepo (JSON/YAML).
    """

    _ALLOWED_SORT = {
        "id": "id",
        "last_name": "last_name",
        "birth_date": "birth_date",
    }

    def __init__(self, base_repo: BaseClientsRepo) -> None:
        self._base = base_repo


    @staticmethod
    def _to_date(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        return datetime.strptime(s, "%d-%m-%Y").date()

    def _load_clients(self) -> List[Client]:
        """
        Загружаем список Client из _clean, если есть; иначе — из исходного файла c валидацией.
        Поведение согласовано с BaseClientsRepo.get_k_n_short_list().
        """
        clean_path = self._base.derive_out_path(self._base.path, "_clean")
        try:
            records = self._base._read_array(clean_path)
            clients = [Client(r) for r in records]
        except FileNotFoundError:
            clients, _ = self._base.read_all(tolerant=True)
        return clients

    @staticmethod
    def _case_contains(hay: Optional[str], needle: Optional[str]) -> bool:
        if not needle:
            return True
        return (hay or "").casefold().find(needle.casefold()) >= 0

    def _apply_filter(self, clients: List[Client], flt: Optional[FileClientFilter]) -> List[Client]:
        if not flt:
            return clients

        d_from = self._to_date(flt.birth_date_from)
        d_to = self._to_date(flt.birth_date_to)

        out: List[Client] = []
        for c in clients:
            # подстроки
            if not self._case_contains(c.last_name, flt.last_name_substr):
                continue
            if not self._case_contains(c.first_name, flt.first_name_substr):
                continue
            if not self._case_contains(c.middle_name, flt.middle_name_substr):
                continue
            if not self._case_contains(c.phone, flt.phone_substr):
                continue
            if not self._case_contains(c.email, flt.email_substr):
                continue

            # точные по паспорту
            if flt.passport_series and (c.passport_series or "").strip() != flt.passport_series:
                continue
            if flt.passport_number and (c.passport_number or "").strip() != flt.passport_number:
                continue

            # диапазон дат
            c_date = self._to_date(c.birth_date)
            if d_from and (not c_date or c_date < d_from):
                continue
            if d_to and (not c_date or c_date > d_to):
                continue

            out.append(c)
        return out

    def _apply_sort(self, clients: List[Client], sort: Optional[SortSpec]) -> List[Client]:
        if not sort:
            key = "id"
            asc = True
        else:
            key = self._ALLOWED_SORT.get((sort.by or "").lower(), "id")
            asc = bool(sort.asc)

        def kfunc(c: Client):
            if key == "id":
                return int(c.id or 0)
            if key == "last_name":
                return (c.last_name or "").casefold()
            if key == "birth_date":
                d = self._to_date(c.birth_date)
                # None отправим в конец при ASC и в начало при DESC
                return (d is None, d)
            return 0

        return sorted(clients, key=kfunc, reverse=not asc)

    # Ниже два метода по заданию.

    def get_k_n_short_list(
        self,
        k: int,
        n: int,
        *,
        filter: Optional[FileClientFilter] = None,
        sort: Optional[SortSpec] = None,
        prefer_contact: str = "phone",
    ) -> List[ClientShort]:
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k и n должны быть положительными целыми числами")

        clients = self._load_clients()
        clients = self._apply_filter(clients, filter)
        clients = self._apply_sort(clients, sort)

        start = (k - 1) * n
        end = start + n
        page = clients[start:end]

        return [ClientShort(self._base.client_to_dict(c), prefer_contact=prefer_contact) for c in page]

    def get_count(self, *, filter: Optional[FileClientFilter] = None) -> int:
        clients = self._load_clients()
        clients = self._apply_filter(clients, filter)
        return len(clients)


if __name__ == "__main__":
    repo_base: Optional[BaseClientsRepo] = None

    # Пытаемся работать с YAML, если нет, то с JSON
    if ClientsRepYaml is not None:
        try:
            repo_base = ClientsRepYaml("clients.yaml")
            ok, errs = repo_base.read_all(tolerant=True)
            repo_base.write_all_ok(ok)
        except FileNotFoundError:
            repo_base = None

    if repo_base is None and ClientsRepJson is not None:
        try:
            repo_base = ClientsRepJson("clients.json")
            ok, errs = repo_base.read_all(tolerant=True)
            repo_base.write_all_ok(ok)
        except FileNotFoundError:
            repo_base = None

    if repo_base is None:
        print("! Не найден ни clients.yaml, ни clients.json")
        raise SystemExit(1)

    deco = ClientsRepFileFilterSortDecorator(repo_base)

    # Пример 1: фамилия содержит "ов", сортировка по last_name ASC
    flt1 = FileClientFilter(last_name_substr="ов")
    sort1 = SortSpec(by="last_name", asc=True)
    print("\n== Пример 1: last_name ILIKE '%ов%', sort last_name ASC ==")
    page1 = deco.get_k_n_short_list(1, 5, filter=flt1, sort=sort1, prefer_contact="email")
    for s in page1:
        print("-", s)
    print("count:", deco.get_count(filter=flt1))

    # Пример 2: диапазон по дате рождения + сортировка по birth_date DESC
    flt2 = FileClientFilter(birth_date_from="01-01-1980", birth_date_to="31-12-2000")
    sort2 = SortSpec(by="birth_date", asc=False)
    print("\n== Пример 2: birth_date in [1980..2000], sort birth_date DESC ==")
    page2 = deco.get_k_n_short_list(1, 5, filter=flt2, sort=sort2)
    for s in page2:
        print("-", s)
    print("count:", deco.get_count(filter=flt2))

    # Пример 3: точная серия паспорта, сортировка по id ASC
    flt3 = FileClientFilter(passport_series="1234")
    print("\n== Пример 3: passport_series='1234', sort id ASC ==")
    page3 = deco.get_k_n_short_list(1, 10, filter=flt3)
    for s in page3:
        print("-", s)
    print("count:", deco.get_count(filter=flt3))
