# edit_controller.py
from __future__ import annotations

from typing import Any, Dict
from urllib.parse import parse_qs

from observable_repo import ObservableClientsRepo
from web_views import layout, ClientFormView, success_and_close, not_found_view


class EditClientController:
    """
    MVC-контроллер для редактирования клиента в отдельном окне/вкладке.
    GET  /client/edit?id=...   -> форма с предзаполненными полями
    POST /client/update        -> сохранение, при успехе postMessage + закрытие окна
    """

    def __init__(self, repo: ObservableClientsRepo) -> None:
        self.repo = repo
        self.view = ClientFormView()


    @staticmethod
    def _query(environ) -> Dict[str, list[str]]:
        return parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)

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


    def edit_form(self, environ, start_response):
        q = self._query(environ)
        try:
            cid = int(q.get("id", [""])[0])
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        client, errs = self.repo.get_by_id(cid)
        if not client:
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view(errs[0]["message"] if errs else f"id={cid} не найден")]

        values = {
            "last_name": client.last_name,
            "first_name": client.first_name,
            "middle_name": client.middle_name,
            "passport_series": client.passport_series,
            "passport_number": client.passport_number,
            "birth_date": client.birth_date,
            "phone": client.phone,
            "email": client.email,
            "address": client.address,
        }
        body_html = self.view.render(mode="edit", cid=client.id, values=values)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [layout("Редактирование клиента", body_html)]

    def update(self, environ, start_response):
        form = self._read_post(environ)
        try:
            cid = int(form.get("id", "") or "0")
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        payload = self._normalize(form)
        try:
            updated = self.repo.replace_by_id(cid, payload)
            try:
                self.repo.notify("client_updated", updated)
            except Exception:
                pass

            body_html = success_and_close(
                "Изменения сохранены",
                event_type="client_updated",
                payload={"id": cid},
            )
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
            return [layout("Успешно", body_html)]

        except Exception as e:
            body_html = self.view.render(mode="edit", cid=cid, values=payload, error=str(e))
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [layout("Ошибка валидации", body_html)]
