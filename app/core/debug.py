import functools

from app.config import settings


class Debug:
    def __init__(self, f):
        self.func = f
        functools.update_wrapper(self, f)

    def __get__(self, obj, objtype=None):
        """Support instance methods."""
        if obj is None:
            return self
        return functools.partial(self.__call__, obj)

    def __call__(self, *args, **kwargs):
        if settings.debug:
            print(
                f"DEBUG: {self.func.__name__}() called w/ args: {args}, kwargs: {kwargs}"
            )

        result = self.func(*args, **kwargs)
        return result
