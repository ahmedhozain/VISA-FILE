import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

load_dotenv()

url = os.getenv('DATABASE_URL')
if not url:
    raise SystemExit('DATABASE_URL is not set')
if url.startswith('postgres://'):
    url = url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(url)
print('Engine name:', engine.name)
print('URL:', engine.url)

insp = inspect(engine)
schema = 'public'
print(f'Listing tables in schema: {schema}')
tables = insp.get_table_names(schema=schema)
print('Tables:', tables)
for t in tables:
    cols = insp.get_columns(t, schema=schema)
    col_names = [c['name'] for c in cols]
    print(f'- {t} columns: {col_names}')
