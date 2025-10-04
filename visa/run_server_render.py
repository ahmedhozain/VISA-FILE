import os

# Set Render Postgres URL here to avoid PowerShell issues
os.environ['DATABASE_URL'] = (
    'postgresql://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@'
    'dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com/ahmed_uv8c?sslmode=require'
)

from app import app

if __name__ == '__main__':
    app.run(debug=True)
