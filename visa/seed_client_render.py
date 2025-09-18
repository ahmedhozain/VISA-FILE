import os
from datetime import datetime

# Force DATABASE_URL to Render Postgres to avoid local SQLite
os.environ['DATABASE_URL'] = (
    'postgresql://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@'
    'dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com/ahmed_uv8c?sslmode=require'
)

from app import app, db, Client

if __name__ == '__main__':
    with app.app_context():
        # Ensure tables exist
        db.create_all()
        # Insert test client
        name = f"Test Client {datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        c = Client(name=name, phone='01000000000', visa_type='Test', total_amount=100)
        db.session.add(c)
        db.session.commit()
        print('Inserted client id:', c.id)
        # Print counts
        count = Client.query.count()
        print('client count now:', count)
