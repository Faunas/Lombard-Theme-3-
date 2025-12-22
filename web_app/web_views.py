# web_views.py
from __future__ import annotations
from typing import Iterable, Optional
from html import escape
import json

from client_short import ClientShort
from client import Client



def layout(title: str, body_html: str) -> bytes:
    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<title>{escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {{
    --danger:#b00020;
    --muted:#666;
    --b:#ddd;
  }}
  body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid var(--b); padding: 8px; vertical-align: top; }}
  th {{ background: #fafafa; text-align: left; }}
  a.button {{ display:inline-block; padding:6px 10px; border:1px solid #555; border-radius:6px; text-decoration:none; }}
  a.button.danger {{ border-color: var(--danger); color: var(--danger); }}
  .muted {{ color:var(--muted); font-size: 90%; }}
  .grid {{ display:grid; grid-template-columns: repeat(2,minmax(220px,1fr)); gap:10px; }}
  .grid .full {{ grid-column: 1 / -1; }}
  label > span.req {{ color:var(--danger); margin-left:4px; }}
  input, select {{ width:100%; padding:6px 8px; box-sizing:border-box; }}
  button {{ padding:6px 12px; }}
  .btns > a {{ margin-right: 6px; }}
  .filters {{
    display:grid; grid-template-columns: repeat(4,minmax(180px,1fr)); gap:10px;
    border:1px solid var(--b); padding:12px; border-radius:8px; margin-bottom:14px;
  }}
  .filters .row {{ display:flex; flex-direction:column; gap:6px; }}
  .filters .row span {{ font-size:12px; color:#333; }}
  .filters .wide {{ grid-column: 1 / -1; }}
  .error {{ color:var(--danger); margin:8px 0; }}
  .flex {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  .pill {{ display:inline-block; border:1px solid var(--b); padding:4px 8px; border-radius:999px; font-size:12px; }}
  .right {{ margin-left:auto; }}
  .warnbox {{
    border:1px solid var(--danger); border-radius:8px; padding:12px; margin:12px 0; background:#fff5f6;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""
    return html.encode("utf-8")


def _esc(x: str | None) -> str:
    return escape(x or "", quote=True)


class ClientFormView:
    """
    Один класс окна формы. Разное поведение задаётся параметром mode:
      - mode="create": пустая форма, action=/client/create
      - mode="edit": предзаполненная форма, action=/client/update, нужен cid
    """

    def _form(
        self,
        *,
        title: str,
        action: str,
        submit_text: str,
        values: dict | None = None,
        error: str | None = None,
        hidden: dict | None = None,
    ) -> str:
        v = {
            "last_name": "", "first_name": "", "middle_name": "",
            "passport_series": "", "passport_number": "",
            "birth_date": "", "phone": "", "email": "", "address": "",
        }
        if values:
            for k in v:
                v[k] = (values.get(k) or "")

        def esc(x: str) -> str: return escape(x, quote=True)
        err_html = f'<div class="error">⚠ {escape(error)}</div>' if error else ""

        hidden_html = ""
        if hidden:
            hidden_html = "".join(
                f'<input type="hidden" name="{escape(k)}" value="{esc(str(hidden[k]))}">'
                for k in hidden.keys()
            )

        return f"""
<h1>{escape(title)}</h1>
{err_html}
<form method="POST" action="{escape(action)}">
  {hidden_html}
  <div class="grid">
    <label>Фамилия<span class="req">*</span><input name="last_name" required value="{esc(v['last_name'])}"></label>
    <label>Имя<span class="req">*</span><input name="first_name" required value="{esc(v['first_name'])}"></label>
    <label>Отчество<span class="req">*</span><input name="middle_name" required value="{esc(v['middle_name'])}"></label>
    <label>Серия паспорта<span class="req">*</span><input name="passport_series" maxlength="4" required value="{esc(v['passport_series'])}"></label>
    <label>Номер паспорта<span class="req">*</span><input name="passport_number" maxlength="6" required value="{esc(v['passport_number'])}"></label>
    <label>Дата рождения<span class="req">*</span><input name="birth_date" placeholder="ДД-ММ-ГГГГ" required value="{esc(v['birth_date'])}"></label>
    <label>Телефон<span class="req">*</span><input name="phone" required value="{esc(v['phone'])}"></label>
    <label>Email<span class="req">*</span><input name="email" required value="{esc(v['email'])}"></label>
    <label class="full">Адрес<span class="req">*</span><input name="address" required value="{esc(v['address'])}"></label>
  </div>
  <div style="margin-top:12px;">
    <button type="submit">{escape(submit_text)}</button>
    <button type="button" onclick="window.close()">Отмена</button>
  </div>
</form>
"""

    def render(
        self,
        *,
        mode: str,
        cid: int | None = None,
        values: dict | None = None,
        error: str | None = None,
    ) -> str:
        if mode == "create":
            return self._form(
                title="Новый клиент",
                action="/client/create",
                submit_text="Сохранить",
                values=values,
                error=error,
            )
        if mode == "edit":
            if cid is None:
                raise ValueError("Для mode='edit' требуется cid")
            return self._form(
                title=f"Редактирование клиента #{cid}",
                action="/client/update",
                submit_text="Сохранить изменения",
                values=values,
                error=error,
                hidden={"id": cid},
            )
        raise ValueError("mode должен быть 'create' или 'edit'")



def index_view(
    shorts: Iterable[ClientShort],
    *,
    filters: dict[str, str],
    total: int,
    page: int,
    page_size: int,
    prev_link: Optional[str],
    next_link: Optional[str],
    sort: dict[str, str],
    error_msg: Optional[str] = None,
) -> bytes:
    rows = []
    for s in shorts:
        cid = s.id if s.id is not None else "-"
        rows.append(
            "<tr>"
            f"<td>{cid}</td>"
            f"<td>{escape(s.last_name)} {escape(s.initials)}</td>"
            f"<td>{escape(s.contact)}</td>"
            f"<td class='muted'>{escape(s.passport)}</td>"
            "<td class='btns'>"
            f"<a class='button' target='_blank' href='/client/select?id={cid}'>Открыть</a>"
            f"<a class='button' data-popup='1' href='/client/edit?id={cid}'>Редактировать</a>"
            f"<a class='button danger' data-popup='1' href='/client/delete?id={cid}'>Удалить</a>"
            "</td>"
            "</tr>"
        )

    err_html = f"<div class='error'>⚠ {escape(error_msg)}</div>" if error_msg else ""

    sb = (sort.get("sb") or "id")
    sd = (sort.get("sd") or "asc")

    body = f"""
<h1>Клиенты (краткая информация)</h1>

<form method="GET" action="/" class="filters">
  <div class="row"><span>Фамилия (подстрока)</span><input name="ln" value="{_esc(filters.get('ln'))}"></div>
  <div class="row"><span>Имя (подстрока)</span><input name="fn" value="{_esc(filters.get('fn'))}"></div>
  <div class="row"><span>Отчество (подстрока)</span><input name="mn" value="{_esc(filters.get('mn'))}"></div>
  <div class="row"><span>Контакт для вывода</span>
    <input name="contact" list="contact_list" value="{_esc(filters.get('contact') or 'phone')}" />
    <datalist id="contact_list">
      <option value="phone" />
      <option value="email" />
    </datalist>
  </div>

  <div class="row"><span>Телефон (подстрока)</span><input name="ph" value="{_esc(filters.get('ph'))}"></div>
  <div class="row"><span>Email (подстрока)</span><input name="em" value="{_esc(filters.get('em'))}"></div>
  <div class="row"><span>Серия паспорта (=)</span><input name="ps" maxlength="4" value="{_esc(filters.get('ps'))}"></div>
  <div class="row"><span>Номер паспорта (=)</span><input name="pn" maxlength="6" value="{_esc(filters.get('pn'))}"></div>

  <div class="row"><span>ДР от (ДД-ММ-ГГГГ)</span><input name="bd_from" value="{_esc(filters.get('bd_from'))}"></div>
  <div class="row"><span>ДР до (ДД-ММ-ГГГГ)</span><input name="bd_to" value="{_esc(filters.get('bd_to'))}"></div>

  <div class="row"><span>Сортировать по</span>
    <select name="sb">
      <option value="id" {"selected" if sb=="id" else ""}>ID</option>
      <option value="last_name" {"selected" if sb=="last_name" else ""}>Фамилия</option>
      <option value="birth_date" {"selected" if sb=="birth_date" else ""}>Дата рождения</option>
    </select>
  </div>
  <div class="row"><span>Направление</span>
    <select name="sd">
      <option value="asc" {"selected" if sd=="asc" else ""}>По возрастанию</option>
      <option value="desc" {"selected" if sd=="desc" else ""}>По убыванию</option>
    </select>
  </div>

  <div class="row"><span>Страница</span><input name="k" value="{page}"></div>
  <div class="row"><span>Размер страницы</span><input name="n" value="{page_size}"></div>

  <div class="wide flex">
    <div class="flex">
      <button type="submit">Применить</button>
      <a class="button" href="/">Сбросить</a>
    </div>
    <div class="right muted">Найдено: <b>{total}</b></div>
  </div>
</form>

{err_html}

<p style="margin: 12px 0 18px;">
  <a class="button" id="btn-create" data-popup="1" href="/client/add">Добавить клиента</a>
  <span class="muted" style="margin-left:8px;">Откроется во всплывающем окне</span>
</p>

<table>
  <thead><tr><th>ID</th><th>ФИО</th><th>Контакт</th><th>Паспорт</th><th></th></tr></thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>

<div class="flex" style="margin-top:10px;">
  <span class="pill">Стр. {page}</span>
  <span class="pill">По {page_size}</span>
  <span class="pill">Всего {total}</span>
  <span class="right">
    {"<a class='button' href='" + escape(prev_link) + "'>&larr; Назад</a>" if prev_link else ""}
    {"<a class='button' href='" + escape(next_link) + "'>Вперёд &rarr;</a>" if next_link else ""}
  </span>
</div>

<script>
  (function() {{
    // Любую ссылку с data-popup="1" открываем во всплывающем окне
    var makePopup = function(a) {{
      a.addEventListener('click', function(e) {{
        e.preventDefault();
        window.open(this.href, this.getAttribute('data-name') || 'popup',
                    'width=860,height=760');
      }});
    }};
    var links = document.querySelectorAll('a[data-popup="1"]');
    for (var i=0;i<links.length;i++) makePopup(links[i]);

    // Слушаем события от попапов и перезагружаем список
    window.addEventListener('message', function(ev) {{
      if (ev.origin !== window.location.origin) return;
      var t = ev.data && ev.data.type;
      if (t === 'client_added' || t === 'client_updated' || t === 'client_deleted') {{
        window.location.reload();
      }}
    }});
  }})();
</script>
"""
    return layout("Главная — Клиенты", body)



def detail_view(c: Client) -> bytes:
    body = f"""
<h1>Карточка клиента</h1>
<p class='btns'>
  <a class='button' href='/'>&larr; На главную</a>
  <a class='button' data-popup='1' data-name='edit_client' href='/client/edit?id={c.id}'>Редактировать</a>
  <a class='button danger' data-popup='1' data-name='delete_client' href='/client/delete?id={c.id}'>Удалить</a>
</p>
<table>
  <tbody>
    <tr><th>ID</th><td>{c.id}</td></tr>
    <tr><th>Фамилия</th><td>{escape(c.last_name)}</td></tr>
    <tr><th>Имя</th><td>{escape(c.first_name)}</td></tr>
    <tr><th>Отчество</th><td>{escape(c.middle_name)}</td></tr>
    <tr><th>Дата рождения</th><td>{escape(c.birth_date)}</td></tr>
    <tr><th>Паспорт серия</th><td>{escape(c.passport_series)}</td></tr>
    <tr><th>Паспорт номер</th><td>{escape(c.passport_number)}</td></tr>
    <tr><th>Телефон</th><td>{escape(c.phone)}</td></tr>
    <tr><th>Email</th><td>{escape(c.email)}</td></tr>
    <tr><th>Адрес</th><td>{escape(c.address)}</td></tr>
  </tbody>
</table>

<script>
  (function() {{
    var links = document.querySelectorAll('a[data-popup="1"]');
    for (var i=0;i<links.length;i++) {{
      links[i].addEventListener('click', function(e) {{
        e.preventDefault();
        window.open(this.href, this.getAttribute('data-name') || 'popup',
                    'width=860,height=760');
      }});
    }}
    // Если из окна что-то прилетело — обновим карточку
    window.addEventListener('message', function(ev) {{
      if (ev.origin !== window.location.origin) return;
      var t = ev.data && ev.data.type;
      if (t === 'client_updated' || t === 'client_deleted' || t === 'client_added') {{
        window.location.reload();
      }}
    }});
  }})();
</script>
"""
    return layout("Карточка клиента", body)



def confirm_delete_view(
    c: Client | None,
    *,
    error: str | None = None,
    form_action: str = "/client/delete/confirm",
) -> str:
    """
    Окно подтверждения удаления.
    По умолчанию POST идет на /client/delete/confirm; при желании можно
    сменить на /client/remove через параметр form_action.
    """
    if not c:
        return f"<h1>Удаление</h1><p class='error'>Клиент не найден.</p>"

    err_html = f'<div class="error">⚠ {escape(error)}</div>' if error else ""
    fio = f"{c.last_name} {c.first_name} {c.middle_name}".strip()
    contact = c.phone or c.email or "—"

    return f"""
<h1>Удалить клиента #{c.id}?</h1>
<div class="warnbox">
  <div><b>{escape(fio)}</b></div>
  <div class="muted">Контакт: {escape(contact)}</div>
  <div class="muted">Паспорт: {escape(c.passport_series)} {escape(c.passport_number)}</div>
</div>
{err_html}
<form method="POST" action="{escape(form_action)}">
  <input type="hidden" name="id" value="{c.id}">
  <button type="submit" class="button danger">Удалить</button>
  <button type="button" class="button" onclick="window.close()">Отмена</button>
</form>
"""


def not_found_view(msg: str = "Not Found") -> bytes:
    return layout("404", f"<h1>404</h1><p>{escape(msg)}</p>")


def success_and_close(message: str, *, event_type: str = "client_added", payload: dict | None = None) -> str:
    data_js = json.dumps({"type": event_type, "payload": payload or {}}, ensure_ascii=False)
    return f"""
<h2>{escape(message)}</h2>
<p class="muted">Окно закроется автоматически. Если не закрылось — закройте вручную.</p>
<script>
  (function(){{
    try {{
      if (window.opener && !window.opener.closed) {{
        window.opener.postMessage({data_js}, window.location.origin);
      }}
    }} catch (e) {{}}
    window.close();
  }})();
</script>
"""
