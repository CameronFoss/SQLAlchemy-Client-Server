from training.server.inserts import insert_default_items
from training.server.base import Session, engine, Base
from training.server.model import Vehicle, Laptop, ContactDetails, Engineer

def reset_db():
    print("Attempting to reset the database")
    session = Session()
    Base.metadata.drop_all(engine)
    print("Called drop_all on base metadata")
    session.commit()
    print("Committed drop all")
    insert_default_items()
    session.close()

if __name__ == "__main__":
    reset_db()
