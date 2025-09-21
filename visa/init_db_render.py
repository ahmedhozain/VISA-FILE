import os
from app import app, init_db

print('Using DATABASE_URL:', os.getenv('DATABASE_URL'))

with app.app_context():
    init_db()

print('DB init done')
