from typing import List, Tuple, Dict, Any
import yaml
from client import Client

class ClientsRepYaml:
    def __init__(self, path: str) -> None:
        self.path = path

    def read_array(self, path: str) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError("YAML должен быть массивом объектов (списком).")
        return data

    def read_all(self, tolerant: bool = False) -> Tuple[List[Client], List[Dict[str, Any]]]:
        records = self.read_array(self.path)

        ok: List[Client] = []
        errors: List[Dict[str, Any]] = []

        for idx, rec in enumerate(records):
            try:
                ok.append(Client(rec))
            except Exception as e:
                err = {
                    "index": idx,
                    "display_index": idx + 1,
                    "id": rec.get("id") if isinstance(rec, dict) else None,
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

    def render_report(self, ok: List[Client], errors: List[Dict[str, Any]], *, view: str = "short") -> str:
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


if __name__ == "__main__":
    repo = ClientsRepYaml("clients.yaml")
    clients, errs = repo.read_all(tolerant=True)
    print(repo.render_report(clients, errs, view="short"))
