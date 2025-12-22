# add_controller.py
from __future__ import annotations

from urllib.parse import parse_qs
from typing import Any, Dict

from observable_repo import ObservableClientsRepo
from web_views import layout, ClientFormView, success_and_close


class AddClientController:
    """
    Отдельный контроллер для окна добавления клиента (MVC).
    GET  /client/add     -> форма (пустая)
    POST /client/create  -> создание, при успехе postMessage + закрытие окна.
    """

    def __init__(self, repo: ObservableClientsRepo) -> None:
        self.repo = repo
        self.view = ClientFormView()

    # --- helpers ---

    @staticmethod
    def _read_post(environ) -> Dict[str, str]:
        try:
            size = int(environ.get("CONTENT_LENGTH", "0") or 0)
        except ValueError:
            size = 0
        body = environ["wsgi.input"].read(size).decode("utf-8", errors="ignore")
        parsed = parse_qs(body, keep_blank_values=True)
        return {k: (v[0] if v else "") for k, v in parsed.items()}

    @staticmethod
    def _normalize(form: Dict[str, str]) -> Dict[str, Any]:
        return {
            "last_name": form.get("last_name", ""),
            "first_name": form.get("first_name", ""),
            "middle_name": form.get("middle_name", ""),
            "passport_series": form.get("passport_series", ""),
            "passport_number": form.get("passport_number", ""),
            "birth_date": form.get("birth_date", ""),
            "phone": form.get("phone", ""),
            "email": form.get("email", ""),
            "address": form.get("address", ""),
        }

    # --- actions ---

    def add_form(self, environ, start_response):
        body_html = self.view.render(mode="create")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [layout("Добавить клиента", body_html)]

    def create(self, environ, start_response):
        form = self._read_post(environ)
        payload = self._normalize(form)

        try:
            created = self.repo.add_client(payload)  # валидация внутри Client(...)
            try:
                self.repo.notify("client_added", created)  # опциональное серверное событие
            except Exception:
                pass

            body_html = success_and_close(
                "Клиент успешно добавлен",
                event_type="client_added",
                payload={"id": created.id},
            )
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
            return [layout("Успешно", body_html)]

        except Exception as e:
            body_html = self.view.render(mode="create", values=payload, error=str(e))
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [layout("Ошибка валидации", body_html)]
