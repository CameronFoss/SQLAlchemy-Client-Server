from .tasks import longtime_add, count_vehicles, count_engineers, count_contacts, count_laptops, count_engineers_assigned_to_vehicle, count_vehicles_by_engineer, read_contacts_for_engineer
import time

if __name__ == '__main__':
    num_cars = count_vehicles.delay()
    while not num_cars.ready():
        time.sleep(1)
    print("Number of vehicles in the database: ", num_cars.result)

    num_engins = count_engineers.delay()
    while not num_engins.ready():
        time.sleep(1)
    print("Number of engineers in the database: ", num_engins.result)

    num_laptops = count_laptops.delay()
    while not num_laptops.ready():
        time.sleep(1)
    print("Number of laptops in the database: ", num_laptops.result)

    num_contacts = count_contacts.delay()
    while not num_contacts.ready():
        time.sleep(1)
    print("Number of contact details in the database: ", num_contacts.result)

    num_fusion_engineers = count_engineers_assigned_to_vehicle.delay("Fusion")
    while not num_fusion_engineers.ready():
        time.sleep(1)
    print("Number of engineers working on vehicle model \"Fusion\": ", num_fusion_engineers.result)

    num_cameron_vehicles = count_vehicles_by_engineer.delay("Cameron Foss")
    while not num_cameron_vehicles.ready():
        time.sleep(1)
    print("Number of vehicles engineer Cameron Foss has been assigned to: ", num_cameron_vehicles.result)

    contacts_for_cameron = read_contacts_for_engineer.delay("Cameron Foss")
    while not contacts_for_cameron.ready():
        time.sleep(1)
    print("Contact details for engineer Cameron Foss: ", contacts_for_cameron.result)