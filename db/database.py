from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# PostgreSQL connection string
connection_string = "postgresql://postgres:postgres@localhost:5432/chatbot"

# Create SQLAlchemy engine
engine = create_engine(connection_string)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()


