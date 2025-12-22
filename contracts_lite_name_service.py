from __future__ import annotations
from typing import Iterable, Dict, Any, Optional

from db_singleton import PgDB

def _fetch_client_names(ids: Iterable[int]) -> Dict[int, str]:
    ids_list = sorted({i for i in ids if isinstance(i, int)})
    if not ids_list:
        return {}
    placeholders = ", ".join(["%s"] * len(ids_list))
    sql = f"""
        SELECT
          id,
          TRIM(
            CONCAT(
              COALESCE(last_name, ''), ' ',
              COALESCE(first_name, ''), ' ',
              COALESCE(middle_name, '')
            )
          ) AS fio
        FROM clients
        WHERE id IN ({placeholders});
    """
    rows = PgDB.get().fetch_all(sql, ids_list)
    return {int(r["id"]): (r["fio"] or "") for r in rows}

def attach_client_names(contracts: Iterable[object]) -> None:
    ids = []
    for c in contracts:
        try:
            cid = getattr(c, "client_id", None)
            if isinstance(cid, int):
                ids.append(cid)
        except Exception:
            pass
    mapping = _fetch_client_names(ids)
    for c in contracts:
        try:
            cid = getattr(c, "client_id", None)
            if isinstance(cid, int) and cid in mapping:
                setattr(c, "client_name", mapping[cid])
        except Exception:
            pass

def attach_client_name(contract: object) -> None:
    try:
        cid = getattr(contract, "client_id", None)
        if not isinstance(cid, int):
            return
        mapping = _fetch_client_names([cid])
        if cid in mapping:
            setattr(contract, "client_name", mapping[cid])
    except Exception:
        pass
