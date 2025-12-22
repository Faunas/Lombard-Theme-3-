from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from db_singleton import PgDB           # используем твой PgDB из ЛР2

@dataclass
class ContractFilter:
    number_substr: Optional[str] = None
    client_id: Optional[int] = None
    status: Optional[str] = None
    start_from: Optional[date] = None
    start_to: Optional[date] = None
    end_from: Optional[date] = None
    end_to: Optional[date] = None

@dataclass
class ContractSort:
    by: str = "id"       # id | number | end_date
    asc: bool = False

from contracts_lite_domain import Contract

class ContractsLiteRepo:
    _ALLOWED_SORT = {"id": "c.id", "number": "c.number", "end_date": "c.end_date"}

    def _where(self, flt: Optional[ContractFilter]) -> tuple[str, list[Any]]:
        if not flt: return "", []
        conds, p = [], []
        if flt.number_substr: conds += ["c.number ILIKE %s"]; p += [f"%{flt.number_substr}%"]
        if flt.client_id:     conds += ["c.client_id = %s"];   p += [flt.client_id]
        if flt.status:        conds += ["c.status = %s"];      p += [flt.status]
        if flt.start_from:    conds += ["c.start_date >= %s"]; p += [flt.start_from]
        if flt.start_to:      conds += ["c.start_date <= %s"]; p += [flt.start_to]
        if flt.end_from:      conds += ["c.end_date >= %s"];   p += [flt.end_from]
        if flt.end_to:        conds += ["c.end_date <= %s"];   p += [flt.end_to]
        return ("WHERE " + " AND ".join(conds), p) if conds else ("", [])

    def _order(self, sort: Optional[ContractSort]) -> str:
        if not sort: return "ORDER BY c.id DESC"
        col = self._ALLOWED_SORT.get((sort.by or "").lower(), "c.id")
        return f"ORDER BY {col} {'ASC' if sort.asc else 'DESC'}"

    @staticmethod
    def _row_to_contract(r: dict[str, Any]) -> Contract:
        return Contract(
            id=r["id"], number=r["number"], client_id=r["client_id"],
            principal=float(r["principal"]), status=r["status"],
            start_date=r["start_date"], end_date=r["end_date"],
            created_at=r.get("created_at"),
        )

    # ===== API =====
    def count(self, *, flt: Optional[ContractFilter] = None) -> int:
        wsql, p = self._where(flt)
        row = PgDB.get().fetch_one(f"SELECT COUNT(*) cnt FROM contracts c {wsql}", p)
        return int(row["cnt"]) if row else 0

    def get_k_n(self, k: int, n: int, *, flt: Optional[ContractFilter] = None,
                sort: Optional[ContractSort] = None) -> list[Contract]:
        if not (isinstance(k, int) and isinstance(n, int) and k > 0 and n > 0):
            raise ValueError("k,n должны быть > 0")
        wsql, p = self._where(flt)
        osql = self._order(sort)
        rows = PgDB.get().fetch_all(
            f"SELECT c.* FROM contracts c {wsql} {osql} LIMIT %s OFFSET %s",
            p + [n, (k-1)*n]
        )
        return [self._row_to_contract(r) for r in rows]

    def get_by_id(self, cid: int) -> Optional[Contract]:
        r = PgDB.get().fetch_one("SELECT * FROM contracts WHERE id=%s", [cid])
        return self._row_to_contract(r) if r else None

    def create(self, payload: dict[str, Any]) -> Contract:
        r = PgDB.get().execute_returning("""
          INSERT INTO contracts(number, client_id, principal, status, start_date, end_date)
          VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
          [payload["number"], payload["client_id"], payload["principal"],
           payload.get("status","Active"), payload["start_date"], payload["end_date"]]
        )
        return self._row_to_contract(r)

    def update(self, cid: int, payload: dict[str, Any]) -> Contract:
        r = PgDB.get().execute_returning("""
          UPDATE contracts SET number=%s, client_id=%s, principal=%s,
                 status=%s, start_date=%s, end_date=%s
          WHERE id=%s RETURNING *""",
          [payload["number"], payload["client_id"], payload["principal"],
           payload["status"], payload["start_date"], payload["end_date"], cid]
        )
        if not r: raise ValueError(f"NotFound: {cid}")
        return self._row_to_contract(r)

    def close(self, cid: int) -> Contract:
        r = PgDB.get().execute_returning(
            "UPDATE contracts SET status='Closed' WHERE id=%s RETURNING *", [cid]
        )
        if not r: raise ValueError(f"NotFound: {cid}")
        return self._row_to_contract(r)
