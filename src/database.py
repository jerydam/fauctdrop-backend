import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base # or from .orm import declarative_base

# --- Supabase Configuration ---
# You MUST set this environment variable in your .env or shell.
# Format: postgresql+asyncpg://[user]:[password]@[host]:[port]/[db_name]
# Get this URL from your Supabase Project Settings -> Database -> Connection String
DATABASE_URL = os.environ.get("DATABASE_URL") 

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set for Supabase connection.")

# Supabase uses asyncpg as the PostgreSQL driver
engine = create_async_engine(DATABASE_URL, echo=False)

# The base class for your ORM models
Base = declarative_base() 

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Database Dependency for FastAPI routes
async def get_db():
    """Provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()