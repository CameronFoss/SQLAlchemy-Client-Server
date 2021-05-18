import socket
import threading
import logging
from types import new_class
import click
from time import sleep
from sys import stdin
from select import select
from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm.exc import UnmappedInstanceError
from training.db_utils import VehicleUtils, EngineerUtils, LaptopUtils, ContactDetailsUtils, cleanup_utils
from training.sock_utils import send_message, decode_message_chunks, get_data_from_connection
from json import JSONDecodeError
from random import randint
from datetime import date

class Server:
    
    def __init__(self, listen_port):
        self.shutdown = False
        self.used_ports = {listen_port}
        self.PORT_MIN = 1024
        self.PORT_MAX = 49151
        self.car_utils = VehicleUtils()
        self.engin_utils = EngineerUtils()
        self.laptop_utils = LaptopUtils()
        self.contact_utils = ContactDetailsUtils()
        self.port = listen_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("localhost", self.port))
        self.sock.listen()
        self.sock.settimeout(1)
        logging.basicConfig(filename="server.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s: %(message)s")

        logging.info("Server started")
        self.listen_thread = threading.Thread(target=self.listen_for_jobs, args=())
        self.listen_thread.daemon = True
        self.listen_thread.start()

        self.shutdown_thread = threading.Thread(target=self.user_shutdown, args=())
        self.shutdown_thread.start()

        self.shutdown_thread.join()

        logging.info("Server shutdown")

    def __del__(self):
        print("Server destructor called")
        self.sock.close()
        cleanup_utils()

    def get_unused_port(self):
        port = randint(self.PORT_MIN, self.PORT_MAX)
        while port in self.used_ports:
            port = randint(self.PORT_MIN, self.PORT_MAX)
        self.used_ports.add(port)
        return port

    def get_client_response(self, listen_sock):
        client_response = None
        while client_response is None:
            message_chunks = get_data_from_connection(listen_sock)

            if not message_chunks:
                continue

            try:
                message_dict = decode_message_chunks(message_chunks)
                client_response = message_dict
                break
            except JSONDecodeError:
                continue
        return client_response

    def user_shutdown(self):
        print("Press \"enter\" at any time to shutdown the server.")
        timeout = 0.5
        while not self.shutdown:
            logging.info("Top of shutdown prompt loop")
            i, _, _ = select([stdin], [], [], timeout)
            if (i):
                self.shutdown = True
                logging.info("Shutting down the server...")
                break

    def listen_for_jobs(self):
        while not self.shutdown:
            message_chunks = get_data_from_connection(self.sock)

            if not message_chunks:
                # catch socket timeout from get_data_from_connection
                logging.info("Timed out on sock.accept()")
                continue
                
            try:
                # decode the message and spawn a new thread to handle it
                message_dict = decode_message_chunks(message_chunks)
                print(type(message_dict))
                logging.info("Successfully received message from client. Spawning a new thread to handle the job.")
                handle_job_thread = threading.Thread(target=self.handle_job, args=(message_dict,))
                handle_job_thread.start()
            except JSONDecodeError:
                continue

    def handle_job(self, job_json):
        print(type(job_json))
        print(job_json)
        try:
            client_port = job_json['port']
        except KeyError:
            logging.error("Client message did not include entry \"client_port\" to report back results.")
            return
        
        self.used_ports.add(client_port)

        try:
            action = job_json['action']
        except KeyError:
            text = "Client message did not include entry \"action\" to let the server know an action to take (add/delete/read/update)"
            logging.error(text)
            msg = {
                'status': 'error',
                'text': text
            }
            send_message("localhost", client_port, msg)
            return

        try:
            data_type = job_json['data_type']
        except KeyError:
            text = "Client message did not include entry \"data_type\" to let the server know which table to work with."
            logging.error(text)
            msg = {
                'status': 'error',
                'text': text
            }
            send_message("localhost", client_port, msg)
            return

        if data_type not in ["vehicle", "engineer", "laptop", "contact_details"]:
            text = "Client message entry \"data_type\" is not one of [\"vehicle\", \"engineer\", \"laptop\", \"contact_details\"]"
            logging.error(text)
            msg = {
                'status': 'error',
                'text': text
            }
            send_message("localhost", client_port, msg)
            return

        if action == "add":
            if data_type == "vehicle":
                self.add_vehicle(job_json, client_port)

            elif data_type == "engineer":
                self.add_engineer(job_json, client_port)
            
            elif data_type == "laptop":
                self.add_laptop(job_json, client_port)
            
            elif data_type == "contact_details":
                self.add_contact_details(job_json, client_port) 

        elif action == "delete":
            if data_type == "vehicle":
                self.delete_vehicle(job_json, client_port)
            
            elif data_type == "engineer":
                self.delete_engineer(job_json, client_port)

            elif data_type == "laptop":
                self.delete_laptop(job_json, client_port)
            
            elif data_type == "contact_details":
                self.delete_contact_details(job_json, client_port)

        elif action == "read":
            if data_type == "vehicle":
                self.query_vehicle(job_json, client_port)
            
            elif data_type == "engineer":
                self.query_engineer(job_json, client_port)

            elif data_type == "laptop":
                self.query_laptop(job_json, client_port)

            elif data_type == "contact_details":
                self.query_contact_details(job_json, client_port)

        else:
            text = f"Client message entry \"action\": {action} must be one of [\"add\", \"delete\", \"read\"]"
            logging.error(text)
            msg = {
                'status': 'error',
                'text': text
            }
            send_message("localhost", client_port, msg)
            return

    def add_vehicle(self, job_json, client_port):
        msg = {
            'status': None
        }

        # Attempt to add a vehicle to the database
        error_text = "Client vehicle insert job has no entry for \"{}\""
        try:
            model = job_json['model']
        except:
            logging.error(error_text.format("model"))
            msg['status'] = 'error'
            msg['text'] = error_text.format("model")
            send_message("localhost", client_port, msg)
            return
        
        try:
            quantity = job_json['quantity']
        except:
            logging.error(error_text.format("quantity"))
            msg['status'] = "error"
            msg['text'] = error_text.format("quantity")
            send_message("localhost", client_port, msg)
            return

        try:
            price = job_json['price']
        except:
            logging.error(error_text.format("price"))
            msg['status'] = 'error'
            msg['text'] = error_text.format("price")
            send_message("localhost", client_port, msg)
            return

        try:
            manufacture_year = job_json['manufacture_year']
        except:
            logging.error(error_text.format("manufacture_year"))
            msg['status'] = 'error'
            msg['text'] = error_text.format("manufacture_year")
            send_message("localhost", client_port, msg)
            return
        
        try:
            manufacture_month = job_json["manufacture_month"]
        except:
            logging.error(error_text.format("manufacture_month"))
            msg["status"] = "error"
            msg["text"] = error_text.format("manufacture_month")
            send_message("localhost", client_port, msg)
            return
        
        try:
            manufacture_date = job_json["manufacture_date"]
        except:
            logging.error(error_text.format("manufacture_date"))
            msg["status"] = "error"
            msg["text"] = error_text.format("manufacture_date")
            send_message("localhost", client_port, msg)
            return

        full_manufacture_date = date(manufacture_year, manufacture_month, manufacture_date)
        new_car = self.car_utils.add_vehicle_db(model, quantity, price, full_manufacture_date)

        # If it already exists, let client know we updated quantity and return
        if new_car is None:
            text = f"Vehicle model {model} manufactured on {full_manufacture_date} already exists in the database.\n" + \
                   f"Updated quantity of {model} vehicles by {quantity}."
            logging.info(text)
            msg["status"] = "updated"
            msg["text"] = text
            send_message("localhost", client_port, msg)
            return

        # Else, let client know new vehicle was added
        new_port = self.get_unused_port()
        logging.info(f"Successfully added new vehicle {model} manufactured on {full_manufacture_date} to the database.")
        msg["status"] = "success"
        msg["port"] = new_port
        new_car_json = new_car.to_json()
        send_message("localhost", client_port, {**msg, **new_car_json})

        # Grab an unused port and bind a new socket to it to listen for more client messages
        # Make sure messages to the client tells it the new port to respond to
        
        new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        new_sock.bind(("localhost", new_port))
        new_sock.listen()
        new_sock.settimeout(1)
        logging.info("Waiting for client to respond \"yes\" or \"no\" to assigning engineers.")
        
        # Wait for client to respond "yes" or "no" to assigning engineers
        client_response = self.get_client_response(new_sock)

        try:
            add_engins = client_response['response']
        except:
            text = "Client did not include entry \"response\" to let the server know whether they wanted to assign engineers to the new vehicle."
            logging.error(text)
            msg = {
                "status": "error",
                "text": text
            }
            send_message("localhost", client_port, msg)
            new_sock.close()
            self.used_ports.remove(new_port)
            return
        
        # If client responds "no", no need for further action

        # If client responds "yes", try adding their list of engineers

        if add_engins == "y":
            # Keep lists of successfully assigned and unassigned engineers
            assigned_names = []
            unassigned_names = []
            new_engins = []
            try:
                engineers = client_response["engineers"]
            except:
                text = "Client did not include entry \"engineers\" to let the server know which engineers to assign to the new vehicle."
                logging.error(text)
                msg = {
                    "status": "error",
                    "text": text
                }
                send_message("localhost", client_port, msg)
                new_sock.close()
                self.used_ports.remove(new_port)
            
            for name in engineers:
                name = name.strip()
                engin = self.engin_utils.read_engineer_by_name(name)
                if engin is None:
                    # If engineer doesn't exist, store in unassigned list
                    logging.info(f"Engineer {name} does not exist in the database. Cannot assign them to the new vehicle.")
                    unassigned_names.append(name)
                    continue
                else:
                    # Else, store in assigned list
                    assigned_names.append(name)
                    new_engins.append(engin)
                    self.car_utils.update_vehicle_db(new_car.id, engineers=new_engins)
                    logging.info(f"Engineer {name} successfully assigned to new vehicle.")

            # Send both lists in final message to client once done
            msg["status"] = "success"
            msg["assigned"] = assigned_names
            msg["unassigned"] = unassigned_names
            logging.info("Finished assigning engineers to the new vehicle.")
            send_message("localhost", client_port, msg)

        # Close new socket
        new_sock.close()
        self.used_ports.remove(new_port)

    def delete_vehicle(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            model = job_json["model"]
        except:
            error_msg = "Client vehicle delete job has no entry for \"model\"."
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        models_deleted = self.car_utils.delete_vehicle_by_model(model)
        if models_deleted:
            logging.info(f"Successfully deleted all {model} model vehicles.")
            msg["status"] = "success"
            send_message("localhost", client_port, msg)
        else:
            error_msg = f"No vehicles of model {model} existed in the database to be deleted."
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
        return

    def query_vehicle(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            model = job_json["model"]
        except:
            error_msg = "Client vehicle read job has no entry for \"model\""
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        cars = []
        if model == "":
            try:
                id = job_json["id"]
            except:
                error_msg = "Client vehicle read job entered a blank model name, but did not have an entry for \"id\""
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            logging.info(f"Attempting to read vehicle id {id} from the database.")
            car = self.car_utils.read_vehicle_by_id(id)
            if car is None:
                error_msg = f"No vehicle with id {id} exists in the database."
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            msg["status"] = "success"
            msg["vehicles"] = [car.to_json()]
            logging.info(f"Successfully read vehicle id {id} from the database:" + str(car))
            send_message("localhost", client_port, msg)
            return
        
        elif model == "all":
            logging.info("Attempting to read all vehicles from the database.")
            cars = self.car_utils.read_vehicles_all()

        else:
            logging.info(f"Attempting to read all {model} model vehicles from the database.")
            cars = self.car_utils.read_vehicles_by_model(model)
        
        if not cars:
            error_msg = f"No cars with model {model} were found in the database."
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
        
        logging.info(f"Vehicle read on {model} model vehicles successful.")
        msg["status"] = "success"
        msg["vehicles"] = [car.to_json() for car in cars]
        send_message("localhost", client_port, msg)

    def add_engineer(self, job_json, client_port):
        msg = {
            'status': None
        }
        
        # Attempt to add an engineer to the database
        error_text = "Client engineer insert job has no entry for \"{}\""
        try:
            engin_name = job_json["name"]
        except:
            logging.error(error_text.format("name"))
            msg["status"] = "error"
            msg["text"] = error_text.format("name")
            send_message("localhost", client_port, msg)
            return
        
        try:
            birth_year = job_json["birth_year"]
        except:
            logging.error(error_text.format("birth_year"))
            msg["status"] = "error"
            msg["text"] = error_text.format("birth_year")
            send_message("localhost", client_port, msg)
            return

        try:
            birth_month = job_json["birth_month"]
        except:
            logging.error(error_text.format("birth_month"))
            msg["status"] = "error"
            msg["text"] = error_text.format("birth_month")
            send_message("localhost", client_port, msg)
            return

        try:
            birth_date = job_json["birth_date"]
        except:
            logging.error(error_text.format("birth_date"))
            msg["status"] = "error"
            msg["text"] = error_text.format("birth_date")
            send_message("localhost", client_port, msg)
            return
        
        full_birth_date = date(birth_year, birth_month, birth_date)
        new_engin = self.engin_utils.add_engineer_db(engin_name, full_birth_date)

        if new_engin is None:
            text = f"Engineer named {engin_name} already exists in the database.\n" + \
                   f"Aborted adding duplicate engineer {engin_name} to the database."
            logging.error(text)
            msg["status"] = "error"
            msg["text"] = text
            send_message("localhost", client_port, msg)
            return

        new_port = self.get_unused_port()
        text = f"Successfully added new engineer {engin_name} to the database!"
        logging.info(text)
        msg["status"] = "success"
        msg["port"] = new_port
        new_engin_json = new_engin.to_json()
        send_message("localhost", client_port, {**msg, **new_engin_json})

        new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        new_sock.bind(("localhost", new_port))
        new_sock.listen()
        new_sock.settimeout(1)
        logging.info("Waiting for client to respond \"yes\" or \"no\" to assign new engineer to vehicles.")

        # Wait for client to respond "yes" or "no" to assigning vehicles
        client_response = self.get_client_response(new_sock)

        try:
            add_vehicles = client_response['response']
        except:
            text = "Client did not include entry \"response\" to let the server know whether to assign the new engineer to any vehicles."
            logging.error(text)
            msg = {
                "status": "error",
                "text": text
            }
            send_message("localhost", client_port, msg)
            new_sock.close()
            self.used_ports.remove(new_port)
            return

        if add_vehicles == 'y':
            logging.info(f"Attempting to assign engineer {engin_name} to vehicle models")
            assigned = []
            unassigned = []

            try:
                vehicles = client_response['vehicles']
            except:
                text = "Client response did not include entry \"vehicles\" to let the server know which vehicles to assign the new engineer to."
                logging.error(text)
                msg = {
                    "status": "error",
                    "text": text
                }
                send_message("localhost", client_port, msg)
                new_sock.close()
                self.used_ports.remove(new_port)
                return
            
            for car_model in vehicles:
                car_model = car_model.strip()
                cars = self.car_utils.read_vehicles_by_model(car_model)
                if not cars:
                    logging.error(f"No vehicles of model {car_model} exist in the database. Cannot assign engineer {engin_name} to this model.")
                    unassigned.append(car_model)
                    continue

                for car in cars:
                    new_engins_list = car.engineers + [new_engin]
                    self.car_utils.update_vehicle_db(car.id, engineers=new_engins_list)
                    assignment_msg = f"Successfully assigned {engin_name} to vehicle {car_model} manufactured on {car.manufacture_date}"
                    logging.info(assignment_msg)
                assigned.append(car_model)
            
            msg["status"] = "success"
            msg["assigned"] = assigned
            msg["unassigned"] = unassigned
            logging.info(f"Finished assigning vehicles to the new engineer {engin_name}")
            send_message("localhost", client_port, msg)

        new_sock.close()
        self.used_ports.remove(new_port)


    def delete_engineer(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            name = job_json["name"]
        except:
            error_msg = "Client engineer delete job has no entry for \"name\""
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        engin = self.engin_utils.read_engineer_by_name(name)
        if engin is None:
            error_msg = f"Engineer {name} doesn't exist in the database. Aborted deleting non-existant engineer."
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        self.engin_utils.delete_engineer_by_name(name)
        logging.info(f"Successfully deleted engineer {name} from the database.")
        msg["status"] = "success"
        send_message("localhost", client_port, msg)
        return


    def query_engineer(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            name = job_json["name"]
        except:
            error_msg = "Client engineer read job has no entry for \"name\""
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        if name == "":
            try:
                id = job_json["id"]
            except:
                error_msg = "Client left engineer name blank, but did not provide an entry for \"id\""
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            logging.info(f"Attempting to read engineer with id {id} from the database.")
            engin = self.engin_utils.read_engineer_by_id(id)
            if engin is None:
                error_msg = f"No engineer with id {id} exists in the database"
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            msg["status"] = "success"
            msg["engineers"] = [engin.to_json()]
            logging.info(f"Successfully read engineer with id {id}:" + str(engin))
            send_message("localhost", client_port, msg)
        elif name == "all":
            logging.info("Attempting to read all engineers.")
            engins = self.engin_utils.read_all_engineers()
            msg["engineers"] = [eng.to_json() for eng in engins]
        
        else:
            logging.info(f"Attempting to read engineer named {name}")
            engin = self.engin_utils.read_engineer_by_name(name)
            if engin is None:
                error_msg = f"No engineer named {name} exists in the database"
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            msg["engineers"] = [engin.to_json()]
        
        logging.info(f"Engineer(s) successfully read from the database.")
        msg["status"] = "success"
        send_message("localhost", client_port, msg)


    def add_laptop(self, job_json, client_port):
        msg = {
            "status": None
        }

        # Attempt to add a laptop to the database
        error_text = "Client laptop insert job has no entry for \"{}\""
        try:
            model = job_json["model"]
        except:
            logging.error(error_text.format("model"))
            msg["status"] = "error"
            msg["text"] = error_text.format("model")
            send_message("localhost", client_port, msg)
            return
        
        try:
            loan_year = job_json["loan_year"]
        except:
            logging.error(error_text.format("loan_year"))
            msg["status"] = "error"
            msg["text"] = error_text.format("loan_year")
            send_message("localhost", client_port, msg)
            return

        try:
            loan_month = job_json["loan_month"]
        except:
            logging.error(error_text.format("loan_month"))
            msg["status"] = "error"
            msg["text"] = error_text.format("loan_month")
            send_message("localhost", client_port, msg)
            return
        
        try:
            loan_date = job_json["loan_date"]
        except:
            logging.error(error_text.format("loan_date"))
            msg["status"] = "error"
            msg["text"] = error_text.format("loan_date")
            send_message("localhost", client_port, msg)
            return
        
        try:
            engin_name = job_json["engineer"]
        except:
            logging.error(error_text.format("engineer"))
            msg["status"] = "error"
            msg["text"] = error_text.format("engineer")
            send_message("localhost", client_port, msg)
            return
        
        new_port = self.get_unused_port()
        new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        new_sock.bind(("localhost", new_port))
        new_sock.listen()
        new_sock.settimeout(1)

        # First, if engineer doesn't exist in the database, prompt client if we should add it without loaning to an engineer
        engin = self.engin_utils.read_engineer_by_name(engin_name)
        if engin is None:
            no_engin_text = f"Engineer {engin_name} does not exist in the database. Prompting client as to whether the laptop should be added without a loaner."
            logging.info(no_engin_text)
            msg["status"] = "no_engineer"
            msg["text"] = no_engin_text
            msg["port"] = new_port
            send_message("localhost", client_port, msg)

            client_response = self.get_client_response(new_sock)
            try:
                proceed = client_response["response"]
            except:
                error_msg = "Client response has no entry \"response\" to let the server know whether to add the laptop or not."
                logging.error(error_msg)
                msg = {
                    "status": "error",
                    "text": error_msg
                }
                send_message("localhost", client_port, msg)
                new_sock.close()
                self.used_ports.remove(new_port)
                return
            
            if proceed == 'n':
                logging.info("Client chose not to proceed with adding the laptop.")
                new_sock.close()
                self.used_ports.remove(new_port)
                return
            
        # Second, see if the engineer already has a laptop loaned to them. Prompt to replace if so
        prev_laptop = self.laptop_utils.read_laptop_by_owner(engin_name)
        if prev_laptop is not None:
            prev_owner_text = f"Engineer {engin_name} already has a laptop loaned to them. Prompting client to see if we should add the laptop and replace the currently loaned one."
            logging.info(prev_owner_text)
            msg["status"] = "previous_laptop"
            msg["text"] = prev_owner_text
            msg["port"] = new_port
            send_message("localhost", client_port, msg)

            client_response = self.get_client_response(new_sock)

            try:
                replace = client_response["response"]
            except:
                error_msg = "Client response has no entry \"response\" to let the server know whether to replace the engineer's currently loaned laptop."
                logging.error(error_msg)
                msg = {
                    "status": "error",
                    "text": error_msg
                }
                send_message("localhost", client_port, msg)
                new_sock.close()
                self.used_ports.remove(new_port)
            
            if replace == 'n':
                logging.info("Client chose not to replace the engineer's current laptop.\nAborted adding new laptop")
                new_sock.close()
                self.used_ports.remove(new_port)
            
        # Finally, add the laptop and send success/error back to client
        new_laptop = self.laptop_utils.add_laptop_db(model, date(loan_year, loan_month, loan_date), engin_name)
        if new_laptop is None:
            logging.error("Laptop already exists in the database. Aborted adding the duplicate laptop.")
            msg["status"] = "error"
            msg["text"] = "Laptop already exists in the database. Aborted adding the duplicate laptop."
            send_message("localhost", client_port, msg)
            new_sock.close()
            self.used_ports.remove(new_port)
            return
        
        new_laptop_json = new_laptop.to_json()
        msg["status"] = "success"
        if engin is None:
            logging.info(f"Successfully added laptop {model}, but it is not loaned by any engineer.")
        else:
            logging.info(f"Successfully added laptop {model} and loaned it to engineer {engin_name}")
        
        msg["replaced"] = False if prev_laptop is None else True
        send_message("localhost", client_port, {**msg, **new_laptop_json})
        
        new_sock.close()
        self.used_ports.remove(new_port)


    def delete_laptop(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            engin_name = job_json["engineer"]
        except:
            error_msg = "Client laptop delete job had no entry for \"engineer\""
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        if engin_name == "":
            try:
                laptop_id = job_json["id"]
            except:
                error_msg = "Client unowned laptop delete job had no entry for \"id\""
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            
            try:
                logging.info(f"Attempting to delete laptop with id {laptop_id}")
                self.laptop_utils.delete_laptop_by_id(laptop_id)
                success_msg = f"Successfully deleted laptop with id {laptop_id}"
                logging.info(success_msg)
                msg["status"] = "success"
                send_message("localhost", client_port, msg)
                return
            except UnmappedInstanceError:
                error_msg = f"Laptop with id {laptop_id} has already been deleted from the database."
                msg["status"] = "error"
                msg["text"] = error_msg
                logging.error(error_msg)
                send_message("localhost", client_port, msg)
                return
        else:
            logging.info(f"Attempting to delete laptop loaned by {engin_name}")
            self.laptop_utils.delete_laptop_by_owner(engin_name)
            logging.info(f"Successfully deleted laptop loaned by {engin_name}")
            msg["status"] = "success"
            send_message("localhost", client_port, msg)
        

    def query_laptop(self, job_json, client_port):
        pass

    def add_contact_details(self, job_json, client_port):
        msg = {
            "status": None
        }

        error_msg = "Client contact details insert job has no entry for \"{}\""
        try:
            engin_name = job_json["engineer"]
        except:
            logging.error(error_msg.format("engineer"))
            msg["status"] = "error"
            msg["text"] = error_msg.format("engineer")
            send_message("localhost", client_port, msg)
            return
        
        try:
            phone_number = job_json["phone_number"]
        except:
            logging.error(error_msg.format("phone_number"))
            msg["status"] = "error"
            msg["text"] = error_msg.format("phone_number")
            send_message("localhost", client_port, msg)
            return

        try:
            address = job_json["address"]
        except:
            logging.error(error_msg.format("address"))
            msg["status"] = "error"
            msg["text"] = error_msg.format("address")
            send_message("localhost", client_port, msg)
            return
        
        # Attempt to add the new contact details, report error to client if duplicate or engineer doesn't exist
        engin = self.engin_utils.read_engineer_by_name(engin_name)
        if engin is None:
            error_msg = f"Engineer {engin_name} does not exist in the database. Contact details cannot be added for a non-existant engineer."
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        new_contact = self.contact_utils.add_contact_details_db(phone_number, address, engin_name)
        if new_contact is None:
            error_msg = f"Detected duplicate contact details. Aborted adding duplicate."
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        success_msg = f"Successfully added contact details for engineer {engin_name}"
        new_contact_json = new_contact.to_json()
        logging.info(success_msg)
        msg["status"] = "success"
        send_message("localhost", client_port, {**msg, **new_contact_json})
        return
     

    def delete_contact_details(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            engin_name = job_json["engineer"]
        except:
            error_msg = "Client contact details delete job had no entry for \"engineer\""
            logging.error(error_msg)
            msg["status"] = "error"
            msg["text"] = error_msg
            send_message("localhost", client_port, msg)
            return
        
        if engin_name == "":
            try:
                contact_id = job_json["id"]
            except:
                error_msg = f"Client response ommitted engineer name but did not have an entry for contact details \"id\""
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            
            try:
                logging.info(f"Attempting to delete contact details with ID {contact_id}")
                self.contact_utils.delete_contact_details_by_id(contact_id)
                success_msg = f"Successfully deleted contact details with ID {contact_id}"
                msg["status"] = "success"
                send_message("localhost", client_port, msg)
                return
            except UnmappedInstanceError:
                error_msg = f"Contact details with ID {contact_id} has already been deleted from the database."
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
        else:
            engin = self.engin_utils.read_engineer_by_name(engin_name)
            if engin is None:
                error_msg = f"Engineer {engin_name} does not exist in the database.\nAborted deleting contact details for non-existant engineer {engin_name}"
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return
            logging.info(f"Attempting to delete contact details for engineer {engin_name}")

            try:
                self.contact_utils.delete_contact_details_by_engin_id(engin.id)
                logging.info(f"Successfully deleted all contact details for engineer {engin_name}")
                msg["status"] = "success"
                send_message("localhost", client_port, msg)
                return
            except UnmappedInstanceError:
                error_msg = f"Engineer {engin_name} has no contact details to delete. Aborted deleting non-existant contact details."
                logging.error(error_msg)
                msg["status"] = "error"
                msg["text"] = error_msg
                send_message("localhost", client_port, msg)
                return


    def query_contact_details(self, job_json, client_port):
        pass

@click.command()
@click.argument("port", nargs=1, type=int)
def main(port):
    Server(port)

if __name__ == "__main__":
    main()