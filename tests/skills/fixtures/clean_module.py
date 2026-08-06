import requests


def fetch():
    response = requests.get("https://example.com", timeout=10)
    return response.text


def safe_divide(numerator: int, denominator: int) -> float:
    try:
        return numerator / denominator
    except ZeroDivisionError as exc:
        raise ValueError("denominator must not be zero") from exc
