# web_app.py
from __future__ import annotations

from typing import Callable, Tuple
from wsgiref.simple_server import make_server

from observable_repo import ObservableClientsRepo
from web_controller import MainController
from web_views import layout

# CRUD контроллеры
from add_controller import AddClientController
from edit_controller import EditClientController
from delete_controller import DeleteClientController
from contracts_lite_controller import ContractsLiteController

# Источник данных
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
    """
    Возвращает Observable-репозиторий.
    ВАЖНО: здесь же оборачиваем базовый репозиторий в декоратор фильтрации/сортировки,
    чтобы методы get_count()/get_k_n_short_list() принимали filter/sort.
    """
    base = make_base_repo()

    # Для БД — декоратор из ЛР2
    if DATA_BACKEND == "db":
        from db_filter_sort_decorator import ClientsRepDBFilterSortDecorator

        filtered = ClientsRepDBFilterSortDecorator(base)  # type: ignore[arg-type]
        return ObservableClientsRepo(filtered)  # type: ignore[arg-type]

    # Для файловых источников можно подключить свой файловый декоратор (если он у тебя есть)
    try:
        from file_filter_sort_decorator import ClientsRepFileFilterSortDecorator  # type: ignore
        filtered = ClientsRepFileFilterSortDecorator(base)  # type: ignore[arg-type]
        return ObservableClientsRepo(filtered)  # type: ignore[arg-type]
    except Exception:
        # Файловый декоратор отсутствует — работаем без фильтра/сортировки
        return ObservableClientsRepo(base)


def application_factory() -> Tuple[Callable, MainController]:
    repo = make_repo()
    controller = MainController(repo)
    add_ctrl = AddClientController(repo)
    edit_ctrl = EditClientController(repo)
    del_ctrl = DeleteClientController(repo)
    contracts_ctrl = ContractsLiteController()

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")

        if path in ("/", "/index"):
            return controller.index(environ, start_response)

        if path == "/client/select":
            return controller.select(environ, start_response)

        if path == "/client/detail":
            return controller.detail(environ, start_response)

        # Добавление
        if path == "/client/add":
            return add_ctrl.add_form(environ, start_response)
        if path == "/client/create":
            return add_ctrl.create(environ, start_response)

        # Редактирование
        if path == "/client/edit":
            return edit_ctrl.edit_form(environ, start_response)
        if path == "/client/update":
            return edit_ctrl.update(environ, start_response)

        # Удаление
        if path == "/client/delete":
            return del_ctrl.confirm(environ, start_response)
        if path == "/client/delete/confirm":
            return del_ctrl.do_delete(environ, start_response)

        # Договоры (Lite)
        if path == "/contracts":
            return contracts_ctrl.index(environ, start_response)
        if path == "/contract/detail":
            return contracts_ctrl.detail(environ, start_response)

        if path == "/contract/add":
            return contracts_ctrl.add_form(environ, start_response)
        if path == "/contract/create":
            return contracts_ctrl.create(environ, start_response)
        if path == "/contract/edit":
            return contracts_ctrl.edit_form(environ, start_response)
        if path == "/contract/update":
            return contracts_ctrl.update(environ, start_response)
        if path == "/contract/close":
            return contracts_ctrl.close_form(environ, start_response)
        if path == "/contract/close/do":
            return contracts_ctrl.close_do(environ, start_response)

        # Простой “healthcheck”
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
