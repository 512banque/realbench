class Cache:
    """A cache with a fixed max size. Behavior when full is up to you."""

    def __init__(self, max_size: int):
        ...

    def get(self, key):
        ...

    def put(self, key, value):
        ...

    def size(self) -> int:
        ...
