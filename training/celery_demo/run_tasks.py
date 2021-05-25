from .tasks import read_contacts_for_engineer, read_all_contacts, read_laptops_by_engineer, read_all_laptops, read_engineer_by_name, read_all_engineers, read_vehicle_by_model, read_all_vehicles, read_engineers_by_vehicle, read_vehicles_by_engineer
from training.client.choice_funcs import get_digit_choice, get_yes_no_choice
import time

def read_vehicles():
    model = input("Enter the model of the vehicle you want to read.\nEnter \"all\" to read all vehicles: ")
    if model == "all":
        cars_json = read_all_vehicles.delay()
        while not cars_json.ready():
            time.sleep(1)
        print(f"Read result for all vehicles: {cars_json.result}")
    else:
        car_json = read_vehicle_by_model.delay(model)
        while not car_json.ready():
            time.sleep(1)
        print(f"Read result for model {model}: {car_json.result}")

def read_engineers():
    name = input("Enter the name of the engineer you want to read.\nEnter \"all\" to read all engineers: ")
    if name == "all":
        engins_json = read_all_engineers.delay()
        while not engins_json.ready():
            time.sleep(1)
        print(f"Read result for all engineers: {engins_json.result}")
    else:
        engin_json = read_engineer_by_name.delay(name)
        while not engin_json.ready():
            time.sleep(1)
        print(f"Read result for engineer {name}: {engin_json.result}")

def read_laptops():
    name = input("Enter the name of the engineer whose laptop you want to read.\nEnter \"all\" to read all laptops: ")
    if name == "all":
        laptops_json = read_all_laptops.delay()
        while not laptops_json.ready():
            time.sleep(1)
        print(f"Read result for all laptops: {laptops_json.result}")
    else:
        laptop_json = read_laptops_by_engineer.delay(name)
        while not laptop_json.ready():
            time.sleep(1)
        print(f"Read result for laptop loaned by engineer {name}: {laptop_json.result}")

def read_contacts():
    name = input("Enter the name of the engineer whose contact details you want to read.\nEnter \"all\" to read all contact details: ")
    if name == "all":
        contacts_json = read_all_contacts.delay()
        while not contacts_json.ready():
            time.sleep(1)
        print(f"Read result for all contact details: {contacts_json.result}")
    else:
        contacts_json = read_contacts_for_engineer.delay(name)
        while not contacts_json.ready():
            time.sleep(1)
        print(f"Read result for engineer {name}'s contact details: {contacts_json.result}")

def read_vehicle_engineer():
    by_engin_name = get_yes_no_choice("Read assignments by engineer name?\n(Enter \"N\" to read by vehicle model) (Y/N): ")
    if by_engin_name == 'y':
        name = input("Enter the name of the engineer whose assigned vehicles you want to read: ")
        cars_json = read_vehicles_by_engineer.delay(name)
        while not cars_json.ready():
            time.sleep(1)
        print(f"Read result for vehicles assigned to engineer {name}: {cars_json.result}")
    else:
        model = input("Enter the model of the vehicle whose assigned engineers you want to read: ")
        engins_json = read_engineers_by_vehicle.delay(model)
        while not engins_json.ready():
            time.sleep(1)
        print(f"Read result for engineers assigned to vehicle model {model}: {engins_json.result}")

def show_interface():
    print("Available Tables to Read From:")
    print("1. Vehicles")
    print("2. Engineers")
    print("3. Laptops")
    print("4. Contact Details")
    print("5. Vehicle-Engineer Assignments")

    choice = get_digit_choice("Select a table to read from:", "Invalid choice. Choose a number (1-5) corresponding to the desired table.", 1, 6)

    if choice == 1:
        read_vehicles()
    elif choice == 2:
        read_engineers()
    elif choice == 3:
        read_laptops()
    elif choice == 4:
        read_contacts()
    elif choice == 5:
        read_vehicle_engineer()
    
    exit = get_yes_no_choice("Exit the celery producer? (Y/N):")

    return exit != 'y'

if __name__ == '__main__':
    run_again = show_interface()
    while run_again:
        run_again = show_interface()