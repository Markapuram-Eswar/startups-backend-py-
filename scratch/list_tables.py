from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql+psycopg://postgres:startup-pass@startups-portal-rds.c3i0uugwmx0g.ap-south-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def list_tables():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        for row in result:
            print(f"Table: {row[0]}")

if __name__ == "__main__":
    list_tables()
