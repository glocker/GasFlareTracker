from psycopg_pool import ConnectionPool

from app.config import DATABASE_URL

# opened in FastAPI's lifespan / explicitly by CLI scripts, not at import time
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False)
