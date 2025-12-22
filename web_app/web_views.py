# web_views.py
from __future__ import annotations
from typing import Iterable
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
  body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; }}
  th {{ background: #fafafa; text-align: left; }}
  a.button {{ display:inline-block; padding:6px 10px; border:1px solid #555; border-radius:6px; text-decoration:none; }}
  .muted {{ color:#666; font-size: 90%; }}
  .grid {{ display:grid; grid-template-columns: repeat(2,minmax(220px,1fr)); gap:10px; }}
  .grid .full {{ grid-column: 1 / -1; }}
  label > span.req {{ color:#b00020; margin-left:4px; }}
  input {{ width:100%; padding:6px 8px; box-sizing:border-box; }}
  button {{ padding:6px 12px; }}
  .btns > a {{ margin-right: 6px; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""
    return html.encode("utf-8")


def index_view(shorts: Iterable[ClientShort]) -> bytes:
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
            "</td>"
            "</tr>"
        )

    body = f"""
<h1>Клиенты (краткая информация)</h1>

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
    // Если из окна редактирования прилетело событие — обновим карточку
    window.addEventListener('message', function(ev) {{
      if (ev.origin !== window.location.origin) return;
      var t = ev.data && ev.data.type;
      if (t === 'client_updated') {{
        window.location.reload();
      }}
    }});
  }})();
</script>
"""
    return layout("Карточка клиента", body)


def not_found_view(msg: str = "Not Found") -> bytes:
    return layout("404", f"<h1>404</h1><p>{escape(msg)}</p>")



def add_client_form(*, values: dict | None = None, error: str | None = None) -> str:
    v = {
        "last_name": "", "first_name": "", "middle_name": "",
        "passport_series": "", "passport_number": "",
        "birth_date": "", "phone": "", "email": "", "address": "",
    }
    if values:
        for k in v: v[k] = (values.get(k) or "")

    def esc(x: str) -> str: return escape(x, quote=True)
    err_html = f'<div style="color:#b00020;margin:8px 0;">⚠ {escape(error)}</div>' if error else ""

    return f"""
<h1>Новый клиент</h1>
{err_html}
<form method="POST" action="/client/create">
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
    <button type="submit">Сохранить</button>
    <button type="button" onclick="window.close()">Отмена</button>
  </div>
</form>
"""



def edit_client_form(cid: int, *, values: dict | None = None, error: str | None = None) -> str:
    v = {
        "last_name": "", "first_name": "", "middle_name": "",
        "passport_series": "", "passport_number": "",
        "birth_date": "", "phone": "", "email": "", "address": "",
    }
    if values:
        for k in v: v[k] = (values.get(k) or "")

    def esc(x: str) -> str: return escape(x, quote=True)
    err_html = f'<div style="color:#b00020;margin:8px 0;">⚠ {escape(error)}</div>' if error else ""

    return f"""
<h1>Редактирование клиента #{cid}</h1>
{err_html}
<form method="POST" action="/client/update">
  <input type="hidden" name="id" value="{cid}">
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
    <button type="submit">Сохранить изменения</button>
    <button type="button" onclick="window.close()">Отмена</button>
  </div>
</form>
"""


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
