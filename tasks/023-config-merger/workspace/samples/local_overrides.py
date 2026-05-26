"""Illustrative per-developer overlay applied last on top of staging/prod."""

CONFIG = {
    "app": {
        "debug": True,
    },
    "db": {
        "host": "127.0.0.1",
        "port": 5432,
    },
    "features": {
        "experimental_ui": True,
    },
}
