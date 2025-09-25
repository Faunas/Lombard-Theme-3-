from typing import Optional


class Client:
    """Класс Клиента"""

    def __init__(
            self,
            id: Optional[int] = None,
            last_name: str = "",
            first_name: str = "",
            middle_name: Optional[str] = None,
            passport_series: str = "",
            passport_number: str = "",
            birth_date: str = "",
            phone: Optional[str] = None,
            email: Optional[str] = None,
            address: Optional[str] = None,
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
        self.__last_name = value

    @property
    def first_name(self) -> str:
        return self.__first_name

    @first_name.setter
    def first_name(self, value: str) -> None:
        self.__first_name = value

    @property
    def middle_name(self) -> Optional[str]:
        return self.__middle_name

    @middle_name.setter
    def middle_name(self, value: Optional[str]) -> None:
        self.__middle_name = value

    @property
    def passport_series(self) -> str:
        return self.__passport_series

    @passport_series.setter
    def passport_series(self, value: str) -> None:
        self.__passport_series = value

    @property
    def passport_number(self) -> str:
        return self.__passport_number

    @passport_number.setter
    def passport_number(self, value: str) -> None:
        self.__passport_number = value

    @property
    def birth_date(self) -> str:
        return self.__birth_date

    @birth_date.setter
    def birth_date(self, value: str) -> None:
        self.__birth_date = value

    @property
    def phone(self) -> Optional[str]:
        return self.__phone

    @phone.setter
    def phone(self, value: Optional[str]) -> None:
        self.__phone = value

    @property
    def email(self) -> Optional[str]:
        return self.__email

    @email.setter
    def email(self, value: Optional[str]) -> None:
        self.__email = value

    @property
    def address(self) -> Optional[str]:
        return self.__address

    @address.setter
    def address(self, value: Optional[str]) -> None:
        self.__address = value


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

    client1 = Client(
        id=1,
        last_name="Иванов",
        first_name="Иван",
        middle_name="Петрович",
        passport_series="1234",
        passport_number="567890",
        birth_date="1990-01-01",
        phone="+7999123-45-67",
        email="ivanov@example.com",
        address="г. Москва, ул. Пушкина, д. 1"
    )
    print_client(client1, "Клиент 1 (полное заполнение)")

    # client2 = Client(
    #     last_name="Петров",
    #     first_name="Пётр",
    #     passport_series="4321",
    #     passport_number="098765",
    #     birth_date="1985-05-20"
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
    # client3.birth_date = "2000-12-31"
    # client3.phone = "8 (912) 000-11-22"
    # client3.email = "sidorov@example.com"
    # client3.address = "г. Екатеринбург, ул. Ленина, д. 10"
    # print_client(client3, "Клиент 3 (заполнение через свойства)")
    #
    # client3.phone = "+7 912 000-11-22"
    # print_client(client3, "Клиент 3 (после изменения телефона)")
