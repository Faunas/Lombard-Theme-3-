from __future__ import annotations
from urllib.parse import parse_qs
from datetime import date
from typing import Dict, Optional

from contracts_lite_repo import ContractsLiteRepo, ContractFilter, ContractSort
from contracts_lite_views import (
    contracts_index_view, contract_detail_view,
    simple_form_popup, success_and_close_popup,
)
from contracts_lite_name_service import attach_client_names, attach_client_name


def _qs(environ) -> Dict[str, list[str]]:
    return parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)

def _first(q: Dict[str, list[str]], key: str, default: str = "") -> str:
    return (q.get(key, [default]) or [default])[0]

def _to_int(s: str, default: int) -> int:
    try:
        v = int(s)
        return v if v > 0 else default
    except:
        return default

def _to_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s) if s else None
    except:
        return None


class ContractsLiteController:
    def __init__(self) -> None:
        self.repo = ContractsLiteRepo()

    # ===== list =====
    def index(self, environ, start_response):
        q = _qs(environ)
        k = _to_int(_first(q, "k"), 1)
        n = _to_int(_first(q, "n"), 10)

        filters_ui = {
            "num": _first(q, "num"),
            "client": _first(q, "client"),
            "st": _first(q, "st"),
            "sfrom": _first(q, "sfrom"),
            "sto": _first(q, "sto"),
            "efrom": _first(q, "efrom"),
            "eto": _first(q, "eto"),
        }
        flt = ContractFilter(
            number_substr=filters_ui["num"] or None,
            client_id=int(filters_ui["client"]) if (filters_ui["client"] or "").isdigit() else None,
            status=filters_ui["st"] or None,
            start_from=_to_date(filters_ui["sfrom"]),
            start_to=_to_date(filters_ui["sto"]),
            end_from=_to_date(filters_ui["efrom"]),
            end_to=_to_date(filters_ui["eto"]),
        )

        sb = (_first(q, "sb") or "id")
        sd = (_first(q, "sd") or "desc").lower()
        sort = ContractSort(by=sb, asc=(sd == "asc"))
        sort_ui = {"sb": sort.by, "sd": ("asc" if sort.asc else "desc")}

        total = self.repo.count(flt=flt)
        data = self.repo.get_k_n(k, n, flt=flt, sort=sort)

        # подставим ФИО клиентов пачкой
        attach_client_names(data)

        base = (f"/contracts?num={filters_ui['num']}&client={filters_ui['client']}&st={filters_ui['st']}"
                f"&sfrom={filters_ui['sfrom']}&sto={filters_ui['sto']}&efrom={filters_ui['efrom']}&eto={filters_ui['eto']}"
                f"&sb={sort_ui['sb']}&sd={sort_ui['sd']}&n={n}")
        prev_link = f"{base}&k={k-1}" if k > 1 else None
        next_link = f"{base}&k={k+1}" if k * n < total else None

        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [contracts_index_view(
            data,
            total=total, page=k, page_size=n,
            prev_link=prev_link, next_link=next_link,
            filters_ui=filters_ui, sort_ui=sort_ui,
        )]

    # ===== detail =====
    def detail(self, environ, start_response):
        q = _qs(environ)
        try:
            cid = int(_first(q, "id"))
        except:
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Bad id"]

        c = self.repo.get_by_id(cid)
        if not c:
            start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Not found"]

        # подставим имя клиента для детальной карточки
        attach_client_name(c)

        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [contract_detail_view(c)]

    # ===== add =====
    def add_form(self, environ, start_response):
        fields = """
<label>Номер<input name="number" required></label><br/>
<label>ID клиента<input name="client_id" required></label><br/>
<label>Сумма<input name="principal" required></label><br/>
<label>Статус<select name="status"><option>Active</option><option>Draft</option></select></label><br/>
<label>Начало (YYYY-MM-DD)<input name="start_date" required></label><br/>
<label>Окончание (YYYY-MM-DD)<input name="end_date" required></label>
"""
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [simple_form_popup("Создать договор", "/contract/create", fields, "Создать")]

    def create(self, environ, start_response):
        size = int(environ.get("CONTENT_LENGTH", "0") or 0)
        body = environ["wsgi.input"].read(size).decode("utf-8", "ignore")
        form = parse_qs(body, keep_blank_values=True)
        f = {k: (v[0] if v else "") for k, v in form.items()}

        payload = {
            "number": f.get("number", ""),
            "client_id": int(f.get("client_id", "0") or "0"),
            "principal": float(f.get("principal", "0") or "0"),
            "status": f.get("status", "Active"),
            "start_date": _to_date(f.get("start_date", "")),
            "end_date": _to_date(f.get("end_date", "")),
        }
        if not payload["start_date"] or not payload["end_date"]:
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Bad dates"]
        created = self.repo.create(payload)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [success_and_close_popup("contract_added", payload_js=f"{{id:{created.id}}}")]

    # ===== edit =====
    def edit_form(self, environ, start_response):
        q = _qs(environ)
        try:
            cid = int(_first(q, "id"))
        except:
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Bad id"]
        c = self.repo.get_by_id(cid)
        if not c:
            start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Not found"]
        fields = f"""
<input type="hidden" name="id" value="{c.id}">
<label>Номер<input name="number" value="{c.number}" required></label><br/>
<label>ID клиента<input name="client_id" value="{c.client_id}" required></label><br/>
<label>Сумма<input name="principal" value="{c.principal:.2f}" required></label><br/>
<label>Статус<select name="status">
  <option {"selected" if c.status=="Active" else ""}>Active</option>
  <option {"selected" if c.status=="Draft" else ""}>Draft</option>
  <option {"selected" if c.status=="Closed" else ""}>Closed</option>
</select></label><br/>
<label>Начало<input name="start_date" value="{c.start_date}" required></label><br/>
<label>Окончание<input name="end_date" value="{c.end_date}" required></label>
"""
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [simple_form_popup("Редактировать договор", "/contract/update", fields, "Сохранить")]

    def update(self, environ, start_response):
        size = int(environ.get("CONTENT_LENGTH", "0") or 0)
        body = environ["wsgi.input"].read(size).decode("utf-8", "ignore")
        form = parse_qs(body, keep_blank_values=True)
        f = {k: (v[0] if v else "") for k, v in form.items()}

        cid = int(f.get("id", "0") or "0")
        payload = {
            "number": f.get("number", ""),
            "client_id": int(f.get("client_id", "0") or "0"),
            "principal": float(f.get("principal", "0") or "0"),
            "status": f.get("status", "Active"),
            "start_date": _to_date(f.get("start_date", "")),
            "end_date": _to_date(f.get("end_date", "")),
        }
        if not payload["start_date"] or not payload["end_date"]:
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Bad dates"]
        self.repo.update(cid, payload)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [success_and_close_popup("contract_updated", payload_js=f"{{id:{cid}}}")]

    # ===== close =====
    def close_form(self, environ, start_response):
        q = _qs(environ)
        try:
            cid = int(_first(q, "id"))
        except:
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Bad id"]
        fields = f"""
<input type="hidden" name="id" value="{cid}">
<p>Подтвердите закрытие договора.</p>
"""
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [simple_form_popup("Закрыть договор", "/contract/close/do", fields, "Закрыть")]

    def close_do(self, environ, start_response):
        size = int(environ.get("CONTENT_LENGTH", "0") or 0)
        body = environ["wsgi.input"].read(size).decode("utf-8", "ignore")
        form = parse_qs(body, keep_blank_values=True)
        cid = int((form.get("id", ["0"])[0]) or "0")
        self.repo.close(cid)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [success_and_close_popup("contract_closed", payload_js=f"{{id:{cid}}}")]
