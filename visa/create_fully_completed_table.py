#!/usr/bin/env python3
"""
Script to create the FullyCompletedClient table
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, FullyCompletedClient

def create_fully_completed_table():
    """Create the FullyCompletedClient table"""
    with app.app_context():
        try:
            # Create the table
            db.create_all()
            print("SUCCESS: FullyCompletedClient table created successfully!")
            
            # Verify the table exists
            inspector = inspect(db.engine)
            if 'fully_completed_client' in inspector.get_table_names():
                print("SUCCESS: Table verification successful!")
            else:
                print("ERROR: Table verification failed!")
                
        except Exception as e:
            print(f"ERROR: Error creating table: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("Creating FullyCompletedClient table...")
    success = create_fully_completed_table()
    
    if success:
        print("\nMigration completed successfully!")
    else:
        print("\nMigration failed!")
        sys.exit(1)
