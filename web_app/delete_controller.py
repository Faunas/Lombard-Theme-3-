# delete_controller.py
from __future__ import annotations

from typing import Dict
from urllib.parse import parse_qs

from observable_repo import ObservableClientsRepo
from web_views import layout, confirm_delete_view, success_and_close, not_found_view


class DeleteClientController:
    """
    Контроллер удаления клиента (MVC) во всплывающем окне.
    GET  /client/delete?id=...  -> окно подтверждения с краткой карточкой
    POST /client/remove         -> выполнение удаления, postMessage('client_deleted') + закрытие окна
    """

    def __init__(self, repo: ObservableClientsRepo) -> None:
        self.repo = repo

    # --- helpers ---

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

    # --- actions ---

    def confirm(self, environ, start_response):
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

        body_html = confirm_delete_view(client)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [layout("Удаление клиента", body_html)]

    def remove(self, environ, start_response):
        form = self._read_post(environ)
        try:
            cid = int(form.get("id", "") or "0")
        except Exception:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [not_found_view("Некорректный id")]

        # пытаемся удалить
        deleted, errors = self.repo.delete_by_id(cid)
        if not deleted:
            # показать окно подтверждения снова, но с ошибкой
            client, _ = self.repo.get_by_id(cid)  # мог уже удалиться, но раз нет deleted — попробуем показать
            body_html = confirm_delete_view(client, error=(errors[0]["message"] if errors else "Не удалось удалить"))
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [layout("Ошибка удаления", body_html)]

        # успех — уведомляем opener и закрываем окно
        try:
            # опционально дублируем серверное событие
            self.repo.notify("client_deleted", {"id": cid, "ok": True, "errors": []})
        except Exception:
            pass

        body_html = success_and_close(
            "Клиент удалён",
            event_type="client_deleted",
            payload={"id": cid},
        )
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [layout("Удалено", body_html)]
