from training.server.inserts import insert_default_items
from training.server.base import engine, Base
from training.server.model import Vehicle, Laptop, ContactDetails, Engineer

def reset_db():
    Base.metadata.drop_all(engine)
    insert_default_items()

if __name__ == "__main__":
    reset_db()
