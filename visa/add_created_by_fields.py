#!/usr/bin/env python3
"""
Script to add created_by fields to FullyCompletedClient table
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def add_created_by_fields():
    """Add created_by fields to FullyCompletedClient table"""
    with app.app_context():
        try:
            # Check if the table exists
            inspector = inspect(db.engine)
            if 'fully_completed_client' not in inspector.get_table_names():
                print("ERROR: FullyCompletedClient table does not exist!")
                return False
            
            # Get existing columns
            existing_columns = [col['name'] for col in inspector.get_columns('fully_completed_client')]
            
            # Add new columns if they don't exist
            new_columns = [
                ('file_created_by', 'VARCHAR(120)'),
                ('followup_created_by', 'VARCHAR(120)'),
                ('legal_created_by', 'VARCHAR(120)')
            ]
            
            for column_name, column_type in new_columns:
                if column_name not in existing_columns:
                    try:
                        with db.engine.connect() as connection:
                            connection.execute(text(f"ALTER TABLE fully_completed_client ADD COLUMN {column_name} {column_type}"))
                            connection.commit()
                        print(f"SUCCESS: Added column {column_name}")
                    except Exception as e:
                        print(f"WARNING: Column {column_name} might already exist: {e}")
                else:
                    print(f"INFO: Column {column_name} already exists")
            
            print("SUCCESS: Migration completed successfully!")
            return True
                
        except Exception as e:
            print(f"ERROR: Error adding columns: {e}")
            return False

if __name__ == "__main__":
    print("Adding created_by fields to FullyCompletedClient table...")
    success = add_created_by_fields()
    
    if success:
        print("\nMigration completed successfully!")
    else:
        print("\nMigration failed!")
        sys.exit(1)
