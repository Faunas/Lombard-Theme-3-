from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Literal

ContractStatus = Literal["Draft", "Active", "Closed"]

@dataclass(slots=True)
class Contract:
    id: Optional[int]
    number: str
    client_id: int
    principal: float
    status: ContractStatus
    start_date: date
    end_date: date
    created_at: Optional[datetime] = None
    client_name: Optional[str] = None
