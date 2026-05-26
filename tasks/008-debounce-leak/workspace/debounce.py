import threading


class Debouncer:
    def __init__(self, func, delay):
        self._func = func
        self._delay = delay
        self._timer = None

    def __call__(self, *args, **kwargs):
        # BUG: each call schedules a new Timer without cancelling the previous one,
        # so N rapid calls execute `func` N times instead of collapsing to 1.
        timer = threading.Timer(self._delay, self._func, args=args, kwargs=kwargs)
        timer.start()
        self._timer = timer

    def cancel(self):
        if self._timer is not None:
            self._timer.cancel()


def debounce(func, delay):
    """Wrap `func` so that rapid successive calls collapse into one,
    executed `delay` seconds after the last call.
    """
    return Debouncer(func, delay)
