from app.config import settings


class Debug:
    def __init__(self, f):
        self._f = f

    def __call__(self, *args, **kwargs):
        if settings.debug:
            print(
                f"DEBUG: {self._f.__name__}() called w/ args: {args}, kwargs: {kwargs}"
            )
        return _f(*args, **kwargs)
