from datetime import date


MINIMUM_SERVICE_AGE = 15
MAXIMUM_MATCHING_AGE = 99


def age_on(birth_date: date, today: date | None = None) -> int:
    reference_date = today or date.today()
    return reference_date.year - birth_date.year - (
        (reference_date.month, reference_date.day)
        < (birth_date.month, birth_date.day)
    )
