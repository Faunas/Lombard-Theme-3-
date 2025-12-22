# web_app.py
from __future__ import annotations

from typing import Callable, Tuple
from wsgiref.simple_server import make_server

from observable_repo import ObservableClientsRepo
from web_controller import MainController
from web_views import layout


DATA_BACKEND = "db"  # 'db' | 'json' | 'yaml'

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lucky_db",
    "user": "postgres",
    "password": "123",
    "auto_migrate": True,
}

JSON_PATH = "clients.json"
YAML_PATH = "clients.yaml"


# ---------- фабрика базового репозитория ----------
def make_base_repo():
    """
    Возвращает один из репозиториев согласно DATA_BACKEND.
    """
    if DATA_BACKEND == "db":
        from clients_rep_db_adapter import ClientsRepDBAdapter

        return ClientsRepDBAdapter(**DB_CONFIG)

    if DATA_BACKEND == "yaml":
        from clients_rep_yaml import ClientsRepYaml

        return ClientsRepYaml(YAML_PATH)

    # по умолчанию json
    from client_rep_json import ClientsRepJson

    return ClientsRepJson(JSON_PATH)


def make_repo() -> ObservableClientsRepo:
    base = make_base_repo()
    return ObservableClientsRepo(base)


def application_factory() -> Tuple[Callable, MainController]:
    repo = make_repo()
    controller = MainController(repo)

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")

        if path in ("/", "/index"):
            return controller.index(environ, start_response)

        if path == "/client/select":
            return controller.select(environ, start_response)

        if path == "/client/detail":
            return controller.detail(environ, start_response)

        if path == "/debug/health":
            try:
                shorts = repo.list_all_short(prefer_contact="phone")
                body = (
                    "<h1>Health</h1>"
                    f"<p>Источник: <b>{DATA_BACKEND}</b></p>"
                    f"<p>Найдено записей: <b>{len(shorts)}</b></p>"
                )
                start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
                return [layout("Health", body)]
            except Exception as e:
                start_response(
                    "500 Internal Server Error",
                    [("Content-Type", "text/plain; charset=utf-8")],
                )
                return [f"Error: {e}".encode("utf-8")]

        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

    return app, controller


if __name__ == "__main__":
    app, _ = application_factory()
    with make_server("127.0.0.1", 8000, app) as httpd:
        print(
            "Web-приложение запущно по адресу: http://127.0.0.1:8000/  "
            f"(источник данных = {DATA_BACKEND})"
        )
        print("  / — список; 'Открыть' -> карточка в новой вкладке")
        print("  /debug/health — статус и счётчик")
        httpd.serve_forever()
