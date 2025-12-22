from __future__ import annotations
from html import escape
from typing import Iterable, Optional

from contracts_lite_domain import Contract
from web_views import layout

def _esc(x: object | None) -> str:
    return escape("" if x is None else str(x), quote=True)

def contracts_index_view(
    data: Iterable[Contract], *, total: int, page: int, page_size: int,
    prev_link: Optional[str], next_link: Optional[str],
    filters_ui: dict[str, str], sort_ui: dict[str, str],
) -> bytes:
    rows = []
    for c in data:
        # Если контроллер заранее подставил ФИО, показываем его; иначе — id
        client_cell = getattr(c, "client_name", None) or c.client_id
        rows.append(
            "<tr>"
            f"<td>{c.id}</td>"
            f"<td>{_esc(c.number)}</td>"
            f"<td>{_esc(client_cell)}</td>"
            f"<td>{c.principal:.2f}</td>"
            f"<td>{_esc(c.status)}</td>"
            f"<td>{_esc(c.end_date)}</td>"
            "<td>"
            f"<a class='button' target='_blank' href='/contract/detail?id={c.id}'>Открыть</a> "
            f"<a class='button' data-popup='1' href='/contract/edit?id={c.id}'>Изм.</a> "
            f"<a class='button danger' data-popup='1' href='/contract/close?id={c.id}'>Закрыть</a>"
            "</td>"
            "</tr>"
        )

    sb = sort_ui.get("sb","id"); sd = sort_ui.get("sd","desc")

    body = f"""
<h1>Договоры (Lite)</h1>

<form method="GET" action="/contracts" class="filters">
  <div class="row"><span>№ (подстрока)</span><input name="num" value="{_esc(filters_ui.get('num'))}"></div>
  <div class="row"><span>Клиент (id)</span><input name="client" value="{_esc(filters_ui.get('client'))}"></div>
  <div class="row"><span>Статус</span>
    <input name="st" list="st_list" value="{_esc(filters_ui.get('st'))}">
    <datalist id="st_list"><option value="Draft"/><option value="Active"/><option value="Closed"/></datalist>
  </div>
  <div class="row"><span>Начало от</span><input name="sfrom" placeholder="YYYY-MM-DD" value="{_esc(filters_ui.get('sfrom'))}"></div>
  <div class="row"><span>Начало до</span><input name="sto" placeholder="YYYY-MM-DD" value="{_esc(filters_ui.get('sto'))}"></div>
  <div class="row"><span>Окончание от</span><input name="efrom" placeholder="YYYY-MM-DD" value="{_esc(filters_ui.get('efrom'))}"></div>
  <div class="row"><span>Окончание до</span><input name="eto" placeholder="YYYY-MM-DD" value="{_esc(filters_ui.get('eto'))}"></div>

  <div class="row"><span>Сортировать по</span>
    <select name="sb">
      <option value="id" {"selected" if sb=="id" else ""}>ID</option>
      <option value="number" {"selected" if sb=="number" else ""}>Номер</option>
      <option value="end_date" {"selected" if sb=="end_date" else ""}>Окончание</option>
    </select>
  </div>
  <div class="row"><span>Направление</span>
    <select name="sd">
      <option value="asc" {"selected" if sd=="asc" else ""}>По возр.</option>
      <option value="desc" {"selected" if sd=="desc" else ""}>По убыв.</option>
    </select>
  </div>

  <div class="row"><span>Стр.</span><input name="k" value="{page}"></div>
  <div class="row"><span>По</span><input name="n" value="{page_size}"></div>

  <div class="wide">
    <button type="submit">Применить</button>
    <a class="button" href="/contracts">Сбросить</a>
    <a class="button" data-popup="1" href="/contract/add" style="margin-left:8px;">Создать</a>
    <span class="right muted">Найдено: <b>{total}</b></span>
  </div>
</form>

<table>
  <thead><tr><th>ID</th><th>№</th><th>Клиент</th><th>Сумма</th><th>Статус</th><th>До</th><th></th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>

<script>
(function(){{
  var links=document.querySelectorAll('a[data-popup="1"]');
  for (var i=0;i<links.length;i++) {{
    links[i].addEventListener('click', function(e) {{
      e.preventDefault();
      window.open(this.href, 'popup', 'width=860,height=760');
    }});
  }}
  window.addEventListener('message', function(ev){{
    if (ev.origin!==window.location.origin) return;
    var t=ev.data&&ev.data.type;
    if (t==='contract_added'||t==='contract_updated'||t==='contract_closed') window.location.reload();
  }});
}})();
</script>
"""
    return layout("Договоры (Lite)", body)

def contract_detail_view(c: Contract) -> bytes:
    client_cell = getattr(c, "client_name", None) or c.client_id
    body = f"""
<h1>Договор #{_esc(c.number)}</h1>
<p class='btns'>
  <a class='button' href='/contracts'>&larr; К списку</a>
  <a class='button' data-popup='1' href='/contract/edit?id={c.id}'>Редактировать</a>
  <a class='button danger' data-popup='1' href='/contract/close?id={c.id}'>Закрыть</a>
</p>
<table>
  <tbody>
    <tr><th>ID</th><td>{c.id}</td></tr>
    <tr><th>Клиент</th><td>{_esc(client_cell)}</td></tr>
    <tr><th>Сумма</th><td>{c.principal:.2f}</td></tr>
    <tr><th>Статус</th><td>{_esc(c.status)}</td></tr>
    <tr><th>Период</th><td>{_esc(c.start_date)} — {_esc(c.end_date)}</td></tr>
  </tbody>
</table>

<script>
(function(){{
  var links=document.querySelectorAll('a[data-popup="1"]');
  for (var i=0;i<links.length;i++) {{
    links[i].addEventListener('click', function(e){{
      e.preventDefault();
      window.open(this.href, 'popup', 'width=860,height=760');
    }});
  }}
  window.addEventListener('message', function(ev){{
    if (ev.origin!==window.location.origin) return;
    var t=ev.data&&ev.data.type;
    if (t==='contract_updated'||t==='contract_closed'||t==='contract_added') window.location.reload();
  }});
}})();
</script>
"""
    return layout("Договор (Lite)", body)

def simple_form_popup(title: str, action: str, fields_html: str, submit_text: str = "OK") -> bytes:
    body = f"""
<h2>{escape(title)}</h2>
<form method="POST" action="{escape(action)}">
  {fields_html}
  <div style="margin-top:10px;">
    <button type="submit">{escape(submit_text)}</button>
    <button type="button" onclick="window.close()">Отмена</button>
  </div>
</form>
"""
    return layout(title, body)

def success_and_close_popup(event_type: str, payload_js: str = "{}") -> bytes:
    body = f"""
<h2>Готово</h2>
<script>
  (function(){{
    try {{
      if (window.opener && !window.opener.closed) {{
        window.opener.postMessage({{type:'{event_type}', payload:{payload_js}}}, window.location.origin);
      }}
    }} catch(e) {{}}
    window.close();
  }})();
</script>
"""
    return layout("Готово", body)
