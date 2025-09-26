from typing import Union
from client import Client


class ClientShort(Client):
    """Короткая версия Клиента (наследуется от Client)"""

    def __init__(self, *args, prefer_contact: str = "phone", sep: str = ";", **kwargs) -> None:
        """
        Короткая версия Клиента на основе полного Клиента.
        """
        # запоминаю только выводимый контакт, а остальное прокидываю в инит родителя
        self.__prefer_contact = "email" if prefer_contact == "email" else "phone"
        super().__init__(*args, sep=sep, **kwargs)

    # Свойства

    @property
    def initials(self) -> str:
        return f"{self.first_name[0]}." + (f"{self.middle_name[0]}." if self.middle_name else "")

    @property
    def passport(self) -> str:
        return f"{self.passport_series} {self.passport_number}"

    @property
    def contact(self) -> str:
        return self.email if self.__prefer_contact == "email" else self.phone

    # Короткий вывод
    def to_string(self) -> str:
        """Короткий вывод (Фамилия И.О., контакт, паспорт, дата)"""
        return f"{self.last_name} {self.initials}, {self.contact}; паспорт {self.passport}; {self.birth_date}"

    def __str__(self) -> str:
        return self.to_string()


if __name__ == "__main__":
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
    print(ClientShort(full_client1))
    print(ClientShort(
        "7;Петров;Пётр;Иванович;4321;098765;31-05-1985;89990001122;petrov@example.com;г. Казань"
    ))
    print(ClientShort(
        '{"last_name":"Романов","first_name":"Роман","middle_name":"Сергеевич",'
        '"passport_series":"5555","passport_number":"666777","birth_date":"15-03-1993",'
        '"phone":"+79998887766","email":"romanov@example.com","address":"СПб"}',
        prefer_contact="email"
    ))
