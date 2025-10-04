import os
import sys
import urllib.parse as up

try:
    import psycopg2
except Exception as e:
    print('psycopg2 not available:', e)
    sys.exit(1)

url = os.getenv('DATABASE_URL')
if not url:
    # fallback to the provided value if env not set
    url = 'postgresql://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com/ahmed_uv8c'

# ensure sslmode=require
parsed = up.urlparse(url)
query = dict(up.parse_qsl(parsed.query))
if 'sslmode' not in query:
    query['sslmode'] = 'require'
new_query = up.urlencode(query)
url = up.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

print('Connecting to:', url)

try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute('select version()')
    version = cur.fetchone()[0]
    cur.execute('select current_user')
    user = cur.fetchone()[0]
    cur.execute('select current_database()')
    db = cur.fetchone()[0]
    print('Connected OK')
    print('Server version:', version)
    print('Current user:', user)
    print('Database:', db)
    cur.close()
    conn.close()
except Exception as e:
    print('Connection FAILED:')
    print(e)
    sys.exit(2)
