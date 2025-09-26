from typing import Optional
from validators import Validator as V
import json


class Client:
    """Класс Клиента"""

    # Валидация

    @staticmethod
    def _require_non_empty(name: str, value: str) -> str:
        """Требуем, чтобы не было пустых полей."""
        return V.require_non_empty(name, value)

    @staticmethod
    def validate_name_letters_only(field: str, value: str) -> str:
        """Только буквы. Без пробелов, дефисов и всякой фигни."""
        return V.letters_only(field, value)

    @staticmethod
    def validate_passport_series(value: str) -> str:
        """Убеждаемся что в серии паспорта только 4 символа и эти символы являются цифрами."""
        return V.passport_series(value)

    @staticmethod
    def validate_passport_number(value: str) -> str:
        """Убеждаемся что в номере паспорта только 6 символа и эти символы являются цифрами."""
        return V.passport_number(value)

    @staticmethod
    def validate_birth_date(value: str) -> str:
        """
        Проверяем на формат ДЕНЬ-МЕСЯЦ-ГОД, реально существующую дату
        """
        return V.birth_date_dd_mm_yyyy(value)

    @staticmethod
    def _clean_phone(raw: str) -> str:
        # Убираю все лишние символы из номера, кроме цифр - позволяет писать телефон в любом формате.
        return V._clean_phone(raw)

    @staticmethod
    def validate_phone(value: str) -> str:
        """Разрешаем только два формата (после очистки скобок/пробелов/дефисов):
           1) +7XXXXXXXXXX (ровно 10 цифр после +7)
           2) 89XXXXXXXXX (ровно 10 цифр после 8; первая из них - 9)
        """
        return V.phone_ru_strict(value)

    @staticmethod
    def validate_email(value: str) -> str:
        """Валидация email"""
        return V.email_strict(value)

    @staticmethod
    def validate_address(value: str) -> str:
        """Валидация адреса. Просто проверка на 'Не пустой'"""
        return V.address_required(value)

    # Перегрузка конструктора

    @staticmethod
    def from_kwargs(data: dict) -> dict:
        """Инициализация из словаря"""
        return dict(data)

    @staticmethod
    def from_json(text: str) -> dict:
        """Инициализация из JSON-строки."""
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("JSON должен описывать объект ({}), а не список/значение.")
        return dict(obj)

    @staticmethod
    def from_string(raw: str, *, sep: str = ";") -> dict:
        """Строка с полями через разделитель.
        Без id: last_name;first_name;middle_name;passport_series;passport_number;birth_date;phone;email;address
        С id:  id;last_name;first_name;middle_name;passport_series;passport_number;birth_date;phone;email;address
        """
        parts = [p.strip() for p in raw.split(sep)]
        if len(parts) == 9:
            id_val = None
            (ln, fn, mn, ps, pn, bd, ph, em, addr) = parts
        elif len(parts) == 10:
            id_str = parts[0]
            if not id_str.isdigit():
                raise ValueError("В формате со строкой первое поле (id) должно быть положительным целым числом.")
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
            *args,                      # допускаем один из источников для создания (dict или str или Client)
            id: Optional[int] = None,
            last_name: Optional[str] = None,
            first_name: Optional[str] = None,
            middle_name: Optional[str] = None,
            passport_series: Optional[str] = None,
            passport_number: Optional[str] = None,
            birth_date: Optional[str] = None,   # 'ДД-ММ-ГГГГ'
            phone: Optional[str] = None,
            email: Optional[str] = None,
            address: Optional[str] = None,
            sep: str = ";",
    ) -> None:
        """
        Один __init__ с *args для перегрузки.
          - dict   - инициализация из словаря;
          - str    - пробуем JSON, иначе строка с разделителем;
          - Client - копирование полей.
        Иначе — используем именованные параметры.
        """

        if len(args) > 1:
            raise TypeError("Ожидаю не более одного аргумента (dict/str/Client).")

        if len(args) == 1:
            src = args[0]
            if isinstance(src, dict):
                payload = Client.from_kwargs(src)
            elif isinstance(src, Client):
                payload = {
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
            elif isinstance(src, str):
                txt = src.strip()
                try:
                    payload = Client.from_json(txt)
                except json.JSONDecodeError:
                    payload = Client.from_string(txt, sep=sep)
            else:
                raise TypeError("Неизвестный тип для создания Клиента. Должен быть dict, str или Class Client.")
        else:
            payload = Client.from_kwargs({
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
            })

        # Проверяем наличие обязательных полей
        required = [
            "last_name", "first_name", "middle_name",
            "passport_series", "passport_number", "birth_date",
            "phone", "email", "address",
        ]
        missing = [k for k in required if (k not in payload or payload[k] is None)]
        if missing:
            raise ValueError("Отсутствуют обязательные поля: " + ", ".join(missing))

        # Присваиваем через свойства
        self.id = payload.get("id")
        self.last_name = payload["last_name"]
        self.first_name = payload["first_name"]
        self.middle_name = payload["middle_name"]
        self.passport_series = payload["passport_series"]
        self.passport_number = payload["passport_number"]
        self.birth_date = payload["birth_date"]
        self.phone = payload["phone"]
        self.email = payload["email"]
        self.address = payload["address"]

    # Cвойства

    @property
    def id(self) -> Optional[int]:
        return self.__id

    @id.setter
    def id(self, value: Optional[int]) -> None:
        self.__id = value

    @property
    def last_name(self) -> str:
        return self.__last_name

    @last_name.setter
    def last_name(self, value: str) -> None:
        self.__last_name = Client.validate_name_letters_only("last_name", value)

    @property
    def first_name(self) -> str:
        return self.__first_name

    @first_name.setter
    def first_name(self, value: str) -> None:
        self.__first_name = Client.validate_name_letters_only("first_name", value)

    @property
    def middle_name(self) -> str:
        return self.__middle_name

    @middle_name.setter
    def middle_name(self, value: str) -> None:
        self.__middle_name = Client.validate_name_letters_only("middle_name", value)

    @property
    def passport_series(self) -> str:
        return self.__passport_series

    @passport_series.setter
    def passport_series(self, value: str) -> None:
        self.__passport_series = Client.validate_passport_series(value)

    @property
    def passport_number(self) -> str:
        return self.__passport_number

    @passport_number.setter
    def passport_number(self, value: str) -> None:
        self.__passport_number = Client.validate_passport_number(value)

    @property
    def birth_date(self) -> str:
        return self.__birth_date

    @birth_date.setter
    def birth_date(self, value: str) -> None:
        self.__birth_date = Client.validate_birth_date(value)

    @property
    def phone(self) -> str:
        return self.__phone

    @phone.setter
    def phone(self, value: str) -> None:
        self.__phone = Client.validate_phone(value)

    @property
    def email(self) -> str:
        return self.__email

    @email.setter
    def email(self, value: str) -> None:
        self.__email = Client.validate_email(value)

    @property
    def address(self) -> str:
        return self.__address

    @address.setter
    def address(self, value: str) -> None:
        self.__address = Client.validate_address(value)

    # Вывод

    def to_full_string(self) -> str:
        """Полная версия (все поля)."""
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
        """Краткая версия"""
        fio = f"{self.last_name} {self.first_name} {self.middle_name}"
        passport = f"{self.passport_series} {self.passport_number}"
        return f"{fio} ({self.birth_date}), паспорт {passport}"

    def __str__(self) -> str:
        """По умолчанию вывожу краткую версию."""
        return self.to_short_string()

    # Сравнение

    def _natural_key(self):
        """Натуральный ключ для сравнения без id и адреса."""
        return (
            self.last_name,
            self.first_name,
            self.middle_name,
            self.birth_date,
            self.passport_series,
            self.passport_number,
            self.phone,
            self.email,
            # self.address,
        )

    def __eq__(self, other: object) -> bool:
        """Сравнение объектов:
        Сравниваем по натуральному ключу (все поля без id)
        """
        if not isinstance(other, Client):
            return NotImplemented
        # Игнорируем id, сравниваем только содержимое
        return self._natural_key() == other._natural_key()



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
    #print_client(client_ok, "Клиент OK")

    # c_from_dict: Client | None = None
    # c_from_json: Client | None = None
    # c_from_str: Client | None = None
    #
    # # Примеры альтернативной инициализации:
    # c_from_dict = Client({"id":"1","last_name":"Петров","first_name":"Пётр","middle_name":"Иванович",
    #                       "passport_series":"4321","passport_number":"098765","birth_date":"31-05-1985",
    #                       "phone":"89990001122","email":"petrov@example.com","address":"г. Казань"})
    # c_from_json = Client('{"last_name":"Сидоров","first_name":"Сидор","middle_name":"Алексеевич",'
    #                      '"passport_series":"1111","passport_number":"222333","birth_date":"31-12-2000",'
    #                      '"phone":"+79990001122","email":"sidorov@example.com","address":"Екатеринбург"}')
    # c_from_str = Client("7;Романов;Роман;Сергеевич;5555;666777;15-03-1993;+79995554433;rom@example.com;СПб")


    # if c_from_dict:
    #     print_client(c_from_dict, "Клиент из словаря")
    # elif c_from_json:
    #     print_client(c_from_json, "Клиент из json")
    # elif c_from_str:
    #     print_client(c_from_str, "Клиент из Строки")

    # Полная и краткая версии выводов
    print("SHORT:", client_ok)
    print("FULL:\n" + client_ok.to_full_string())

    # Сравнение

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

    print("SHORT:", another_client)
    print("FULL:\n" + another_client.to_full_string())


    print("Результат сравнения двух Клиентов:", "Одинаковые" if client_ok == another_client else "Разные")

