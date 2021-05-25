from __future__ import absolute_import
from training.server.model import Laptop
from celery_demo.celery import app
from training.server.db_utils import VehicleUtils, EngineerUtils, LaptopUtils, ContactDetailsUtils, cleanup_utils
import time

engin_utils = EngineerUtils()
car_utils = VehicleUtils()
laptop_utils = LaptopUtils()
contact_utils = ContactDetailsUtils()

@app.task
def read_contacts_for_engineer(name):
    print(f"Reading all contact details for engineer {name}")
    engin = engin_utils.read_engineer_by_name(name)
    contacts = contact_utils.read_contact_details_by_engin_id(engin.id)
    contacts = [contact.to_json() for contact in contacts]
    return contacts

@app.task
def read_all_contacts():
    print("Reading all contact info")
    contacts = contact_utils.read_all_contact_details()
    contacts = [contact.to_json() for contact in contacts]
    return contacts

@app.task
def read_laptops_by_engineer(name):
    print(f"Reading info for laptop loaned by engineer {name}")
    laptop = laptop_utils.read_laptop_by_owner(name)
    return laptop.to_json()

@app.task
def read_all_laptops():
    print("Reading info for all laptops")
    laptops = laptop_utils.read_all_laptops()
    laptops = [laptop.to_json() for laptop in laptops]
    return

@app.task
def read_vehicle_by_model(model):
    print(f"Reading info for vehicle model {model}")
    cars = car_utils.read_vehicles_by_model(model)
    cars = [car.to_json() for car in cars]
    return cars

@app.task
def read_all_vehicles():
    print("Reading info for all vehicles")
    cars = car_utils.read_vehicles_all()
    cars = [car.to_json() for car in cars]
    return cars

@app.task
def read_engineer_by_name(name):
    print(f"Reading info for engineer {name}")
    engin = engin_utils.read_engineer_by_name(name)
    return engin.to_json()

@app.task
def read_all_engineers():
    print("Reading info for all engineers")
    engins = engin_utils.read_all_engineers()
    engins = [engin.to_json() for engin in engins]
    return engins

@app.task
def read_engineers_by_vehicle(model):
    print(f"Reading info for engineers assigned to vehicle {model}")
    engins = car_utils.read_assigned_engineers_by_model(model)
    engins = [engin.to_json() for engin in engins]
    return engins

@app.task
def read_vehicles_by_engineer(name):
    print(f"Reading info for vehicles engineer {name} is assigned to")
    cars = engin_utils.read_assigned_vehicles_by_name(name)
    cars = [car.to_json() for car in cars]
    return cars