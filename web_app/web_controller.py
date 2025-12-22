# web_controller.py
from __future__ import annotations
from typing import Callable, Tuple, Any, Dict, Optional
from urllib.parse import parse_qs, urlencode

from mvc_observer import Observer
from observable_repo import ObservableClientsRepo
from web_views import (
    index_view,
    detail_view,
    not_found_view,
)
from client import Client

# Фабрика "наблюдаемого" репозитория с поддержкой фильтра/сортировки (через DB-декоратор)
# Если захочешь подключить файлы (JSON/YAML), логика аналогичная — свой декоратор из ЛР2 для файлов.
from db_filter_sort_decorator import ClientsRepDBFilterSortDecorator, ClientFilter, SortSpec
from clients_rep_db_adapter import ClientsRepDBAdapter


DATA_BACKEND = "db"  # 'db' | потенциально 'json' / 'yaml' если добавишь позже

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lucky_db",
    "user": "postgres",
    "password": "123",
    "auto_migrate": True,
}


class FilteredRepoFactory:
    """
    Возвращает Observable-репозиторий, внутри которого DB-репозиторий
    обёрнут декоратором фильтра/сортировки из ЛР2.
    """
    @staticmethod
    def make() -> ObservableClientsRepo:
        if DATA_BACKEND == "db":
            base = ClientsRepDBAdapter(**DB_CONFIG)
            filtered = ClientsRepDBFilterSortDecorator(base)
            return ObservableClientsRepo(filtered)
        base = ClientsRepDBAdapter(**DB_CONFIG)
        filtered = ClientsRepDBFilterSortDecorator(base)
        return ObservableClientsRepo(filtered)


class MainController(Observer):
    """
    Вся логика в контроллере (MVC).
    View — только рендер, Model — репозиторий + сущности.
    Контроллер подписан на события репозитория (Observer).
    """

    def __init__(self, repo: ObservableClientsRepo) -> None:
        self.repo = repo
        self.repo.attach(self)
        self._selected_cache: dict[int, Client] = {}

    # ===== Observer =====
    def update(self, event: str, payload: Any) -> None:
        if event == "client_selected" and isinstance(payload, Client):
            if payload.id is not None:
                self._selected_cache[payload.id] = payload

    # ===== helpers =====
    @staticmethod
    def _query(environ) -> dict[str, list[str]]:
        return parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)

    @staticmethod
    def _first(params: dict[str, list[str]], key: str, default: str = "") -> str:
        return (params.get(key, [default]) or [default])[0]

    @staticmethod
    def _to_int(val: str, default: int) -> int:
        try:
            v = int(val)
            return v if v > 0 else default
        except Exception:
            return default

    @staticmethod
    def _build_link(base_path: str, params: dict[str, str]) -> str:
        clean = {k: v for k, v in params.items() if v not in (None, "", [])}
        return f"{base_path}?{urlencode(clean)}" if clean else base_path

    def _parse_filters(self, q: dict[str, list[str]]) -> tuple[ClientFilter, dict[str, str], str]:
        """
        Возвращает:
          - объект ClientFilter (для БД-декоратора),
          - "плоский" dict (для обратной подстановки в форму),
          - prefer_contact ('phone'|'email') для ClientShort.
        """
        filters_ui: dict[str, str] = {
            "ln": self._first(q, "ln"),         # last_name_substr
            "fn": self._first(q, "fn"),         # first_name_substr
            "mn": self._first(q, "mn"),         # middle_name_substr
            "ph": self._first(q, "ph"),         # phone_substr
            "em": self._first(q, "em"),         # email_substr
            "ps": self._first(q, "ps"),         # passport_series (=)
            "pn": self._first(q, "pn"),         # passport_number (=)
            "bd_from": self._first(q, "bd_from"),
            "bd_to": self._first(q, "bd_to"),
            "contact": self._first(q, "contact") or "phone",
        }

        flt = ClientFilter(
            last_name_substr=filters_ui["ln"] or None,
            first_name_substr=filters_ui["fn"] or None,
            middle_name_substr=filters_ui["mn"] or None,
            phone_substr=filters_ui["ph"] or None,
            email_substr=filters_ui["em"] or None,
            passport_series=filters_ui["ps"] or None,
            passport_number=filters_ui["pn"] or None,
            birth_date_from=filters_ui["bd_from"] or None,
            birth_date_to=filters_ui["bd_to"] or None,
        )

        prefer_contact = "email" if (filters_ui["contact"] or "").lower() == "email" else "phone"
        return flt, filters_ui, prefer_contact

    def _parse_sort(self, q: dict[str, list[str]]) -> tuple[SortSpec, dict[str, str]]:
        """
        Читает sb (sort_by) и sd (sort_dir) из query string.
        Допустимые поля: id | last_name | birth_date
        Направление: asc | desc
        """
        allowed_cols = {"id", "last_name", "birth_date"}
        by = self._first(q, "sb") or "id"
        if by not in allowed_cols:
            by = "id"

        dir_raw = (self._first(q, "sd") or "asc").lower()
        asc = False if dir_raw == "desc" else True

        ui = {"sb": by, "sd": "desc" if not asc else "asc"}
        return SortSpec(by=by, asc=asc), ui

    # ===== маршруты =====
    def index(self, environ, start_response) -> list[bytes]:
        q = self._query(environ)

        # пагинация
        page = self._to_int(self._first(q, "k"), 1)
        per_page = self._to_int(self._first(q, "n"), 10)

        # фильтры и сортировка
        flt, filters_ui, prefer_contact = self._parse_filters(q)
        sort_spec, sort_ui = self._parse_sort(q)

        # общее число по фильтру
        total = self.repo.get_count(filter=flt)

        # вытаскиваем нужную страницу
        shorts = self.repo.get_k_n_short_list(
            page, per_page, filter=flt, sort=sort_spec, prefer_contact=prefer_contact
        )

        # соберём ссылки для пагинации, сохраняя фильтры и сорт
        base_params = {
            **filters_ui,
            **sort_ui,
            "contact": filters_ui["contact"] or "phone",
            "n": str(per_page),
        }
        prev_link = None
        next_link = None
        if page > 1:
            prev_link = self._build_link("/", {**base_params, "k": str(page - 1)})
        if page * per_page < total:
            next_link = self._build_link("/", {**base_params, "k": str(page + 1)})

        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [index_view(
            shorts,
            filters=filters_ui,
            total=total,
            page=page,
            page_size=per_page,
            prev_link=prev_link,
            next_link=next_link,
            sort=sort_ui,
            error_msg=None,
        )]

    def select(self, environ, start_response) -> list[bytes]:
        q = self._query(environ)
        try:
            cid = int(self._first(q, "id"))
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        try:
            self.repo.select_client(cid)
        except Exception as e:
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view(str(e))]

        start_response("302 Found", [("Location", f"/client/detail?id={cid}")])
        return [b""]

    def detail(self, environ, start_response) -> list[bytes]:
        q = self._query(environ)
        try:
            cid = int(self._first(q, "id"))
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
