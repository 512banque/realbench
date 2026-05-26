"""Illustrative staging overlay applied on top of base."""

CONFIG = {
    "app": {
        "debug": True,
        "log_level": "DEBUG",
    },
    "db": {
        "host": "staging-db.internal",
        "pool_size": 10,
    },
    "allowed_origins": ["https://staging.example.com"],
}
