# client.py
from __future__ import annotations

import json
from typing import Any

from client_short import ClientShort
from validators import Validator as V


class Client(ClientShort):
    """
    Полный клиент: наследует минимальные поля из ClientShort и ДОБАВЛЯЕТ:
    - passport_series, passport_number (отдельно),
    - phone, email (оба),
    - address.
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
        parts = [p.strip() for p in raw.split(sep)]
        if len(parts) == 9:
            id_val: int | None = None
            (ln, fn, mn, ps, pn, bd, ph, em, addr) = parts
        elif len(parts) == 10:
            id_str = parts[0]
            if not id_str.isdigit():
                raise ValueError(
                    "В формате со строкой первое поле (id) должно быть положительным целым числом."
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
            "address": addr,
        }

    def __init__(
        self,
        *args: Client | ClientShort | dict[str, Any] | str,
        id: int | None = None,
        last_name: str | None = None,
        first_name: str | None = None,
        middle_name: str | None = None,
        passport_series: str | None = None,
        passport_number: str | None = None,
        birth_date: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        sep: str = ";",
        prefer_contact: str = "phone",
    ) -> None:
        if len(args) > 1:
            raise TypeError(
                "Ожидаю не более одного позиционного аргумента (dict/str/Client/ClientShort)."
            )

        if len(args) == 1:
            src = args[0]
            if isinstance(src, Client):
                payload: dict[str, Any] = {
                    "id": src.id,
                    "last_name": src.last_name,
                    "first_name": src.first_name,
                    "middle_name": src.middle_name,
                    "passport_series": src.passport_series,
                    "passport_number": src.passport_number,
                    "birth_date": src.birth_date,
                    "phone": src.phone,
                    "email": src.email,
                    "address": src.address,
                }
            elif isinstance(src, ClientShort):
                # ClientShort НЕ хранит полные поля; их нужно передать явно
                if not (passport_series and passport_number and phone and email and address):
                    raise ValueError(
                        "При создании Client из ClientShort необходимо передать "
                        "passport_series, passport_number, phone, email и address."
                    )
                payload = {
                    "id": src.id,
                    "last_name": src.last_name,
                    "first_name": src.first_name,
                    "middle_name": src.middle_name,
                    "passport_series": passport_series,
                    "passport_number": passport_number,
                    "birth_date": src.birth_date,
                    "phone": phone,
                    "email": email,
                    "address": address,
                }
            elif isinstance(src, dict):
                payload = Client.from_kwargs(src)
            elif isinstance(src, str):
                txt = src.strip()
                try:
                    payload = Client.from_json(txt)
                except json.JSONDecodeError:
                    payload = Client.from_string(txt, sep=sep)
            else:
                raise TypeError(
                    "Неизвестный тип для создания Клиента. Должен быть dict, str, Client или ClientShort."
                )
        else:
            payload = Client.from_kwargs(
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
                    "address": address,
                }
            )

        # Обязательные поля (как раньше — включая address)
        required = [
            "last_name",
            "first_name",
            "middle_name",
            "passport_series",
            "passport_number",
            "birth_date",
            "phone",
            "email",
            "address",
        ]
        missing = [k for k in required if (k not in payload or payload[k] is None)]
        if missing:
            raise ValueError("Отсутствуют обязательные поля: " + ", ".join(missing))

        # Приводим к строкам перед валидацией — так mypy доволен и валидаторы получают str
        ln = V.letters_only("last_name", str(payload["last_name"]))
        fn = V.letters_only("first_name", str(payload["first_name"]))
        mn = V.letters_only("middle_name", str(payload["middle_name"]))
        ps = V.passport_series(str(payload["passport_series"]))
        pn = V.passport_number(str(payload["passport_number"]))
        bd = V.birth_date_dd_mm_yyyy(str(payload["birth_date"]))
        ph = V.phone_ru_strict(str(payload["phone"]))
        em = V.email_strict(str(payload["email"]))
        addr = V.address_required(str(payload["address"]))

        # id должен быть int | None
        raw_id = payload.get("id")
        id_val: int | None
        if raw_id is None:
            id_val = None
        elif isinstance(raw_id, int):
            id_val = raw_id
        elif isinstance(raw_id, str) and raw_id.isdigit():
            id_val = int(raw_id)
        else:
            raise ValueError("id должен быть int или числовой строкой.")

        # Сначала инициализируем «короткую» часть (сжатые поля)
        super().__init__(
            source=None,
            id=id_val,
            last_name=ln,
            first_name=fn,
            middle_name=mn,
            passport_series=ps,
            passport_number=pn,
            birth_date=bd,
            phone=ph,
            email=em,
            prefer_contact=prefer_contact,
        )

        # Затем сохраняем «полные» поля отдельно
        self.__passport_series = ps
        self.__passport_number = pn
        self.__phone = ph
        self.__email = em
        self.address = addr  # через setter (валидация уже прошла)

    # ===== Расширенные свойства =====
    @property
    def passport_series(self) -> str:
        return self.__passport_series

    @passport_series.setter
    def passport_series(self, value: str) -> None:
        self.__passport_series = V.passport_series(str(value))

    @property
    def passport_number(self) -> str:
        return self.__passport_number

    @passport_number.setter
    def passport_number(self, value: str) -> None:
        self.__passport_number = V.passport_number(str(value))

    @property
    def phone(self) -> str:
        return self.__phone

    @property
    def email(self) -> str:
        return self.__email

    @property
    def address(self) -> str:
        return self.__address

    @address.setter
    def address(self, value: str) -> None:
        self.__address = V.address_required(str(value))

    # ===== Сравнение (как раньше: адрес игнорируем) =====
    def _natural_key(self) -> tuple[str, str, str, str, str, str, str, str]:
        return (
            self.last_name,
            self.first_name,
            self.middle_name,
            self.birth_date,
            self.passport_series,
            self.passport_number,
            self.phone,
            self.email,
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Client):
            return self._natural_key() == other._natural_key()
        if isinstance(other, ClientShort):
            # Сравниваем по доступной части: ФИО+дата+паспорт (сжатый)
            return (
                self.last_name == other.last_name
                and self.first_name == other.first_name
                and self.middle_name == other.middle_name
                and self.birth_date == other.birth_date
                and f"{self.passport_series} {self.passport_number}" == other.passport
            )
        return NotImplemented

    # ===== Вывод =====
    def to_full_string(self) -> str:
        return (
            f"id:               {self.id}\n"
            f"Фамилия:          {self.last_name}\n"
            f"Имя:              {self.first_name}\n"
            f"Отчество:         {self.middle_name}\n"
            f"Паспорт серия:    {self.passport_series}\n"
            f"Паспорт номер:    {self.passport_number}\n"
            f"Дата рождения:    {self.birth_date}\n"
            f"Телефон:          {self.phone}\n"
            f"Email:            {self.email}\n"
            f"Адрес:            {self.address}"
        )

    def to_short_string(self) -> str:
        fio = f"{self.last_name} {self.first_name} {self.middle_name}"
        passport = f"{self.passport_series} {self.passport_number}"
        return f"{fio} ({self.birth_date}), паспорт {passport}"

    def __str__(self) -> str:
        return self.to_short_string()


if __name__ == "__main__":
    client_ok = Client(
        last_name="Иванов",
        first_name="Иван",
        middle_name="Петрович",
        passport_series="1234",
        passport_number="567890",
        birth_date="01-01-1990",
        phone="+79991234567",
        email="1petrov.mmm123@chipolino.fun.ru",
        address="г. Москва, ул. Пушкина, д. 1",
    )
    print("SHORT (Client):", client_ok)
    print("FULL:\n" + client_ok.to_full_string())

    another_client = Client(
        last_name="Иванов",
        first_name="Иван",
        middle_name="Петрович",
        passport_series="1234",
        passport_number="567890",
        birth_date="01-01-1990",
        phone="+79991234567",
        email="1petrov.mmm123@chipolino.fun.ru",
        address="г. Москва, ул. Пуkkkшкина, д. 1",
    )
    print("Сравнение:", "Одинаковые" if client_ok == another_client else "Разные")

    # Из короткого в полный
    short = ClientShort(
        "Петров;Пётр;Иванович;4321;098765;31-05-1985;89990001122;petrov@gmail.com;г. Казань",
        prefer_contact="email",
    )
    full_from_short = Client(
        short,
        passport_series="4321",
        passport_number="098765",
        phone="89990001122",
        email="petrov@gmail.com",
        address="г. Казань",
    )
    print("FROM SHORT FULL:\n", full_from_short.to_full_string())
