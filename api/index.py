import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, initialize_database

app = create_app()

try:
    initialize_database(app)
except Exception:
    logging.exception("Viral Place database initialization failed")
