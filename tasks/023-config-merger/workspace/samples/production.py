"""Illustrative production overlay (most-specific, last in priority)."""

CONFIG = {
    "app": {
        "debug": False,
        "log_level": "WARN",
    },
    "db": {
        "host": "prod-db.internal",
        "port": 6432,
        "pool_size": 50,
        "ssl": True,
    },
    "features": {
        "billing": True,
    },
    "allowed_origins": ["https://app.example.com", "https://api.example.com"],
}
