import threading


class Debouncer:
    def __init__(self, func, delay):
        self._func = func
        self._delay = delay
        self._timer = None
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                self._delay, self._func, args=args, kwargs=kwargs
            )
            self._timer.start()

    def cancel(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def debounce(func, delay):
    """Wrap `func` so that rapid successive calls collapse into one,
    executed `delay` seconds after the last call.
    """
    return Debouncer(func, delay)
