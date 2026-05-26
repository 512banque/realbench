"""Illustrative base config (defaults for a small web app).

These dicts are NOT loaded or parsed by merge_configs. They live here
only to give a reader a feel for the kind of nested structures the
function is expected to merge in real usage.
"""

CONFIG = {
    "app": {
        "name": "demo",
        "debug": False,
        "log_level": "INFO",
    },
    "db": {
        "host": "localhost",
        "port": 5432,
        "pool_size": 5,
    },
    "features": {
        "billing": False,
        "search": True,
    },
    "allowed_origins": ["http://localhost:3000"],
}
