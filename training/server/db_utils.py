from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import IntegrityError
from training.server.base import Session
from datetime import date
from training.server.model import Vehicle, vehicle_engineer_association, Engineer, Laptop, ContactDetails
from sqlalchemy import literal
from sqlalchemy.orm.exc import UnmappedInstanceError

class VehicleUtils:
    # Create a new vehicle
    def add_vehicle_db(self, session, model, quantity, price, manufacture_date):
        # if vehicle exists, update quantity
        car_exists = (session.query(literal(True)).filter(Vehicle.model == model).first())
        if car_exists is not None:
            cars = self.read_vehicles_by_model(session, model)
            session.commit()
            for car in cars:
                new_quantity = car.quantity + quantity
                print(f"Updating model {model} in the database.")
                self.update_vehicle_db(session, car.id, quantity=new_quantity)
                session.commit()
                return None
        else:            
            new_car = Vehicle(model, quantity, price, manufacture_date)
            session.add(new_car)
            session.commit()
            print("Committed new car")
            new_car_id = new_car.id
            new_car_engins = [engin.name for engin in new_car.engineers]
            return new_car

    # Delete a vehicle by model
    def delete_vehicle_by_model(self, session, model):
        cars = self.read_vehicles_by_model(session, model)
        if not cars:
            return False
        for car in cars:
            session.query(vehicle_engineer_association).filter(vehicle_engineer_association.c.vehicle_id == car.id).delete()
            session.delete(car)
        session.commit()
        return True

    # Read all vehicles
    def read_vehicles_all(self, session):
        cars = session.query(Vehicle).all()
        session.commit()
        return cars

    # Read a vehicle by id
    def read_vehicle_by_id(self, session, id):
        car = session.query(Vehicle).get(id)
        session.commit()
        return car

    # Read a vehicles by model
    def read_vehicles_by_model(self, session, model):
        cars = session.query(Vehicle).filter(Vehicle.model == model).all()
        session.commit()
        return cars

    # Read engineers assigned to a vehicle model
    def read_assigned_engineers_by_model(self, session, model):
        cars = self.read_vehicles_by_model(session, model)
        engineer_ids = []
        for car in cars:
            engineer_ids += session.query(vehicle_engineer_association.c.engineer_id).filter(vehicle_engineer_association.c.vehicle_id == car.id).all()
        session.commit()
        return [EngineerUtils.read_engineer_by_id(EngineerUtils(), session, id) for id in engineer_ids]

    # Update a vehicle record by id
    def update_vehicle_db(self, session, id, model=None, quantity=None, price=None, manufacture_date=None, engineers=None):
        car = self.read_vehicle_by_id(session, id)
        try:
            car.model = model if model is not None else car.model
            car.quantity = quantity if quantity is not None else car.quantity
            car.price = price if price is not None else car.price
            car.manufacture_date = manufacture_date if manufacture_date is not None else car.manufacture_date
            car.engineers = engineers if engineers is not None else car.engineers
            session.commit()
            print("Commited vehicle update")
        except:
            session.rollback()
            print("Rollback vehicle update")
            return None
        return car

class EngineerUtils:
    # Create a new engineer
    def add_engineer_db(self, session, name, date_of_birth):
        new_engin = Engineer(name, date_of_birth)
        try:
            session.add(new_engin)
            session.commit()
            return new_engin
        except IntegrityError:
            session.rollback()
            return None
        

    # Delete an engineer and their respective contact details
    def delete_engineer_by_name(self, session, name):
        engin = self.read_engineer_by_name(session, name)
        try:
            ContactDetailsUtils.delete_contact_details_by_engin_id(ContactDetailsUtils(), session, engin.id)
        except UnmappedInstanceError:
            pass
        session.query(vehicle_engineer_association).filter(vehicle_engineer_association.c.engineer_id == engin.id).delete()
        session.delete(engin)
        session.commit()

    # Read all engineers
    def read_all_engineers(self, session):
        engins = session.query(Engineer).all()
        session.commit()
        return engins

    # Read an engineer by id
    def read_engineer_by_id(self, session, id):
        engin = session.query(Engineer).get(id)
        session.commit()
        return engin

    # Read an engineer by name
    def read_engineer_by_name(self, session, name):
        engin = session.query(Engineer).filter(Engineer.name == name).first()
        session.commit()
        return engin

    # Read vehicles this engineer is assigned to
    def read_assigned_vehicles_by_name(self, session, name):
        engin = self.read_engineer_by_name(session, name)
        vehicle_ids = session.query(vehicle_engineer_association.c.vehicle_id).filter(vehicle_engineer_association.c.engineer_id == engin.id).all()
        car_utils = VehicleUtils()
        session.commit()
        return [car_utils.read_vehicle_by_id(session, id) for id in vehicle_ids]

    # Update an engineer record by id
    def update_engineer_by_id(self, session, id, name=None, date_of_birth=None):
        engin = self.read_engineer_by_id(session, id)
        engin.name = name if name is not None else engin.name
        engin.birthday = date_of_birth if date_of_birth is not None else engin.birthday
        session.commit()
        return engin

class LaptopUtils:
    # Create a new laptop
    def add_laptop_db(self, session, model, date_loaned, engineer_name):
        engin = EngineerUtils.read_engineer_by_name(EngineerUtils(), session, engineer_name)
        try:
            new_laptop = Laptop(model, date_loaned, engin)
            session.add(new_laptop)
            session.commit()
            return new_laptop
        except IntegrityError:
            session.rollback()
            return None

    # Delete a laptop
    def delete_laptop_by_id(self, session, id):
        laptop = self.read_laptop_by_id(id)
        session.delete(laptop)
        session.commit()

    def delete_laptop_by_model_owner(self, session, model, engineer_name):
        laptop = self.read_laptop_by_model_owner(model, engineer_name)
        session.delete(laptop)
        session.commit()

    def delete_laptop_by_owner(self, session, engineer_name):
        laptop = self.read_laptop_by_owner(session, engineer_name)
        session.delete(laptop)
        session.commit()

    # Read all laptops
    def read_all_laptops(self, session):
        laptops = session.query(Laptop).all()
        session.commit()
        return laptops

    # Read laptops by model
    def read_laptops_by_model(self, session, model):
        laptops = session.query(Laptop).filter(Laptop.model == model).all()
        session.commit()
        return laptops

    # Read a laptop by id
    def read_laptop_by_id(self, session, id):
        laptop = session.query(Laptop).get(id)
        session.commit()
        return laptop

    # Read laptop by model and owner
    def read_laptop_by_model_owner(self, session, model, engineer_name):
        engin = EngineerUtils.read_engineer_by_name(EngineerUtils(), session, engineer_name)
        laptop = session.query(Laptop).filter(Laptop.model == model, Laptop.engineer_id == engin.id).first()
        session.commit()
        return laptop

    # Read laptop by owner
    def read_laptop_by_owner(self, session, engineer_name):
        engin = EngineerUtils.read_engineer_by_name(EngineerUtils(), session, engineer_name)
        if engin is None:
            return None
        laptop = session.query(Laptop).filter(Laptop.engineer_id == engin.id).first()
        session.commit()
        return laptop

    # Update laptop by id
    def update_laptop_by_id(self, session, id, model=None, date_loaned=None, engineer_name=None):
        laptop = self.read_laptop_by_id(session, id)
        laptop.model = model if model is not None else laptop.model
        laptop.date_loaned = date_loaned if date_loaned is not None else laptop.date_loaned
        if engineer_name == "":
            laptop.engineer = None
        else:
            engin = EngineerUtils.read_engineer_by_name(EngineerUtils(), session, engineer_name)
            laptop.engineer = engin if engin is not None else laptop.engineer
        session.commit()
        return laptop



class ContactDetailsUtils:

    # Create new contact details
    def add_contact_details_db(self, session, phone_number, address, engineer_name):
        engin = EngineerUtils.read_engineer_by_name(EngineerUtils(), session, engineer_name)
        try:
            new_contact = ContactDetails(phone_number, address, engin)
            session.add(new_contact)
            session.commit()
            return new_contact
        except IntegrityError:
            session.rollback()
            return None

    # Delete contact details by id
    def delete_contact_details_by_id(self, session, id):
        contact = self.read_contact_details_by_id(session, id)
        session.delete(contact)
        session.commit()

    # Delete contact details by engineer id
    def delete_contact_details_by_engin_id(self, session, engin_id):
        contacts = self.read_contact_details_by_engin_id(session, engin_id)
        for contact in contacts:
            session.delete(contact)
        session.commit()

    # Read all contact details
    def read_all_contact_details(self, session):
        contacts = session.query(ContactDetails).all()
        session.commit()
        return contacts

    # Read contact details by id
    def read_contact_details_by_id(self, session, id):
        contact = session.query(ContactDetails).get(id)
        session.commit()
        return contact

    # Read contact details by engineer id
    def read_contact_details_by_engin_id(self, session, engin_id):
        contacts = session.query(ContactDetails).filter(ContactDetails.engineer_id == engin_id).all()
        session.commit()
        return contacts

    # Update contact details by id
    def update_contact_details_by_id(self, session, id, phone_number=None, address=None, engineer_name=None):
        contact = self.read_contact_details_by_id(session, id)
        engin = EngineerUtils.read_engineer_by_name(EngineerUtils(), session, engineer_name)
        contact.phone_number = phone_number if phone_number is not None else contact.phone_number
        contact.address = address if address is not None else contact.address
        contact.engineer = engin if engin is not None else contact.engineer
        session.commit()
        return contact

    # Update contact details by engineer id
    def update_contact_details_by_engin_id(self, session, engin_id, phone_number=None, address=None):
        contact = self.read_contact_details_by_engin_id(session, engin_id)
        engin = EngineerUtils.read_engineer_by_id(EngineerUtils(), session, engin_id)
        session.commit()
        return self.update_contact_details_by_id(session, contact.id, phone_number, address, engin.name)