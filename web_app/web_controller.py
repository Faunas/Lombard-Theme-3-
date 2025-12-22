# web_controller.py
from __future__ import annotations
from typing import Any
from urllib.parse import parse_qs, urlencode

from mvc_observer import Observer
from observable_repo import ObservableClientsRepo
from web_views import index_view, detail_view, not_found_view
from client import Client


class MainController(Observer):
    """
    Вся логика в контроллере.
    View — только отрисовка, Model — репозиторий + сущности.
    Контроллер подписан на события репозитория (Observer).
    Теперь контроллер также собирает фильтр из query-параметров и дергает
    соответствующий декоратор (DB или файловый) для получения страницы списка.
    """

    def __init__(self, repo: ObservableClientsRepo) -> None:
        self.repo = repo
        self.repo.attach(self)
        self._selected_cache: dict[int, Client] = {}

    # Observer API
    def update(self, event: str, payload: Any) -> None:
        if event == "client_selected" and isinstance(payload, Client):
            if payload.id is not None:
                self._selected_cache[payload.id] = payload

    @staticmethod
    def _query(environ) -> dict[str, list[str]]:
        qs = environ.get("QUERY_STRING", "")
        return parse_qs(qs, keep_blank_values=True)

    @staticmethod
    def _redirect(start_response, location: str) -> list[bytes]:
        start_response("302 Found", [("Location", location)])
        return [b""]

    @staticmethod
    def _q_get(q: dict[str, list[str]], key: str, default: str = "") -> str:
        return (q.get(key, [default]) or [default])[0]

    @staticmethod
    def _safe_int(s: str, default: int) -> int:
        try:
            v = int(s)
            return v if v > 0 else default
        except Exception:
            return default

    def _make_filter(self, backend: str, q: dict[str, list[str]]):
        """
        backend: 'db' | 'file'
        Возвращает:
          - экземпляр ClientFilter (или FileClientFilter),
          - словарь echo-значений для view (для заполнения формы),
        """
        vals = {
            "ln": self._q_get(q, "ln"),
            "fn": self._q_get(q, "fn"),
            "mn": self._q_get(q, "mn"),
            "ph": self._q_get(q, "ph"),
            "em": self._q_get(q, "em"),
            "ps": self._q_get(q, "ps"),
            "pn": self._q_get(q, "pn"),
            "bd_from": self._q_get(q, "bd_from"),
            "bd_to": self._q_get(q, "bd_to"),
            "contact": self._q_get(q, "contact", "phone"),
        }

        def nz(s: str) -> str | None:
            s = (s or "").strip()
            return s if s else None

        if backend == "db":
            from db_filter_sort_decorator import ClientFilter
            flt = ClientFilter(
                last_name_substr=nz(vals["ln"]),
                first_name_substr=nz(vals["fn"]),
                middle_name_substr=nz(vals["mn"]),
                phone_substr=nz(vals["ph"]),
                email_substr=nz(vals["em"]),
                passport_series=nz(vals["ps"]),
                passport_number=nz(vals["pn"]),
                birth_date_from=nz(vals["bd_from"]),
                birth_date_to=nz(vals["bd_to"]),
            )
        else:
            from file_filter_sort_decorator import FileClientFilter
            flt = FileClientFilter(
                last_name_substr=nz(vals["ln"]),
                first_name_substr=nz(vals["fn"]),
                middle_name_substr=nz(vals["mn"]),
                phone_substr=nz(vals["ph"]),
                email_substr=nz(vals["em"]),
                passport_series=nz(vals["ps"]),
                passport_number=nz(vals["pn"]),
                birth_date_from=nz(vals["bd_from"]),
                birth_date_to=nz(vals["bd_to"]),
            )

        return flt, vals

    def _apply_filter_and_page(
        self,
        backend: str,
        k: int,
        n: int,
        flt_obj,
        prefer_contact: str = "phone",
    ):
        """
        Вызывает соответствующий декоратор (DB или файловый) и возвращает (shorts, total_count).
        """
        if backend == "db":
            from db_filter_sort_decorator import ClientsRepDBFilterSortDecorator
            deco = ClientsRepDBFilterSortDecorator(base_db_repo=self.repo.base_repo())
            shorts = deco.get_k_n_short_list(k, n, filter=flt_obj, sort=None, prefer_contact=prefer_contact)
            total = deco.get_count(filter=flt_obj)
            return shorts, total

        from file_filter_sort_decorator import ClientsRepFileFilterSortDecorator
        deco = ClientsRepFileFilterSortDecorator(self.repo.base_repo())
        shorts = deco.get_k_n_short_list(k, n, filter=flt_obj, sort=None, prefer_contact=prefer_contact)
        total = deco.get_count(filter=flt_obj)
        return shorts, total

    @staticmethod
    def _filters_to_query(filters: dict[str, str], *, include_page: bool = False, k: int = 1, n: int = 20) -> str:
        """
        Собирает query-строку из значений фильтра (пустые не включаем).
        Если include_page=True — добавляем k/n.
        """
        data: dict[str, str] = {}
        for key in ("ln", "fn", "mn", "ph", "em", "ps", "pn", "bd_from", "bd_to", "contact"):
            v = (filters.get(key) or "").strip()
            if v:
                data[key] = v
        if include_page:
            data["k"] = str(k)
            data["n"] = str(n)
        return urlencode(data, doseq=False)

    def index(self, environ, start_response) -> list[bytes]:
        """
        Теперь index обрабатывает фильтры:
          GET-параметры (query):
            ln, fn, mn, ph, em, ps, pn, bd_from, bd_to, contact
            k, n  — пагинация
        """
        q = self._query(environ)
        backend = self.repo.backend_kind()

        # пагинация
        k = self._safe_int(self._q_get(q, "k", "1"), 1)
        n = self._safe_int(self._q_get(q, "n", "20"), 20)
        if n > 200:
            n = 200

        error_msg: str | None = None

        try:
            flt_obj, echo_vals = self._make_filter(backend, q)
            prefer_contact = echo_vals.get("contact") or "phone"
            shorts, total = self._apply_filter_and_page(backend, k, n, flt_obj, prefer_contact=prefer_contact)
        except Exception as e:
            error_msg = str(e)
            echo_vals = {
                "ln": self._q_get(q, "ln"),
                "fn": self._q_get(q, "fn"),
                "mn": self._q_get(q, "mn"),
                "ph": self._q_get(q, "ph"),
                "em": self._q_get(q, "em"),
                "ps": self._q_get(q, "ps"),
                "pn": self._q_get(q, "pn"),
                "bd_from": self._q_get(q, "bd_from"),
                "bd_to": self._q_get(q, "bd_to"),
                "contact": self._q_get(q, "contact", "phone"),
            }
            shorts = []
            total = 0

        base_q = self._filters_to_query(echo_vals, include_page=False)
        prev_link = None
        next_link = None
        if k > 1:
            prev_link = "/?" + self._filters_to_query(echo_vals, include_page=True, k=k - 1, n=n)
        if (k - 1) * n + len(shorts) < total:
            next_link = "/?" + self._filters_to_query(echo_vals, include_page=True, k=k + 1, n=n)

        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [index_view(
            shorts=shorts,
            filters=echo_vals,
            total=total,
            page=k,
            page_size=n,
            prev_link=prev_link,
            next_link=next_link,
            error_msg=error_msg,
        )]

    def select(self, environ, start_response) -> list[bytes]:
        q = self._query(environ)
        try:
            cid = int(self._q_get(q, "id"))
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        try:
            self.repo.select_client(cid)
        except Exception as e:
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view(str(e))]

        return self._redirect(start_response, f"/client/detail?id={cid}")

    def detail(self, environ, start_response) -> list[bytes]:
        q = self._query(environ)
        try:
            cid = int(self._q_get(q, "id"))
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        c = self._selected_cache.get(cid)
        if not c:
            c, _ = self.repo.get_by_id(cid)
        if not c:
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view(f"id={cid} не найден")]

        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [detail_view(c)]
