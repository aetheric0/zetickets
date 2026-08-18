import asyncio
import app.core.config; 
from sqlalchemy.ext.asyncio import create_async_engine; 
from sqlalchemy import text 

engine = create_async_engine(app.core.config.settings.SQL_ALCHEMY_DATABASE_URI) 
async def models_print():
    result = await asyncio.run(engine.connect()).execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))

    yield f'{result.columns}'

print(models_print())
