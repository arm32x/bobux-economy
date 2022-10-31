import sqlite3

import yoyo


connection = sqlite3.connect("data/bobux.db", detect_types=sqlite3.PARSE_DECLTYPES)

# This will not affect existing code since sqlite3.Row objects support
# the same operations as tuples. However, this allows new code to take
# advantage of features provided by sqlite3.Row.
connection.row_factory = sqlite3.Row

def migrate():
    yoyo_backend = yoyo.get_backend("sqlite:///data/bobux.db")
    yoyo_migrations = yoyo.read_migrations("migrations")
    with yoyo_backend.lock():
        yoyo_backend.apply_migrations(yoyo_backend.to_apply(yoyo_migrations))
