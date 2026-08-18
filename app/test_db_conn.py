import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings  # adjust import path if needed

async def test_conn():
    engine = create_async_engine(settings.SQL_ALCHEMY_DATABASE_URI)
    async with engine.connect() as conn:
        print("Successfully connected to PostgreSQL!")
    await engine.dispose()

asyncio.run(test_conn())