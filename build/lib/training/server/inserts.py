from datetime import date
from training.server.model import Vehicle, Laptop, ContactDetails, Engineer
from training.server.base import Session, engine, Base

def insert_default_items():
    Base.metadata.create_all(engine)

    session = Session()

    # Vehicles
    fusion_2020 = Vehicle('Fusion', 3, 23170, date(2019, 10, 5))
    explorer_2020 = Vehicle('Explorer', 1, 32765, date(2019, 6, 15))
    bronco_2020 = Vehicle('Bronco', 0, 26820, date(2018, 12, 20))
    mustang_2020 = Vehicle('Mustang Shelby GT500', 10, 73995, date(2019, 3, 30))

    # Engineers
    cameron = Engineer('Cameron Foss', date(1998, 12, 1))
    prerna = Engineer('Prerna Sancheti', date(1992, 8, 13))
    jaiven = Engineer('Jaivenkatram Harirao', date(1990, 3, 26))

    # Vehicle - Engineer Relationships
    fusion_2020.engineers = [prerna, jaiven]
    explorer_2020.engineers = [cameron, prerna]
    bronco_2020.engineers = [jaiven]
    mustang_2020.engineers = [cameron, prerna, jaiven]

    # Contact Details and Contact Details - Engineer Relationships
    cameron_contact = ContactDetails("989-906-0292", "302 W Davis Ave Ann Arbor MI", cameron)
    prerna_contact = ContactDetails("555-999-9999", "1123 Example St", prerna)
    prerna_contact2 = ContactDetails("555-777-7777", "432 Example Work Address", prerna)
    jaiven_contact = ContactDetails("555-333-3333", "888 Another Example St", jaiven)

    # Laptops and Laptop - Engineer Relationships
    cameron_laptop = Laptop("Macbook Air", date(2016, 9, 1), cameron)
    prerna_laptop = Laptop("Surface Pro 7", date(2018, 12, 10), prerna)
    jaiven_laptop = Laptop("Dell Latitude", date(2017, 7, 11), jaiven)

    # persist data to DB
    session.add(fusion_2020)
    session.add(explorer_2020)
    session.add(bronco_2020)
    session.add(mustang_2020)

    session.add(cameron_contact)
    session.add(prerna_contact)
    session.add(prerna_contact2)
    session.add(jaiven_contact)

    session.add(cameron_laptop)
    session.add(prerna_laptop)
    session.add(jaiven_laptop)

    session.commit()
    session.close()

if __name__ == "__main__":
    insert_default_items()