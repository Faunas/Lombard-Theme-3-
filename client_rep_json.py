from typing import List, Tuple, Dict, Any, Union
import json
from client import Client

class ClientsRepJson:
    def __init__(self, path: str, wrapper_key: str | None = None) -> None:
        self.path = path
        self.wrapper_key = wrapper_key

    def _unwrap(self, data: Union[list, dict]) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            key = self.wrapper_key or "items"
            if key in data and isinstance(data[key], list):
                return data[key]
        raise ValueError("Некорректный JSON: нужен массив объектов или объект с ключом 'items'.")

    def read_all(self, tolerant: bool = False) -> Tuple[List[Client], List[Dict[str, Any]]]:
        """Читает файл и возвращает (ok, errors).
        ok: список успешно созданных Client
        errors: список словарей с деталями ошибки по каждому элементу с проблемной валидацией
        """
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        records = self._unwrap(raw)

        ok: List[Client] = []
        errors: List[Dict[str, Any]] = []

        for idx, rec in enumerate(records):
            try:
                ok.append(Client(rec))
            except Exception as e:
                err = {
                    "index": idx,                     # 0 - индекс в массиве
                    "display_index": idx + 1,         # 1 - человекочитаемые индекс
                    "id": rec.get("id", None),
                    "error_type": type(e).__name__,
                    "message": str(e),
                }
                if not tolerant:
                    where = f"элемент #{err['display_index']}"
                    if err["id"] is not None:
                        where += f" (id={err['id']})"
                    raise ValueError(f"Ошибка чтения {self.path}: {where}: {err['message']}") from e
                errors.append(err)

        return ok, errors

    # Форматирование отчёта с выводом успешных записей (short или full)
    def render_report(self, ok: List[Client], errors: List[Dict[str, Any]], *, view: str = "short") -> str:
        """
        Собирает отчёт.
        Можно выводить короткий отчет "short" (по умолчанию)
        Или полный отчет по клиентам full"
        """
        lines: List[str] = []
        lines.append(f"Загружено клиентов: {len(ok)}; ошибок: {len(errors)}")

        if ok:
            lines.append("Успешно загружены:")
            if view == "full":
                for c in ok:
                    cid = c.id if c.id is not None else "—"
                    lines.append(f"- id={cid}:\n{c.to_full_string()}")
            else:
                for c in ok:
                    cid = c.id if c.id is not None else "—"
                    lines.append(f"- id={cid}: {c}")

        if errors:
            lines.append("Ошибки:")
            for e in errors:
                hint = f"id={e['id']}" if e['id'] is not None else f"index={e['display_index']}"
                lines.append(f"- {hint}: {e['error_type']}: {e['message']}")

        return "\n".join(lines)


if __name__ == '__main__':
    repo = ClientsRepJson("clients.json")
    clients, errs = repo.read_all(tolerant=True)

    # Два варианта вывода "short" или "full"
    VIEW = "short"
    print(repo.render_report(clients, errs, view=VIEW))
