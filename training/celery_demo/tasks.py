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
    print("Finsihed reading contact details")
    return contacts

@app.task
def count_vehicles_by_engineer(name):
    print(f"Counting the total number of vehicles engineer {name} has been assigned to")
    cars = engin_utils.read_assigned_vehicles_by_name(name)
    print("Finished reading vehicles")
    return len(cars)

@app.task
def count_engineers_assigned_to_vehicle(model):
    print(f"Counting the total number of engineers assigned to vehicle model {model}")
    engins = car_utils.read_assigned_engineers_by_model(model)
    print("Finished reading engineers")
    return len(engins)

@app.task
def count_contacts():
    print("Counting the total number of contact details in the database")
    contacts = contact_utils.read_all_contact_details()
    print("Finsihed reading contacts")
    return len(contacts)

@app.task
def count_laptops():
    print("Counting the total number of laptops in the database")
    laptops = laptop_utils.read_all_laptops()
    print("Finsihed reading laptops")
    return len(laptops)

@app.task
def count_engineers():
    print("Counting the total number of engineers in the database")
    engins = engin_utils.read_all_engineers()
    print("Finsihed reading engineers")
    return len(engins)


@app.task
def count_vehicles():
    print("Counting the total number of vehicles in the database")
    cars = car_utils.read_vehicles_all()
    print("Finished reading cars")
    return len(cars)

@app.task
def longtime_add(x, y):
    print('long time task begins')
    # sleep 5 seconds
    time.sleep(5)
    print('long time task finished')
    return x + y
