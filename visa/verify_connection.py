import os
import traceback
from app import app, db

print('DATABASE_URL set:', bool(os.getenv('DATABASE_URL')))
print('DATABASE_URL value:', os.getenv('DATABASE_URL'))

try:
    with app.app_context():
        print('Engine name:', db.engine.name)
        print('Engine URL:', db.engine.url)
        print('Calling db.create_all() ...')
        db.create_all()
        print('create_all done.')
        # Introspect tables
        from sqlalchemy import inspect
        insp = inspect(db.engine)
        tables = insp.get_table_names(schema='public') if db.engine.name == 'postgresql' else insp.get_table_names()
        print('Tables found:', tables)
        for t in tables:
            cols = insp.get_columns(t, schema='public') if db.engine.name == 'postgresql' else insp.get_columns(t)
            print(f'- {t}:', [c['name'] for c in cols])
except Exception as e:
    print('Error during verification:')
    traceback.print_exc()
    raise
