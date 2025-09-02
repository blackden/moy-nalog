class NalogError(Exception):
    """Base exception for Moy Nalog client."""


class Unauthorized(NalogError):
    pass


class Forbidden(NalogError):
    pass


class NotFound(NalogError):
    pass


class ValidationError(NalogError):
    pass


class ServerError(NalogError):
    pass


class UnknownError(NalogError):
    pass


def raise_for_status(status_code: int, body: str) -> None:
    if status_code < 400:
        return
    if status_code == 400:
        raise ValidationError(body)
    if status_code == 401:
        raise Unauthorized(body)
    if status_code == 403:
        raise Forbidden(body)
    if status_code == 404:
        raise NotFound(body)
    if status_code == 422:
        raise ValidationError(body)
    if status_code >= 500:
        raise ServerError(body)
    raise UnknownError(body)

