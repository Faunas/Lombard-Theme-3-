# web_controller.py
from __future__ import annotations
from typing import Callable, Dict, Any
from urllib.parse import parse_qs

from mvc_observer import Observer
from observable_repo import ObservableClientsRepo
from web_views import index_view, detail_view, not_found_view
from client import Client


class MainController(Observer):
    """
    Вся логика в контроллере.
    View — только отрисовка, Model — репозиторий + сущности.
    Контроллер подписан на события репозитория (Observer).
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

    # Helpers
    @staticmethod
    def _query(environ) -> dict[str, list[str]]:
        qs = environ.get("QUERY_STRING", "")
        return parse_qs(qs, keep_blank_values=True)

    @staticmethod
    def _redirect(start_response, location: str) -> list[bytes]:
        start_response("302 Found", [("Location", location)])
        return [b""]

    # Routes
    def index(self, environ, start_response) -> list[bytes]:
        # запрашиваем список; репозиторий при этом сгенерирует событие "list_ready"
        shorts = self.repo.list_all_short(prefer_contact="phone")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [index_view(shorts)]

    def select(self, environ, start_response) -> list[bytes]:
        q = self._query(environ)
        try:
            cid = int(q.get("id", [""])[0])
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
            cid = int(q.get("id", [""])[0])
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        # сначала пробуем взять из кэша, куда нас положил Observer
        c = self._selected_cache.get(cid)
        if not c:
            c, _ = self.repo.get_by_id(cid)
        if not c:
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view(f"id={cid} не найден")]

        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [detail_view(c)]
