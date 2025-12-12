# client_short.py
from __future__ import annotations

import json
from typing import Any

from validators import Validator


class ClientShort:
    """
    Короткий клиент: хранит только минимально нужное.
    Данные для входа валидируются по прежним правилам, но внутри
    мы держим сжатый набор.
    """

    @staticmethod
    def from_kwargs(data: dict[str, Any]) -> dict[str, Any]:
        return dict(data)

    @staticmethod
    def from_json(text: str) -> dict[str, Any]:
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("JSON должен описывать объект ({}), а не список/значение.")
        return dict(obj)

    @staticmethod
    def from_string(raw: str, *, sep: str = ";") -> dict[str, Any]:
        """
        Без id:
          last_name;first_name;middle_name;passport_series;passport_number;
          birth_date;phone;email;address

        С id:
          id;last_name;first_name;middle_name;passport_series;passport_number;
          birth_date;phone;email;address

        (address сохраняется в payload для совместимости, но в ClientShort НЕ хранится)
        """
        parts = [p.strip() for p in raw.split(sep)]
        if len(parts) == 9:
            id_val: int | None = None
            (ln, fn, mn, ps, pn, bd, ph, em, addr) = parts
        elif len(parts) == 10:
            id_str = parts[0]
            if not id_str.isdigit():
                raise ValueError(
                    "В формате со строкой первое поле (id) должно быть "
                    "положительным целым числом."
                )
            id_val = int(id_str)
            (ln, fn, mn, ps, pn, bd, ph, em, addr) = parts[1:]
        else:
            raise ValueError(f"Ожидаю 9 полей (без id) или 10 (с id), разделённых '{sep}'.")

        return {
            "id": id_val,
            "last_name": ln,
            "first_name": fn,
            "middle_name": mn,
            "passport_series": ps,
            "passport_number": pn,
            "birth_date": bd,
            "phone": ph,
            "email": em,
            "address": addr,  # для совместимости формата
        }

    def __init__(
        self,
        source: ClientShort | dict[str, Any] | str | None = None,
        *,
        sep: str = ";",
        prefer_contact: str = "phone",
        id: int | None = None,
        last_name: str | None = None,
        first_name: str | None = None,
        middle_name: str | None = None,
        passport_series: str | None = None,
        passport_number: str | None = None,
        birth_date: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> None:
        """
        Если передан source (ClientShort | dict | str(JSON/строка)) — используем его.
        Иначе берём именованные аргументы.
        """
        if source is not None:
            if isinstance(source, ClientShort):
                payload: dict[str, Any] = {
                    "id": source.id,
                    "last_name": source.last_name,
                    "first_name": source.first_name,
                    "middle_name": source.middle_name,
                    "passport_series": None,  # в short не хранится
                    "passport_number": None,  # в short не хранится
                    "birth_date": source.birth_date,
                    "phone": source.contact if source.contact_type == "phone" else None,
                    "email": source.contact if source.contact_type == "email" else None,
                    "address": None,
                }
            elif isinstance(source, dict):
                payload = ClientShort.from_kwargs(source)
            elif isinstance(source, str):
                txt = source.strip()
                try:
                    payload = ClientShort.from_json(txt)
                except json.JSONDecodeError:
                    payload = ClientShort.from_string(txt, sep=sep)
            else:
                raise TypeError("source должен быть ClientShort, dict или str")
        else:
            payload = ClientShort.from_kwargs(
                {
                    "id": id,
                    "last_name": last_name,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "passport_series": passport_series,
                    "passport_number": passport_number,
                    "birth_date": birth_date,
                    "phone": phone,
                    "email": email,
                }
            )

        # Проверяем обязательные входные поля
        required = [
            "last_name",
            "first_name",
            "middle_name",
            "passport_series",
            "passport_number",
            "birth_date",
            "phone",
            "email",
        ]
        missing = [k for k in required if (k not in payload or payload[k] is None)]
        if missing:
            raise ValueError(
                "Отсутствуют обязательные поля (короткий клиент): " + ", ".join(missing)
            )

        # Приводим к строкам перед валидацией — валидаторы ожидают str
        ln = Validator.letters_only("last_name", str(payload["last_name"]))
        fn = Validator.letters_only("first_name", str(payload["first_name"]))
        mn = Validator.letters_only("middle_name", str(payload["middle_name"]))
        ps = Validator.passport_series(str(payload["passport_series"]))
        pn = Validator.passport_number(str(payload["passport_number"]))
        bd = Validator.birth_date_dd_mm_yyyy(str(payload["birth_date"]))
        ph = Validator.phone_ru_strict(str(payload["phone"]))
        em = Validator.email_strict(str(payload["email"]))

        # Нормализуем id к int | None
        raw_id = payload.get("id")
        if raw_id is None:
            id_val: int | None = None
        elif isinstance(raw_id, int):
            id_val = raw_id
        elif isinstance(raw_id, str) and raw_id.isdigit():
            id_val = int(raw_id)
        else:
            raise ValueError("id должен быть int или числовой строкой.")

        # Сохраняем только короткие поля
        self.__id: int | None = id_val
        self.__last_name: str = ln
        self.__first_name: str = fn
        self.__middle_name: str = mn
        self.__birth_date: str = bd
        self.__passport: str = f"{ps} {pn}"

        self.__contact_type: str = "email" if prefer_contact == "email" else "phone"
        self.__contact: str = em if self.__contact_type == "email" else ph

    # ===== Свойства (только короткие) =====
    @property
    def id(self) -> int | None:
        return self.__id

    @id.setter
    def id(self, value: int | None) -> None:
        self.__id = value

    @property
    def last_name(self) -> str:
        return self.__last_name

    @property
    def first_name(self) -> str:
        return self.__first_name

    @property
    def middle_name(self) -> str:
        return self.__middle_name

    @property
    def birth_date(self) -> str:
        return self.__birth_date

    @property
    def passport(self) -> str:
        return self.__passport

    @property
    def contact(self) -> str:
        return self.__contact

    @property
    def contact_type(self) -> str:
        # "phone" или "email"
        return self.__contact_type

    # Производные
    @property
    def initials(self) -> str:
        mid = f"{self.middle_name[0]}." if self.middle_name else ""
        return f"{self.first_name[0]}.{mid}"

    # Вывод
    def to_string(self) -> str:
        return (
            f"{self.last_name} {self.initials}, {self.contact}; "
            f"паспорт {self.passport}; {self.birth_date}"
        )

    def __str__(self) -> str:
        return self.to_string()
