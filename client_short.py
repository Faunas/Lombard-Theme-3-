from typing import Union
from client import Client


class ClientShort:
    """Короткая версия Клиента"""

    def __init__(self, source: Union[Client, dict, str], *, sep: str = ";", prefer_contact: str = "phone") -> None:
        """
        Короткая версия Клиента на основе полного Клиента.
        """

        # Привожу данные к объекту Client
        if isinstance(source, Client):
            c = source
        elif isinstance(source, dict):
            c = Client(source)
        elif isinstance(source, str):
            c = Client(source, sep=sep)
        else:
            raise TypeError("source должен быть Client, dict или str")

        # Поля короткой версии
        self.__last_name = c.last_name
        self.__initials = f"{c.first_name[0]}." + (f"{c.middle_name[0]}." if c.middle_name else "")
        self.__birth_date = c.birth_date
        self.__passport = f"{c.passport_series} {c.passport_number}"

        # Один дополнительный контакт
        if prefer_contact == "email":
            contact = c.email
        else:
            contact = c.phone
        self.__contact = contact

        self.__id = c.id

    # Свойства
    @property
    def id(self):
        return self.__id

    @property
    def last_name(self) -> str:
        return self.__last_name

    @property
    def initials(self) -> str:
        return self.__initials

    @property
    def birth_date(self) -> str:
        return self.__birth_date

    @property
    def passport(self) -> str:
        return self.__passport

    @property
    def contact(self) -> str:
        return self.__contact

    # Вывод
    def to_string(self) -> str:
        """Короткий вывод (Фамилия И.О., контакт, паспорт, дата)"""
        return f"{self.last_name} {self.initials}, {self.contact}; паспорт {self.passport}; {self.birth_date}"

    def __str__(self) -> str:
        return self.to_string()


if __name__ == "__main__":
    # 1. Создаю обычного клиента со всеми полями
    full_client1 = Client(
        last_name="Иванов",
        first_name="Иван",
        middle_name="Петрович",
        passport_series="1234",
        passport_number="567890",
        birth_date="01-01-1990",
        phone="+79991234567",
        email="ivanov@example.com",
        address="г. Москва, ул. Пушкина, д. 1",
    )
    short1 = ClientShort(full_client1) # Внутри уже создаётся клиент с урезанными полями
    print(short1)

    # Тест на вход строки

    # 1. без id (9 полей)
    short_from_str = ClientShort(
        "Иванов;Иван;Строкович;1234;567890;01-01-1990;+79990001122;ivanov@example.com;г. Москва"
    )
    print(short_from_str)

    # 2. с id (10 полей)
    short_from_str_with_id = ClientShort(
        "7;Петров;Пётр;Строкович;4321;098765;31-05-1985;89990001122;petrov@example.com;г. Казань"
    )
    print(short_from_str_with_id)

    # 3. строка с другим разделителем
    short_from_str_any_sep = ClientShort(
        "Сидоров|Сидор|Строкович|1111|222333|31-12-2000|+79995554433|sidorov@example.com|г. Екб",
        sep="|"
    )
    print(short_from_str_any_sep)

    # Тест на вход json

    json_text = (
        '{"last_name":"Романов","first_name":"Роман","middle_name":"Джсонович",'
        '"passport_series":"5555","passport_number":"666777","birth_date":"15-03-1993",'
        '"phone":"+79998887766","email":"romanov@example.com","address":"СПб"}'
    )
    short_from_json = ClientShort(json_text)
    print(short_from_json)

    short_from_json_email = ClientShort(json_text, prefer_contact="email")
    print(short_from_json_email)