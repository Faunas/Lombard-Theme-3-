# web_views.py
from __future__ import annotations
from typing import Iterable
from html import escape

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
            f"<td><a class='button' target='_blank' href='/client/select?id={cid}'>Открыть</a></td>"
            "</tr>"
        )
    body = f"""
<h1>Клиенты (краткая информация)</h1>
<p class="muted">Клик «Открыть» — детальная карточка в новой вкладке.</p>
<table>
  <thead><tr><th>ID</th><th>ФИО</th><th>Контакт</th><th>Паспорт</th><th></th></tr></thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
"""
    return layout("Главная — Клиенты", body)


def detail_view(c: Client) -> bytes:
    body = f"""
<h1>Карточка клиента</h1>
<p><a class='button' href='/'>&larr; На главную</a></p>
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
"""
    return layout("Карточка клиента", body)


def not_found_view(msg: str = "Not Found") -> bytes:
    return layout("404", f"<h1>404</h1><p>{escape(msg)}</p>")
