import sqlite3

import yoyo


connection = sqlite3.connect("data/bobux.db")

def migrate():
    yoyo_backend = yoyo.get_backend("sqlite:///data/bobux.db")
    yoyo_migrations = yoyo.read_migrations("migrations")
    with yoyo_backend.lock():
        yoyo_backend.apply_migrations(yoyo_backend.to_apply(yoyo_migrations))
