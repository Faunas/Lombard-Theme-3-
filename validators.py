import re
from datetime import date


class Validator:
    """Общий класс валидации для полей Клиента."""

    # Валидация

    @staticmethod
    def require_non_empty(name: str, value: str) -> str:
        """Требуем, чтобы не было пустых полей."""
        v = str(value).strip()
        if not v:
            raise ValueError(f"Поле '{name}' обязательно и не может быть пустым.")
        return v

    @staticmethod
    def letters_only(field: str, value: str) -> str:
        """Только буквы. Без пробелов, дефисов и всякой фигни."""
        v = Validator.require_non_empty(field, value)
        if not all(ch.isalpha() for ch in v):
            raise ValueError(
                f"Поле '{field}' может содержать только буквы (без пробелов и символов)."
            )
        return v

    @staticmethod
    def passport_series(value: str) -> str:
        """Убеждаемся что в серии паспорта только 4 символа и эти символы являются цифрами."""
        v = Validator.require_non_empty("passport_series", value).replace(" ", "")
        if not (len(v) == 4 and v.isdigit()):
            raise ValueError(
                "Поле 'passport_series' должно содержать ровно 4 цифры (например, '1234')."
            )
        return v

    @staticmethod
    def passport_number(value: str) -> str:
        """Убеждаемся что в номере паспорта только 6 символов и эти символы являются цифрами."""
        v = Validator.require_non_empty("passport_number", value).replace(" ", "")
        if not (len(v) == 6 and v.isdigit()):
            raise ValueError(
                "Поле 'passport_number' должно содержать ровно 6 цифр (например, '567890')."
            )
        return v

    @staticmethod
    def birth_date_dd_mm_yyyy(value: str) -> str:
        """
        Проверяем на формат ДЕНЬ-МЕСЯЦ-ГОД, реально существующую дату.
        """
        v = Validator.require_non_empty("birth_date", value)
        # Убеждаемся что формат день-месяц-год
        if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", v):
            raise ValueError(
                "Поле 'birth_date' должно быть в формате 'ДД-ММ-ГГГГ', например '01-01-1990'."
            )
        # Получаем дату от пользователя
        dd, mm, yyyy = map(int, v.split("-"))
        # Проверяем, а существует ли такая дата вообще?
        try:
            d = date(
                yyyy, mm, dd
            )  # Если даты нет, то выбросит ValueError. Например, для 31-02-1990.
        except ValueError:
            raise ValueError(f"Поле 'birth_date' содержит несуществующую дату: {v}.") from None
        # Проверяю, чтобы дата была не в будущем. (Заключаем договора всё-таки)
        if d > date.today():
            raise ValueError("Поле 'birth_date' не может указывать на будущую дату.")
        return f"{dd:02d}-{mm:02d}-{yyyy:04d}"

    @staticmethod
    def _clean_phone(raw: str) -> str:
        # Убираю все лишние символы из номера, кроме цифр — позволяет писать телефон в любом формате.
        return re.sub(r"[()\s\-]", "", str(raw))

    @staticmethod
    def phone_ru_strict(value: str) -> str:
        """Разрешаем только два формата (после очистки скобок/пробелов/дефисов):
        1) +7XXXXXXXXXX (ровно 10 цифр после +7)
        2) 89XXXXXXXXX (ровно 10 цифр после 8; первая из них - 9)
        """
        v = Validator.require_non_empty("phone", value)
        v = Validator._clean_phone(v)
        # Ровно один '+' только в начале
        if v.count("+") > 1 or (v.count("+") == 1 and not v.startswith("+")):
            raise ValueError("Поле 'phone' имеет недопустимый '+'. Разрешён только ведущий '+'.")
        if re.fullmatch(r"\+7\d{10}", v):
            return v
        if re.fullmatch(r"8(9\d{9})", v):
            return v
        raise ValueError(
            "Поле 'phone' должно быть: '+7XXXXXXXXXX' или '8XXXXXXXXXX' (после 8 — 9)."
        )

    @staticmethod
    def email_strict(value: str) -> str:
        """Валидация email"""
        v = Validator.require_non_empty("email", value)

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
            raise ValueError("Домен должен содержать хотя бы одну точку (например, chipolino.fun).")
        label_re = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?$")
        for lab in labels:
            if not lab:
                raise ValueError(
                    "Домен содержит пустую метку (две точки подряд или точка на краю)."
                )
            if not label_re.fullmatch(lab):
                raise ValueError(
                    "Метка домена содержит недопустимые символы или начинается/заканчивается дефисом."
                )
        if not re.fullmatch(r"[A-Za-z]{2,}", labels[-1]):
            raise ValueError("Доменная зона должна состоять минимум из двух букв.")
        return v

    @staticmethod
    def address_required(value: str) -> str:
        """Валидация адреса. Просто проверка на 'Не пустой'"""
        return Validator.require_non_empty("address", value)
