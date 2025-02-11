import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_DIALECT = os.getenv('DB_DIALECT')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = quote_plus(os.getenv('DB_PASSWORD')) 

def get_db_session(db_name):
    url_connection = f"{DB_DIALECT}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{db_name}?connect_timeout=1000"
    
    engine = create_engine(
        url_connection,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
    )
    
    SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
    
    return SessionLocal
