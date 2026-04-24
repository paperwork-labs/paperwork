import contextvars
import logging

_request_id_ctx = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> contextvars.Token:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id_ctx.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
