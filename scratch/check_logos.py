from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql+psycopg://postgres:startup-pass@startups-portal-rds.c3i0uugwmx0g.ap-south-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def check_logos():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT id, name, logo FROM "Startup" WHERE logo IS NOT NULL LIMIT 10'))
        for row in result:
            print(f"ID: {row[0]}, Name: {row[1]}, Logo: {row[2]}")

if __name__ == "__main__":
    check_logos()
