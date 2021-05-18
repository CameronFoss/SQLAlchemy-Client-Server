from sqlalchemy import Column, Integer, String, Boolean, Date, Numeric, Table, ForeignKey
from sqlalchemy.orm import relationship, backref
from training.base import Base

vehicle_engineer_association = Table(
    'vehicle_engineers', Base.metadata,
    Column('vehicle_id', Integer, ForeignKey('vehicles.id')),
    Column('engineer_id', Integer, ForeignKey('engineers.id'))
)

class Vehicle(Base):
    __tablename__ = 'vehicles'

    id = Column(Integer, primary_key=True)
    model = Column(String(20), unique=True)
    in_stock = Column(Boolean)
    quantity = Column(Integer)
    price = Column(Numeric)
    manufacture_date = Column(Date)
    engineers = relationship("Engineer", secondary=vehicle_engineer_association)

    def __init__(self, model, quantity, price, manufacture_date):
        self.model = model
        self.quantity = quantity
        self.in_stock = (quantity > 0)
        self.price = price
        self.manufacture_date = manufacture_date

    def __str__(self):
        return f"ID: {self.id}\nModel: {self.model}\nQuantity: {self.quantity}\nPrice: {self.price}\nManufacture Date: {self.manufacture_date}"

    def to_json(self):
        return {
            "data_type": "vehicle",
            "model": self.model,
            "quantity": self.quantity,
            "price": float(self.price),
            "manufacture_year": self.manufacture_date.year,
            "manufacture_month": self.manufacture_date.month,
            "manufacture_date": self.manufacture_date.day
        }

class Engineer(Base):
    __tablename__ = 'engineers'

    id = Column(Integer, primary_key=True)
    name = Column(String(20), unique=True)
    birthday = Column(Date)

    def __init__(self, name, birthday):
        self.name = name
        self.birthday = birthday
    
    def __str__(self):
        return f"ID: {self.id}\nName: {self.name}\nBirthday: {self.birthday}"

    def to_json(self):
        return {
            "data_type": "engineer",
            "name": self.name,
            "birth_year": self.birthday.year,
            "birth_month": self.birthday.month,
            "birth_date": self.birthday.day
        }

class Laptop(Base):
    __tablename__ = 'laptops'

    id = Column(Integer, primary_key=True)
    model = Column(String(20))
    date_loaned = Column(Date)
    engineer_id = Column(Integer, ForeignKey("engineers.id"))
    engineer = relationship("Engineer", backref=backref("laptop", uselist=False))

    def __init__(self, model, date_loaned, engineer):
        self.model = model
        self.date_loaned = date_loaned
        self.engineer = engineer

    def __str__(self):
        return f"ID: {self.id}\nModel: {self.model}\nDate Loaned: {self.date_loaned}\nEngineer: {str(self.engineer)}"

    def to_json(self):
        engin_name = "None" if self.engineer is None else self.engineer.name
        return {
            "data_type": "laptop",
            "model": self.model,
            "loan_year": self.date_loaned.year,
            "loan_month": self.date_loaned.month,
            "loan_date": self.date_loaned.day,
            "engineer": engin_name
        }

class ContactDetails(Base):
    __tablename__ = 'contact_details'

    id = Column(Integer, primary_key=True)
    phone_number = Column(String(12), unique=True)
    address = Column(String(100))
    engineer_id = Column(Integer, ForeignKey('engineers.id'))
    engineer = relationship('Engineer', backref='contact_details')

    def __init__(self, phone_number, address, engineer):
        self.phone_number = phone_number
        self.address = address
        self.engineer = engineer

    def __str__(self):
        return f"ID: {self.id}\nPhone Number: {self.phone_number}\nAddress: {self.address}\nEngineer: {str(self.engineer)}"

    def to_json(self):
        engin_name = "None" if self.engineer is None else self.engineer.name
        return {
            "data_type": "contact_details",
            "phone_number": self.phone_number,
            "address": self.address,
            "engineer": engin_name
        }