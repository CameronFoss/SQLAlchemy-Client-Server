from json.decoder import JSONDecodeError
from math import inf
from datetime import date
from os import replace

from sqlalchemy.orm.exc import UnmappedInstanceError
from sqlalchemy.sql.expression import delete, insert
from training.choice_funcs import get_digit_choice, get_yes_no_choice, get_day, get_month, get_year
from training.sock_utils import send_message, decode_message_chunks, get_data_from_connection
from docx import Document
import json
import logging
import socket
import click

def dump_to_json(object, out_file_name):
    try:
        with open(out_file_name, 'w') as f:
            json.dump(object, f, indent=4, sort_keys=True)
    except JSONDecodeError:
        msg = f"JSONDecodeError: There was a problem dumping the JSON object {object} to {out_file_name}"
        print(msg)
        logging.error(msg)

def dump_to_docx(object, out_file_name):
    document = Document()
    document.add_heading("Query Results", 0)
    if isinstance(object, dict):
        # only have one row worth of data
        table = document.add_table(rows=1, cols=len(object))
        table.autofit = True
        # iterate over keys for header cells and vals for data cells
        hdr_cells = table.rows[0].cells
        row_cells = table.add_row().cells
        for i, key, value in enumerate(object.items()):
            hdr_cells[i].text = key
            row_cells[i].text = str(value)
    else:
        # iterate over object for many rows of data
        table = document.add_table(rows=1, cols=len(object[0]))
        table.autofit = True
        hdr_cells = table.rows[0].cells
        for i, key in enumerate(object[0]):
            hdr_cells[i].text = key
        for dic in object:
            row_cells = table.add_row().cells
            for i, value in enumerate(dic.values()):
                row_cells[i].text = str(value)
    document.add_page_break()
    document.save(out_file_name)


class Client:

    def __init__(self, server_port, listen_port):
        self.server_port = server_port
        self.port = listen_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("localhost", self.port))
        self.sock.listen()
        self.sock.settimeout(1)
        logging.basicConfig(filename="client.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s: %(message)s")

    def get_server_response(self):
        server_response = None
        while server_response is None:
            message_chunks = get_data_from_connection(self.sock)

            if not message_chunks:
                continue

            try:
                message_dict = decode_message_chunks(message_chunks)
                server_response = message_dict
                break
            except JSONDecodeError:
                continue
        return server_response

    # Add a vehicle to the DB, update quantity if model already exists
    def add_vehicle(self, model=None, prompt_engin_assign=True):
        if model is None:
            model = input("Enter the model of the new vehicle:")
        quantity = get_digit_choice("Enter the quantity of new vehicles:",
                                    "Please enter a non-negative quantity.",
                                    0, inf)
        price = get_digit_choice("Enter the price of the new vehicle:",
                                 "Invalid price. Please enter a price > 0",
                                 1, inf)
        year = get_year("Enter the year the new vehicle was manufactured:")
        month = get_month("Enter the month the new vehicle was manufactured:")
        day = get_day("Enter the date the new vehicle was manufactured:")
        manufacture_date = date(year, month, day)

        # Send insert message to the server
        logging.info(f"Asking server to add new vehicle {model} manufactured on {manufacture_date} to the database.")
        insert_msg = {
            "port": self.port,
            "action": "add",
            "data_type": "vehicle",
            "model": model,
            "quantity": quantity,
            "price": price,
            "manufacture_year": year,
            "manufacture_month": month,
            "manufacture_date": day
        }
        send_message("localhost", self.server_port, insert_msg)

        # Wait for server response
        server_response = self.get_server_response()

        status = server_response["status"]
        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            print(error_msg)
            return

        elif status == "update":
            update_msg = server_response["text"]
            logging.info(update_msg)
            print(update_msg)
            return

        # Else: insert was successful
        new_server_port = server_response["port"]
        # Added a new vehicle, prompt user to assign engineers to the vehicle
        success_msg = f"Successfully added new vehicle!\nModel: {model}\nQuantity: {quantity}\nPrice: {price}\nManufacture Date: {manufacture_date}"
        print(success_msg)
        logging.info(success_msg)

        if prompt_engin_assign:
            assign_engin = get_yes_no_choice("Assign engineers to this vehicle? (Y/N):")
            if assign_engin == 'y':
                engineer_names = input("\nEnter names of engineers to assign.\nSeparate names by a comma (e.g. John Smith, Jane Doe):")
                engineer_names = engineer_names.split(',')
                logging.info(f"Asking server to assign engineers {engineer_names} to the {model} manufactured on {manufacture_date}.")
                assign_msg = {
                    "response": "y",
                    "engineers": engineer_names
                }
                send_message("localhost", new_server_port, assign_msg)

                server_response = self.get_server_response()
                status = server_response["status"]

                if status == "error":
                    error_msg = server_response["text"]
                    logging.error(error_msg)
                    print(error_msg)
                    return

                assigned = server_response["assigned"]
                unassigned = server_response["unassigned"]

                print("\nSuccessfully assigned engineers to the new vehicle!")
                logging.info(f"\nSuccessfully assigned engineers {assigned} to vehicle model {model} manufactured on {manufacture_date}")
                logging.info(f"\nEngineers {unassigned} did not exist in the database, and could not be assigned to the new vehicle.")
            else:
                assign_msg = {
                    "response": "n"
                }
                send_message("localhost", new_server_port, assign_msg)
                logging.info(f"User skipped assigning any engineers to new vehicle {model} manufactured on {manufacture_date}")

    # Add an engineer to the DB
    def add_engineer(self, engin_name=None, prompt_vehicle_assign=True):
        if engin_name is None:
            engin_name = input("Enter the new Engineer's name:")
        birth_year = get_year(f"Enter engineer {engin_name}'s birth year:")
        birth_month = get_month(f"Enter engineer {engin_name}'s birth month:")
        birth_day = get_day(f"Enter engineer {engin_name}'s birth date:")
        date_of_birth = date(birth_year, birth_month, birth_day)
        

        logging.info(f"Asking server to add new engineers {engin_name} born on {date_of_birth} to the database.")
        insert_msg = {
            "data_type": "engineer",
            "action": "add",
            "port": self.port,
            "name": engin_name,
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_date": birth_day
        }
        send_message("localhost", self.server_port, insert_msg)

        server_response = self.get_server_response()

        try:
            new_server_port = server_response["port"]
        except:
            no_port = "Server response did not include entry \"port\" to let the client know where to send yes/no response."
            logging.error(no_port)
            return None
        
        try:
            status = server_response["status"]
        except:
            no_status = "Server response did not include entry \"status\" to let the client know how to proceed."
            logging.error(no_status)
            return None
        
        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            return None

        success_msg = f"Successfully added new engineer {engin_name} to the database!"
        logging.info(success_msg)

        
        if prompt_vehicle_assign:
            assign_vehicle = get_yes_no_choice("Assign the new engineer to any vehicles? (Y/N):")
            if assign_vehicle == 'y':
                vehicle_models = input("Enter models of vehicles to assign.\nIt is assumed that manufacture date is irrelevant.\nSeparate model names by a comma (e.g. Fusion, Bronco):")
                vehicle_models = vehicle_models.split(',')
                logging.info(f"Asking the server to assign engineer {engin_name} to vehicles {vehicle_models}")
                assign_msg = {
                    "response": "y",
                    "vehicles": vehicle_models
                }
                send_message("localhost", new_server_port, assign_msg)

                server_response = self.get_server_response()
                status = server_response["status"]

                if status == "error":
                    error_msg = server_response["text"]
                    logging.error(error_msg)
                    return
                
                assigned = server_response["assigned"]
                unassigned = server_response["unassigned"]

                print(f"Successfully assigned {engin_name} to vehicles!")
                logging.info(f"Successfully assigned engineer {engin_name} to vehicles {assigned}.")
                logging.info(f"Vehicle models {unassigned} did not exist in the database, and could not be assigned to the new engineer {engin_name}.")
            else:
                assign_msg = {
                    "response" : "n"
                }
                logging.info(f"User skipped assigning engineer {engin_name} to any vehicles.")
                send_message("localhost", new_server_port, assign_msg)

    # Add a laptop to the DB and loan to an engineer if desired
    def add_laptop(self):
        engin_name = input("Enter the name of the engineer this laptop will be loaned to:")
        engin_name = engin_name.strip()
        model = input("Enter the model of the new laptop:")
        year_loaned = get_year(f"Enter the year the laptop was loaned to {engin_name}:")
        month_loaned = get_month(f"Enter the month the laptop was loaned to {engin_name}:")
        day_loaned = get_day(f"Enter the date the laptop was loaned to {engin_name}")
        logging.info(f"Asking server to add a new laptop to the database. Attempting to loan it to engineer {engin_name}")

        insert_msg = {
            "data_type": "laptop",
            "action": "add",
            "port": self.port,
            "model": model,
            "loan_year": year_loaned,
            "loan_month": month_loaned,
            "loan_date": day_loaned,
            "engineer": engin_name
        }
        send_message("localhost", self.server_port, insert_msg)

        success = False
        while not success:
            server_response = self.get_server_response()

            try:
                status = server_response["status"]
            except:
                error_msg = "Server response has no entry for \"status\" to let client know how to proceed."
                print(error_msg)
                logging.error(error_msg)
                return

            if status == "error":
                error_msg = server_response["text"]
                logging.error(error_msg)
                print(error_msg)
                return

            elif status == "success":
                success = True
                loaned_to = server_response["engineer"]
                success_msg = f"Successfully added laptop {model} to the database and loaned it to {loaned_to}."
                logging.info(success_msg)
                print(success_msg)
                return

            try:
                new_server_port = server_response["port"]
            except:
                error_msg = "Server response has no entry for \"port\" to let the client know where to send the response to."
                print(error_msg)
                logging.error(error_msg)
                return
            
            if status == "no_engineer":
                logging.info(f"Engineer {engin_name} did not exist in the database.")
                print(f"Engineer {engin_name} did not exist in the database.")
                abort_laptop = get_yes_no_choice(f"Would you still like to add this laptop without loaning it to an engineer? (Y/N):")
                response_msg = {
                    "response": abort_laptop
                }
                send_message("localhost", new_server_port, response_msg)
                if abort_laptop == 'n':
                    logging.info("Client chose to abort adding the laptop without loaning it to an existing engineer.")
                    return
            
            elif status == "previous_laptop":
                warning_msg = f"Engineer {engin_name} already has a laptop loaned to them\n" + \
                          f"\n!!! WARNING !!! - Adding a new laptop would replace the laptop already loaned to {engin_name}" + \
                          f"{engin_name}'s previous laptop would not be deleted from the database, but would be loaned by no one."
                print(warning_msg)
                logging.warning(warning_msg)
                replace_laptop = get_yes_no_choice(f"Replace {engin_name}'s laptop with the new one? (Y/N)")
                response_msg = {
                    "response": replace_laptop
                }
                send_message("localhost", new_server_port, response_msg)
                if replace_laptop == 'n':
                    logging.info(f"Client chose to abort adding the laptop as to not replace {engin_name}'s existing laptop")
                    return
            

    # Add contact details for an engineer
    def add_contact(self):
        engin_name = input("Which engineer's contact info are you providing? Enter their name:")
        engin_name = engin_name.strip()
        phone_number = input(f"Enter {engin_name}'s phone number (XXX)-XXX-XXXX:")
        address = input(f"Enter {engin_name}'s address:")
        logging.info(f"Asking server to add contact details for engineer {engin_name}.")
        insert_msg = {
            "data_type": "contact_details",
            "action": "add",
            "port": self.port,
            "phone_number": phone_number,
            "address": address,
            "engineer": engin_name
        }
        send_message("localhost", self.server_port, insert_msg)

        server_response = self.get_server_response()

        try:
            status = server_response["status"]
        except:
            error_msg = "Server response has no entry \"status\" to let the client know how to proceed."
            logging.error(error_msg)
            print(error_msg)
            return
        
        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            print(error_msg)
            return
        
        success_msg = f"Successfully added new contact information for {engin_name}!"
        print(success_msg)
        logging.info(success_msg)
        return
        
    # Delete an engineer
    def delete_engineer(self):
        engin_name = input("Enter the name of the engineer to be deleted:")
        engin_name = engin_name.strip()
        proceed = get_yes_no_choice(f"!!! WARNING !!! - Deleting engineer {engin_name} will also delete any of their contact details. Proceed? (Y/N):")
        if proceed == 'n':
            print(f"Aborted deleting engineer {engin_name} from the database.")
            logging.info(f"User chose to abort deleting engineer {engin_name} as to not delete their contact details.")
            return
        logging.info(f"Asking server to delete engineer {engin_name} from the database.")
        delete_msg = {
            "data_type": "engineer",
            "action": "delete",
            "port": self.port,
            "name": engin_name
        }
        send_message("localhost", self.server_port, delete_msg)

        server_response = self.get_server_response()

        try:
            status = server_response["status"]
        except:
            error_msg = "Server response has no entry for \"status\" to let the client know how to proceed."
            logging.error(error_msg)
            print(error_msg)
            return

        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            print(error_msg)
            return
        
        success_msg = f"Successfully deleted engineer {engin_name} and their contact details from the database."
        print(success_msg)
        logging.info(success_msg)

    # Delete a vehicle
    def delete_vehicle(self):
        model = input("Enter the model of the vehicle to delete:")
        model = model.strip()
        logging.info(f"Attempting to delete all {model} vehicle records from the database.")
        proceed = get_yes_no_choice(f"!!! WARNING !!! - ALL {model} vehicle records will be deleted, regardless of manufacture date.\nProceed? (Y/N):")
        if proceed == 'n':
            logging.info(f"User chose to abort deleting all {model} vehicle records.")
            print(f"Aborted deletion of {model} vehicle records.")
            return
        delete_msg = {
            "data_type": "vehicle",
            "action": "delete",
            "port": self.port,
            "model": model
        }
        send_message("localhost", self.server_port, delete_msg)

        server_response = self.get_server_response()

        try:
            status = server_response["status"]
        except:
            error_msg = "Server response has no entry \"status\" to let the client know how to proceed."
            logging.error(error_msg)
            print(error_msg)
            return
        
        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            print(error_msg)
            return

        success_msg = f"Successfully deleted all {model} vehicle records."
        print(success_msg)
        logging.info(success_msg)

    # Delete a laptop
    def delete_laptop(self):
        engin_name = input("Enter the name of the engineer this laptop is loaned to.\n(Leave empty if laptop is loaned to no engineer):")
        engin_name = engin_name.strip()
        delete_msg = {
            "data_type": "laptop",
            "action": "delete",
            "port": self.port,
            "engineer": engin_name
        }
        if engin_name == "":
            id = get_digit_choice(f"Enter the ID number of the un-loaned laptop to be deleted:",
                                   "Invalid Laptop ID. Enter a number > 0", 1, inf)
            delete_msg["id"] = id

        send_message("localhost", self.server_port, delete_msg)

        server_response = self.get_server_response()

        try:
            status = server_response["status"]
        except:
            error_msg = "Server response did not include an entry \"status\" to let the client know how to proceed."
            logging.error(error_msg)
            print(error_msg)
            return
        
        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            print(error_msg)
            return
        
        success_msg = f"Successfully deleted laptop from the database"
        logging.info(success_msg)
        print(success_msg)


    # Delete contact details
    def delete_contact(self):
        engin_name = input("Enter the name of the engineer whose contact details should be deleted.\n(Leave empty to delete contacts by id):")
        engin_name = engin_name.strip()
        proceed = get_yes_no_choice(f"!!! WARNING !!! - All contact details for engineer {engin_name} will be deleted. Proceed? (Y/N):")
        if proceed == 'n':
            logging.info(f"User chose to abort deleting all contact details for engineer {engin_name}")
            print(f"Aborted deleting contact details for engineer {engin_name}.")
            return

        delete_msg = {
            "data_type": "contact_details",
            "action": "delete",
            "port": self.port,
            "engineer": engin_name
        }
        if engin_name == "":
            id = get_digit_choice(f"Enter the ID number of the contact details to be deleted:",
                                   "Invalid Contact Details ID. Enter a number > 0", 1, inf)
            delete_msg["id"] = id

        send_message("localhost", self.server_port, delete_msg)

        server_response = self.get_server_response()

        try:
            status = server_response["status"]
        except:
            error_msg = "Server response had no entry \"status\" to let the client know how to proceed."
            logging.error(error_msg)
            print(error_msg)
            return
        
        if status == "error":
            error_msg = server_response["text"]
            logging.error(error_msg)
            print(error_msg)
            return
        
        success_msg = "Successfully deleted contact details."
        logging.info(success_msg)
        print(success_msg)


    # Decorator for query functions, prompts to dump the results as a JSON object/array
    def json_dump_prompt(func):
        def wrapper(*args, **kwargs):
            db_object = func(*args, **kwargs)
            dump = get_yes_no_choice("Dump the result as JSON? (Y/N)")
            if dump == 'n':
                return db_object
            out_file_name = input("Enter the name of the file to dump JSON to:")
            logging.info(f"Attempting to dump user read result as JSON to file named {out_file_name}")
            if isinstance(db_object, dict):
                # db_object is a single json object
                json_obj = db_object.to_json()
                dump_to_json(json_obj, out_file_name)
                succcess_msg = f"Successfully dumped {json_obj} to {out_file_name}"
                print(succcess_msg)
                logging.info(succcess_msg)
                return db_object
            else:
                # db_object is a list of json objects
                json_array = [obj.to_json() for obj in db_object]
                dump_to_json(json_array, out_file_name)
                succcess_msg = f"Successfully dumped {json_array} to {out_file_name}"
                print(succcess_msg)
                logging.info(succcess_msg)
                return db_object
        return wrapper

    # Decorator for query functions, prompts to dump results to a Word document (docx)
    def docx_dump_prompt(func):
        def wrapper(*args, **kwargs):
            db_object = func(*args, **kwargs)
            dump = get_yes_no_choice("Dump the result to a Word document? (Y/N):")
            if dump == 'n':
                return
            out_file_name = input("Enter the name of the word file to dump to:")
            # remove any potential file extension and replace with .docx
            out_file_name = out_file_name.rsplit('.', 1)[0] + ".docx"
            logging.info(f"Attempting to dump user read result to Word document named {out_file_name}")
            if isinstance(db_object, dict):
                # db_object is a single DB object
                json_obj = db_object.to_json()
                dump_to_docx(json_obj, out_file_name)
            else:
                # db_object is a list of DB objects
                json_array = [obj.to_json() for obj in db_object]
                dump_to_docx(json_array, out_file_name)
        return wrapper

    # Query vehicles, prompt for each column
    @docx_dump_prompt
    @json_dump_prompt
    def query_vehicles(self):
        model = input("Enter the model of vehicles to read.\nEnter \"all\" to read all vehicles.\n(Leave blank to read by vehicle ID):")
        model = model.strip()
        if model == "":
            id = get_digit_choice("Enter the vehicle id to read:",
                                  "Invalid vehicle ID. Enter a number > 0", 1, inf)
            logging.info(f"Reading info for vehicle with ID {id}")
            car = self.car_utils.read_vehicle_by_id(id)
            print(f"Info for vehicle id {id}:")
            print(str(car))
            return car
        elif model == "all":
            logging.info("Reading all vehicle info.")
            cars = self.car_utils.read_vehicles_all()
            print("Info for all vehicles:")
            for car in cars:
                print(str(car))
            return cars
        else:
            logging.info(f"Reading info for model {model} vehicles.")
            cars = self.car_utils.read_vehicles_by_model(model)
            print(f"Info for vehicles of model {model}:")
            for car in cars:
                print(str(car))
            return cars

    # Query engineers, prompt for each column
    @docx_dump_prompt
    @json_dump_prompt
    def query_engineers(self):
        name = input("Enter the name of the engineer to read.\nEnter \"all\" to read all vehicles.\n(Leave blank to read by engineer ID):")
        name = name.strip()
        if name == "":
            id = get_digit_choice("Enter the engineer ID to read:",
                                  "Invalid engineer ID. Enter a number > 0", 1, inf)
            logging.info(f"Reading info for engineer with ID {id}")
            engin = self.engin_utils.read_engineer_by_id(id)
            print(f"Info for engineer ID {id}:")
            print(str(engin))
            return engin
        elif name == "all":
            engins = self.engin_utils.read_all_engineers()
            logging.info("Reading info for all engineers.")
            print("Info for all engineers:")
            for engin in engins:
                print(str(engin))
            return engins
        else:
            logging.info(f"Reading info for engineer named {name}")
            engin = self.engin_utils.read_engineer_by_name(name)
            print(f"Info for engineer {name}:")
            print(str(engin))
            return engin

    # Query laptops, prompt for each column
    @docx_dump_prompt
    @json_dump_prompt
    def query_laptops(self):
        read_all = get_yes_no_choice("Read all laptops? Enter \"N\" to read a single laptop (Y/N):")
        if read_all == 'y':
            logging.info("Reading info for all laptops")
            laptops = self.laptop_utils.read_all_laptops()
            print("Info for all laptops:")
            for laptop in laptops:
                print(str(laptop))
            return laptops
        read_by_model = get_yes_no_choice("Read laptops by model name? Enter \"N\" to read by engineer name (Y/N):")
        if read_by_model == 'y':
            model = input("Enter the model of laptops to read:")
            logging.info(f"Reading info for model {model} laptops")
            laptops = self.laptop_utils.read_laptops_by_model(model)
            print(f"Info for laptops of model {model}:")
            for laptop in laptops:
                print(str(laptop))
            return laptops
        else:
            engin_name = input("Enter the name of engineer whose loaned laptop will be read:")
            logging.info(f"Reading info for laptop loaned by engineer {engin_name}")
            laptop = self.laptop_utils.read_laptop_by_owner(engin_name)
            print(f"Info for laptop loaned by {engin_name}:")
            print(str(laptop))
            return laptop

    # Query contact details, prompt for each column
    @docx_dump_prompt
    @json_dump_prompt
    def query_contacts(self):
        name = input("Enter the name of the engineer whose contact details will be read.\nEnter \"all\" to read all contact details.\nLeave blank to read contact details by ID:")
        name = name.strip()
        if name == "all":
            logging.info("Reading info for all contact details")
            contacts = self.contact_utils.read_all_contact_details()
            print("Info for all contact details:")
            for contact in contacts:
                print(str(contact))
            return contacts
        elif name == "":
            id = get_digit_choice("Enter the contact details ID to read:",
                                  "Invalid ID. Enter a number > 0", 1, inf)
            logging.info(f"Reading info for contact details with ID {id}")
            contact = self.contact_utils.read_contact_details_by_id(id)
            print(f"Info for contact details with ID {id}:")
            print(str(contact))
            return contact
        else:
            logging.info(f"Reading info for contact details of engineer {name}")
            engin = self.engin_utils.read_engineer_by_name(name)
            contacts = self.contact_utils.read_contact_details_by_engin_id(engin.id)
            print(f"Info for contact details of engineer {name}:")
            for contact in contacts:
                print(str(contact))
            return contacts

    def insert_from_json(self):
        file_name = input("Enter the file name containing JSON data to insert:")
        file_name = file_name.strip()
        try:
            logging.info(f"Attempting to insert JSON data stored in file {file_name} to the database")
            with open(file_name) as f:
                json_data = json.load(f)
            if isinstance(json_data, dict):
                self.parse_json_object_and_insert(json_data)
            else:
                # JSON array
                for json_object in json_data:
                    self.parse_json_object_and_insert(json_object)
        except JSONDecodeError:
            error_msg = f"JSONDecodeError: There was a problem reading the JSON object in {file_name} ; JSON object likely not encoded properly."
            print(error_msg)
            logging.error(error_msg)
        except FileNotFoundError:
            error_msg = f"FileNotFoundError: file named {file_name} does not exist."
            print(error_msg)
            logging.error(error_msg)

    def parse_json_object_and_insert(self, json_object):
        logging.info(f"Attempting to parse JSON object and insert into the database.")
        data_type = json_object.get('data_type', None)
        if data_type is None:
            error_msg = "Error: no \"data_type\" entry found in JSON object." + \
                        f"\nAborted adding {json_object} to the database."
            print(error_msg)
            logging.error(error_msg)

        elif data_type == "vehicle":
            logging.info("Attempting to add a vehicle to the database from JSON object.")
            model = json_object.get('model', None)
            quantity = json_object.get('quantity', None)
            price = json_object.get('price', None)
            manufacture_year = json_object.get('manufacture_year', None)
            manufacture_month = json_object.get('manufacture_month', None)
            manufacture_date = json_object.get('manufacture_date', None)
            abort = False
            if model is None:
                model_error = "Error: no entry for vehicle \"model\" found."
                print(model_error)
                logging.error(model_error)
                abort = True
            if quantity is None:
                quantity_error = "Error: no entry for vehicle \"quantity\" found."
                print(quantity_error)
                logging.error(quantity_error)
                abort = True
            if price is None:
                price_error = "Error: no entry for vehicle \"price\" found."
                print(price_error)
                logging.error(price_error)
                abort = True
            if manufacture_year is None:
                year_error = "Error: no entry for vehicle \"manufacture_year\" found."
                print(year_error)
                logging.error(year_error)
                abort = True
            if manufacture_month is None:
                month_error = "Error: no entry for vehicle \"manufacture_month\" found."
                print(month_error)
                logging.error(month_error)
                abort = True
            if manufacture_date is None:
                date_error = "Error: no entry for vehicle \"manufacture_date\" found."
                print(date_error)
                logging.error(date_error)
                abort = True
            if abort:
                abort_msg = f"Aborted adding vehicle {json_object} to the database."
                print(abort_msg)
                logging.error(abort_msg)
                return
            new_car = self.car_utils.add_vehicle_db(model, quantity, price, date(manufacture_year, manufacture_month, manufacture_date))
            if new_car is None:
                car_exists = f"Vehicle model {model} manufactured on {date(manufacture_year, manufacture_month, manufacture_date)} " + \
                             f"already exists in the database.\nIncreased quantity of vehicle model {model} by {quantity}"
                print(car_exists)
                logging.info(car_exists)
            else:
                success_msg = "New vehicle info:" + "\n" + str(new_car) + f"\nSuccessfully added new vehicle to the database!"
                print(success_msg)
                logging.info(success_msg)

        elif data_type == "engineer":
            logging.info("Attempting to add an engineer to the database from JSON object.")
            name = json_object.get('name', None)
            birth_year = json_object.get('birth_year', None)
            birth_month = json_object.get('birth_month', None)
            birth_date = json_object.get('birth_date', None)
            abort = False
            if name is None:
                name_error = "Error: no entry for engineer \"name\" found."
                print(name_error)
                logging.error(name_error)
                abort = True
            if birth_year is None:
                year_error = "Error: no entry for engineer \"birth_year\" found."
                print(year_error)
                logging.error(year_error)
                abort = True
            if birth_month is None:
                month_error = "Error: no entry for engineer \"birth_month\" found."
                print(month_error)
                logging.error(month_error)
                abort = True
            if birth_date is None:
                date_error = "Error: no entry for engineer \"birth_date\" found."
                print(date_error)
                logging.error(date_error)
                abort = True
            if abort:
                abort_msg = f"Aborted adding engineer {json_object} to the database"
                print(abort_msg)
                logging.error(abort_msg)
                return
            new_engin = self.engin_utils.add_engineer_db(name, date(birth_year, birth_month, birth_date))
            if new_engin is None:
                dup_error = f"Engineer named {name} already exists in the database." + \
                            f"\nUpdating info for engineer {name} in the database."
                print(dup_error)
                logging.info(dup_error)
                engin = self.engin_utils.read_engineer_by_name(name)
                engin = self.engin_utils.update_engineer_by_id(engin.id, name=name, date_of_birth=date(birth_year, birth_month, birth_date))
                success_msg = f"Successfully updated info for engineer {name}:\n" + str(engin)
                print(success_msg)
                logging.info(success_msg)
                return
            success_msg = "New engineer info:\n" + str(new_engin) + f"\nSuccessfully added new engineer to the database!"
            print(success_msg)
            logging.info(success_msg)
                

        elif data_type == "laptop":
            logging.info("Attempting to add a laptop to the database from JSON object")
            model = json_object.get('model', None)
            loan_year = json_object.get('loan_year', None)
            loan_month = json_object.get('loan_month', None)
            loan_date = json_object.get('loan_date', None)
            engineer = json_object.get('engineer', None)
            abort = False
            if model is None:
                model_error = "Error: no entry for laptop \"model\" found."
                print(model_error)
                logging.error(model_error)
                abort = True
            if loan_year is None:
                year_error = "Error: no entry for laptop \"loan_year\" found."
                print(year_error)
                logging.error(year_error)
                abort = True
            if loan_month is None:
                month_error = "Error: no entry for laptop \"loan_month\" found."
                print(month_error)
                logging.error(month_error)
                abort = True
            if loan_date is None:
                date_error = "Error: no entry for laptop \"loan_date\" found."
                print(date_error)
                logging.error(date_error)
                abort = True
            if engineer is None:
                engineer_error = "Error: no entry for laptop \"engineer_id\" found."
                print(engineer_error)
                logging.error(engineer_error)
                abort = True
            if abort:
                abort_msg = f"Aborted adding laptop {json_object} to the database"
                print(abort_msg)
                logging.error(abort_msg)
                return
            new_laptop = self.laptop_utils.add_laptop_db(model, date(loan_year, loan_month, loan_date), engineer)
            success_msg = "New laptop info:\n" + str(new_laptop) + "\nSuccessfully added new laptop to the database!"
            print(success_msg)
            logging.info(success_msg)

        elif data_type == "contact_details":
            logging.info("Attempting to add new contact details from JSON object.")
            phone_number = json_object.get('phone_number', None)
            address = json_object.get('address', None)
            engineer = json_object.get('engineer', None)
            abort = False
            if phone_number is None:
                phone_error = "Error: no entry for contact details \"phone_number\" found."
                print(phone_error)
                logging.error(phone_error)
                abort = True
            if address is None:
                addr_error = "Error: no entry for contact details \"address\" found."
                print(addr_error)
                logging.error(addr_error)
                abort = True
            if engineer is None:
                engin_error = "Error: no entry for contact details \"engineer\" found."
                print(engin_error)
                logging.error(engin_error)
                abort = True
            engin = self.engin_utils.read_engineer_by_name(engineer)
            if engin is None:
                engin_error = f"Error: engineer {engineer} does not exist in the database. Contact details cannot be added without an existing engineer."
                print(engin_error)
                logging.error(engin_error)
                abort = True
            if abort:
                abort_msg = f"Aborted adding contact details {json_object} to the database."
                print(abort_msg)
                logging.error(abort_msg)
                return
            new_contact = self.contact_utils.add_contact_details_db(phone_number, address, engineer)
            if new_contact is None:
                dup_error = f"Contact details with phone number {phone_number} already exists." + \
                            f"\nAborted adding contact details {json_object} to the database."
                print(dup_error)
                logging.info(dup_error)
                return
            success_msg = "New contact details info:\n" + str(new_contact) + "\nSuccessfully added new contact details to the database!"
            print(success_msg)
            logging.info(success_msg)

        else:
            data_type_error = f"\"data_type\" entry value of {data_type} is not recognized.\n" + \
                              "\"data_type\" should be one of: \"vehicle\", \"engineer\", \"laptop\", \"contact_details\"\n" + \
                              f"Aborted adding entry {json_object} to the database."
            print(data_type_error)
            logging.error(data_type_error)
            return

    def display_interface(self):
        tables = ["Vehicles", "Engineers", "Laptops", "Contact Details"]
        function_map = [
            [self.add_vehicle, self.delete_vehicle, self.query_vehicles],
            [self.add_engineer, self.delete_engineer, self.query_engineers],
            [self.add_laptop, self.delete_laptop, self.query_laptops],
            [self.add_contact, self.delete_contact, self.query_contacts],
            self.insert_from_json
        ]
        print("\nWelcome to your Database Utilities!")
        print("1. Vehicles")
        print("2. Engineers")
        print("3. Laptops")
        print("4. Contact Details")
        print("5. Insert data from a JSON file")
        print("6: Exit Database Utilities")

        table_choice = get_digit_choice("Select a table, JSON insertion, or Exit:",
                                        "Invalid selection. Please enter a digit corresponding to the desired table, JSON insert, or Exit.",
                                        1, 7)
        table_choice -= 1

        if table_choice == 5:
            return False

        if table_choice == 4:
            self.insert_from_json()
            return True

        print(f"\nWhat would you like to do in the {tables[table_choice]} table?")
        print(f"1. Add a(n) {tables[table_choice][0:-1]}")
        print(f"2. Delete a(n) {tables[table_choice][0:-1]}")
        print(f"3. Read from the {tables[table_choice]} table")
        print("4. Choose a different table to work with")

        action_choice = get_digit_choice(f"Select an action to perform on the {tables[table_choice]} table:",
                                         "Invalid selection. Please enter a digit corresponding to the desired action.",
                                         1, 5)
        action_choice -= 1

        if action_choice == 3:
            # tell main() to restart the interface
            return True

        # call the chosen function from the function map
        function_map[table_choice][action_choice]()

        exit_choice = get_yes_no_choice("Exit the utilities script? (Y/N):")

        # returns false if user chose y to exit, tells main to stop running interface()
        return exit_choice.lower() != "y"

@click.command()
@click.argument("server_port", nargs=1, type=int)
@click.argument("client_port", nargs=1, type=int)
def main(server_port, client_port):
    print(f"Server port: {server_port}")
    print(f"Client port: {client_port}")
    client = Client(server_port, client_port)
    run_again = client.display_interface()
    while run_again:
        run_again = client.display_interface()

if __name__ == "__main__":
    main()