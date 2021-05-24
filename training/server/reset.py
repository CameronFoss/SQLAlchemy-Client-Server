from training.server.inserts import insert_default_items
from training.server.base import engine, Base
from training.server.model import Vehicle, Laptop, ContactDetails, Engineer
from training.server.db_utils import session

def reset_db():
    Base.metadata.drop_all(engine)
    print("Called drop_all on base metadata")
    session.commit()
    print("Committed drop all")
    insert_default_items()

if __name__ == "__main__":
    reset_db()
