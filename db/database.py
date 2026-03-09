import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/digiturk_demo")

# Fix Render's postgres:// -> postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# For Neon: use certifi CA bundle so SSL works on all platforms (especially macOS)
connect_args = {}
if "neon.tech" in DATABASE_URL:
    import certifi
    # Strip sslmode/channel_binding from URL — pass via connect_args
    DATABASE_URL = re.sub(r'[?&]sslmode=[^&]*', '', DATABASE_URL)
    DATABASE_URL = re.sub(r'[?&]channel_binding=[^&]*', '', DATABASE_URL)
    DATABASE_URL = DATABASE_URL.rstrip('?&')
    connect_args["sslmode"] = "require"
    connect_args["sslrootcert"] = certifi.where()

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()