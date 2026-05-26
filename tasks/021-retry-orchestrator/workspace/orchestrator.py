from services import TransientError, PermanentError, RetryExhausted


class RetryOrchestrator:
    """TODO: implement your retry strategy and document it here."""

    def __init__(self, max_total_retries: int = 10):
        ...

    def call(self, service, *args, **kwargs):
        ...
