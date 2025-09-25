from typing import Optional
from datetime import date
import re


class Client:
    """Класс Клиента"""

    # Валидация

    @staticmethod
    def _require_non_empty(name: str, value: str) -> str:
        """Требуем, чтобы не было пустых полей."""
        v = str(value).strip()
        if not v:
            raise ValueError(f"Поле '{name}' обязательно и не может быть пустым.")
        return v

    @staticmethod
    def validate_name_letters_only(field: str, value: str) -> str:
        """Только буквы. Без пробелов, дефисов и всякой фигни."""
        v = Client._require_non_empty(field, value)
        if not all(ch.isalpha() for ch in v):
            raise ValueError(f"Поле '{field}' может содержать только буквы (без пробелов и символов).")
        return v

    @staticmethod
    def validate_passport_series(value: str) -> str:
        """Убеждаемся что в серии паспорта только 4 символа и эти символы являются цифрами."""
        v = Client._require_non_empty("passport_series", value).replace(" ", "")
        if not (len(v) == 4 and v.isdigit()):
            raise ValueError("Поле 'passport_series' должно содержать ровно 4 цифры (например, '1234').")
        return v

    @staticmethod
    def validate_passport_number(value: str) -> str:
        """Убеждаемся что в номере паспорта только 6 символа и эти символы являются цифрами."""
        v = Client._require_non_empty("passport_number", value).replace(" ", "")
        if not (len(v) == 6 and v.isdigit()):
            raise ValueError("Поле 'passport_number' должно содержать ровно 6 цифр (например, '567890').")
        return v

    @staticmethod
    def validate_birth_date(value: str) -> str:
        """
        Проверяем на формат ДЕНЬ-МЕСЯЦ-ГОД, реально существующую дату
        """
        v = Client._require_non_empty("birth_date", value)
        # Убеждаемся что формат день-месяц-год
        if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", v):
            raise ValueError("Поле 'birth_date' должно быть в формате 'ДД-ММ-ГГГГ', например '01-01-1990'.")
        # Получаем дату от пользователя
        dd, mm, yyyy = map(int, v.split("-"))
        # Проверяем, а существует ли такая дата вообще?
        try:
            d = date(yyyy, mm,
                     dd)  # Если даты нет, то выбросит ValueError. Например, для 31-02-1990. В феврале только 28 дней, а передали 31.
        except ValueError:
            raise ValueError(f"Поле 'birth_date' содержит несуществующую дату: {v}.") from None
        # Проверяю, чтобы дата была не в будущем. (Заключаем договора всё-таки)
        if d > date.today():
            raise ValueError("Поле 'birth_date' не может указывать на будущую дату.")
        return f"{dd:02d}-{mm:02d}-{yyyy:04d}"

    @staticmethod
    def _clean_phone(raw: str) -> str:
        # Убираю все лишние символы из номера, кроме цифр - позволяет писать телефон в любом формате.
        return re.sub(r"[()\s\-]", "", str(raw))

    @staticmethod
    def validate_phone(value: str) -> str:
        """Разрешаем только два формата (после очистки скобок/пробелов/дефисов):
           1) +7XXXXXXXXXX (ровно 10 цифр после +7)
           2) 89XXXXXXXXX (ровно 10 цифр после 8; первая из них - 9)
        """
        v = Client._require_non_empty("phone", value)
        v = Client._clean_phone(v)
        # Ровно один '+' только в начале
        if v.count("+") > 1 or (v.count("+") == 1 and not v.startswith("+")):
            raise ValueError("Поле 'phone' имеет недопустимый '+'. Разрешён только ведущий '+'.")
        if re.fullmatch(r"\+7\d{10}", v):
            return v
        if re.fullmatch(r"8(9\d{9})", v):
            return v
        raise ValueError("Поле 'phone' должно быть: '+7XXXXXXXXXX' или '8XXXXXXXXXX' (после 8 — 9).")

    @staticmethod
    def validate_email(value: str) -> str:
        """Валидация email"""
        v = Client._require_non_empty("email", value)

        if v.count("@") != 1:
            raise ValueError("Поле 'email' должно содержать ровно один символ '@'.")
        local, domain = v.split("@", 1)

        # Локальная часть
        if local.startswith(".") or local.endswith("."):
            raise ValueError("Локальная часть email не может начинаться или заканчиваться точкой.")
        if ".." in local:
            raise ValueError("Локальная часть email не может содержать две точки подряд.")
        if not re.fullmatch(r"[A-Za-z0-9._%+\-]+", local):
            raise ValueError("Локальная часть email содержит недопустимые символы.")

        # Домен
        if domain.startswith(".") or domain.endswith("."):
            raise ValueError("Домен не может начинаться или заканчиваться точкой.")
        if ".." in domain:
            raise ValueError("Домен не может содержать две точки подряд.")
        labels = domain.split(".")
        if len(labels) < 2:
            raise ValueError("Домен должен содержать хотя бы одну точку (например, chipilino.fun).")
        label_re = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?$")
        for lab in labels:
            if not lab:
                raise ValueError("Домен содержит пустую метку (две точки подряд или точка на краю).")
            if not label_re.fullmatch(lab):
                raise ValueError("Метка домена содержит недопустимые символы или начинается/заканчивается дефисом.")
        if not re.fullmatch(r"[A-Za-z]{2,}", labels[-1]):
            raise ValueError("Доменная зона должна состоять минимум из двух букв.")
        return v

    @staticmethod
    def validate_address(value: str) -> str:
        """Валидация адреса. Просто проверка на 'Не пустой'"""
        return Client._require_non_empty("address", value)

    def __init__(
            self,
            id: Optional[int] = None,
            *,
            last_name: str,
            first_name: str,
            middle_name: str,
            passport_series: str,
            passport_number: str,
            birth_date: str,  # 'ДД-ММ-ГГГГ'
            phone: str,
            email: str,
            address: str,
    ) -> None:
        self.id = id
        self.last_name = last_name
        self.first_name = first_name
        self.middle_name = middle_name
        self.passport_series = passport_series
        self.passport_number = passport_number
        self.birth_date = birth_date
        self.phone = phone
        self.email = email
        self.address = address

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


if __name__ == "__main__":
    def print_client(c: "Client", title: str) -> None:
        print("=" * 60)
        print(title)
        print(f"id:               {c.id}")
        print(f"Фамилия:          {c.last_name}")
        print(f"Имя:              {c.first_name}")
        print(f"Отчество:         {c.middle_name}")
        print(f"Паспорт серия:    {c.passport_series}")
        print(f"Паспорт номер:    {c.passport_number}")
        print(f"Дата рождения:    {c.birth_date}")
        print(f"Телефон:          {c.phone}")
        print(f"Email:            {c.email}")
        print(f"Адрес:            {c.address}")
        print()


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
    print_client(client_ok, "Клиент OK")

    # client1 = Client(
    #     id=1,
    #     last_name="Иванов",
    #     first_name="Иван",
    #     middle_name="Петрович",
    #     passport_series="1234",
    #     passport_number="567890",
    #     birth_date="01-01-1990",
    #     phone="+7999123-45-67",
    #     email="ivanov@example.com",
    #     address="г. Москва, ул. Пушкина, д. 1"
    # )
    # print_client(client1, "Клиент 1 (полное заполнение)")

    # client2 = Client(
    #     last_name="Петров",
    #     first_name="Пётр",
    #     passport_series="4321",
    #     passport_number="098765",
    #     birth_date="20-05-1985"
    #
    # )
    # print_client(client2, "Клиент 2")
    #
    # client3 = Client()
    # client3.id = 3
    # client3.last_name = "Сидоров"
    # client3.first_name = "Сидор"
    # client3.middle_name = None
    # client3.passport_series = "1111"
    # client3.passport_number = "222333"
    # client3.birth_date = "31-12-2000"
    # client3.phone = "8 (912) 000-11-22"
    # client3.email = "sidorov@example.com"
    # client3.address = "г. Екатеринбург, ул. Ленина, д. 10"
    # print_client(client3, "Клиент 3 (заполнение через свойства)")
    #
    # client3.phone = "+7 912 000-11-22"
    # print_client(client3, "Клиент 3 (после изменения телефона)")

    # Тест валидации
    # t_client = Client(last_name="Иванов", first_name="Иван", passport_series="1234", passport_number="567890", birth_date="31-02-1990")  # Не существующая дата
    # t_client = Client(last_name="Иванов", first_name="Иван", passport_series="12a4", passport_number="567890", birth_date="01-01-1990")  # Буква в поле passport_series
    # t_client = Client(last_name="Иванов", first_name="Иван", passport_series="1234", passport_number="56789", birth_date="01-01-1990")   # Недостаток цифр в поле passport_number
    # t_client = Client(last_name="Ива-нов", first_name="Иван", passport_series="1234", passport_number="567890", birth_date="01-01-1990")   # Не разрешенный символ в поле last_name
    # t_client = Client(last_name="Иванов", first_name="Иван", passport_series="1234", passport_number="567890", birth_date="01-01-1990", phone="+7(999 ())()())(123    45-67")
    # t_client = Client(last_name="Иванов", first_name="Иван", passport_series="1234", passport_number="567890", birth_date="01-01-1990", email="petrov.mmm123@chipolino.fun.ru")
    t_client: Client | None = None
    if t_client:
        print_client(t_client, "Клиент TEST")
