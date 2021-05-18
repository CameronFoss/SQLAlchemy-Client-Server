from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

engine = create_engine('mysql+mysqldb://root:LiviLexiStorm4578!@localhost:3306/SQLAlchemy')
Session = sessionmaker(bind=engine)

Base = declarative_base()