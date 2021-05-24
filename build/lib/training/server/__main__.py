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
from training.server.db_utils import VehicleUtils, EngineerUtils, LaptopUtils, ContactDetailsUtils, cleanup_utils
from training.sock_utils import send_message, decode_message_chunks, get_data_from_connection
from training.server.reset import reset_db
from json import JSONDecodeError
from random import randint
from datetime import date

class Server:
    
    def __init__(self, listen_port, handle_jobs_multithreaded=False):
        logging.basicConfig(filename="server.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s: %(message)s")
        self.shutdown = False
        self.multithreaded = handle_jobs_multithreaded
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
        logging.info(f"Bound server socket to {self.port}")
        self.sock.listen()
        self.sock.settimeout(1)
        

        logging.info("Server started")
        self.db_lock = threading.Lock()
        self.listen_thread = threading.Thread(target=self.listen_for_jobs, args=(handle_jobs_multithreaded,))
        self.listen_thread.daemon = True
        self.listen_thread.start()
        logging.info("Listen thread started")
        self.shutdown_thread = threading.Thread(target=self.user_shutdown, args=())
        self.shutdown_thread.start()
        logging.info("User Shutdown Input thread started")
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

    def send_error_msg(self, error_msg, client_port):
        msg = {
            "status": "error",
            "text": error_msg
        }
        logging.error(error_msg)
        self.try_send_message("localhost", client_port, msg)

    def call_with_lock(self, func, *args, **kwargs):
        if self.multithreaded:
            with self.db_lock:
                res = func(*args, **kwargs)
                return res
        else:
            res = func(*args, **kwargs)
            return res

    def try_send_message(self, host, client_port, msg):
        try:
            send_message(host, client_port, msg)
        except ConnectionRefusedError:
            error_msg = f"ConnectionRefusedError: socket.connect to client port {client_port} refused (likely cause is no open socket on port {client_port}"
            logging.error(error_msg)
            return False
        return True

    def user_shutdown(self):
        print("Press \"enter\" at any time to shutdown the server.")
        timeout = 0.5
        while not self.shutdown:
            i, _, _ = select([stdin], [], [], timeout)
            if (i):
                self.shutdown = True
                logging.info("Shutting down the server...")
                break

    def listen_for_jobs(self, single_threaded=False):
        while not self.shutdown:
            message_chunks = get_data_from_connection(self.sock)

            if not message_chunks:
                # catch socket timeout from get_data_from_connection
                continue
                
            try:
                # decode the message and spawn a new thread to handle it
                message_dict = decode_message_chunks(message_chunks)
                print(type(message_dict))
                
                if single_threaded:
                    logging.info(f"Successfully received message from client. Handling job on this thread {message_dict}.")
                    self.handle_job(message_dict)
                else:
                    logging.info(f"Successfully received message from client. Spawning a new thread to handle job {message_dict}.")
                    handle_job_thread = threading.Thread(target=self.handle_job, args=(message_dict,))
                    handle_job_thread.start()
            except JSONDecodeError:
                continue

    def handle_job(self, job_json):
        print(type(job_json))
        print(job_json)
        try:
            action = job_json['action']
        except KeyError:
            text = "Client message did not include entry \"action\" to let the server know an action to take (add/delete/read/update)"
            self.send_error_msg(text)
            return
        
        if action == "reset":
            logging.info("Resetting the database...")
            #with self.db_lock:
                #logging.info("DB_lock held by reset thread")
            reset_db()
            logging.info("Database successfully reset.")
            return

        try:
            client_port = job_json['port']
        except KeyError:
            logging.error("Client message did not include entry \"port\" to report back results.")
            return
        
        self.used_ports.add(client_port)

        try:
            data_type = job_json['data_type']
        except KeyError:
            text = "Client message did not include entry \"data_type\" to let the server know which table to work with."
            self.send_error_msg(text)
            return

        if data_type not in ["vehicle", "engineer", "laptop", "contact_details", "vehicle_engineers"]:
            text = "Client message entry \"data_type\" is not one of [\"vehicle\", \"engineer\", \"laptop\", \"contact_details\", \"vehicle_engineers\"]"
            self.send_error_msg(text)
            return

        vehicle_engineers_error_msg = f"Data type vehicle_engineers only supports the \"read\" action and does not support action \"{action}\""

        if action == "add":
            if data_type == "vehicle":
                self.add_vehicle(job_json, client_port)

            elif data_type == "engineer":
                self.add_engineer(job_json, client_port)
            
            elif data_type == "laptop":
                self.add_laptop(job_json, client_port)
            
            elif data_type == "contact_details":
                self.add_contact_details(job_json, client_port)
            
            elif data_type == "vehicle_engineers":
                self.send_error_msg(vehicle_engineers_error_msg, client_port)
                return

        elif action == "delete":
            if data_type == "vehicle":
                self.delete_vehicle(job_json, client_port)
            
            elif data_type == "engineer":
                self.delete_engineer(job_json, client_port)

            elif data_type == "laptop":
                self.delete_laptop(job_json, client_port)
            
            elif data_type == "contact_details":
                self.delete_contact_details(job_json, client_port)
            
            elif data_type == "vehicle_engineers":
                self.send_error_msg(vehicle_engineers_error_msg, client_port)


        elif action == "read":
            if data_type == "vehicle":
                self.query_vehicle(job_json, client_port)
            
            elif data_type == "engineer":
                self.query_engineer(job_json, client_port)

            elif data_type == "laptop":
                self.query_laptop(job_json, client_port)

            elif data_type == "contact_details":
                self.query_contact_details(job_json, client_port)
            
            elif data_type == "vehicle_engineers":
                self.query_vehicle_engineers(job_json, client_port)
            
        elif action == "update":
            if data_type == "vehicle":
                self.update_vehicle(job_json, client_port)
            
            elif data_type == "engineer":
                self.update_engineer(job_json, client_port)

            elif data_type == "laptop":
                self.update_laptop(job_json, client_port)
                
            else:
                unimplemented_err = f"Server action \"update\" is not yet implemented for data type \"{data_type}\""
                self.send_error_msg(unimplemented_err, client_port)
                return

        else:
            text = f"Client message entry \"action\": {action} must be one of [\"add\", \"delete\", \"read\"]"
            self.send_error_msg(text)
            return

    def query_vehicle_engineers(self, job_json, client_port):
        msg = {
            "status": None
        }

        model = engineer = None
        try:
            model = job_json["model"]
        except:
            logging.info("Client vehicle_engineers read job had no entry for \"model\". Attempting to read by \"engineer\" instead.")
        
        try:
            engineer = job_json["engineer"]
        except:
            logging.info("Client vehicle_engineers read job had no entry for \"engineer\".")
            if model is None:
                error_msg = "Aborted reading vehicle_engineers relationship because client did not provide either \"model\" nor \"engineer\"."
                self.send_error_msg(error_msg, client_port)
                return
        
        if model is not None:
            try:
                engineers = self.car_utils.read_assigned_engineers_by_model(model)
            except AttributeError:
                error_msg = f"No model {model} vehicles exist in the database."
                self.send_error_msg(error_msg, client_port)
                return

            if not engineers:
                error_msg = f"No engineers are assigned to any model {model} vehicles."
                self.send_error_msg(error_msg, client_port)
                return
            
            msg["status"] = "success"
            msg["engineers"] = [engin.to_json() for engin in engineers]
            logging.info(f"Successfully read engineers assigned to vehicle model {model}")

        if engineer is not None:
            try:
                cars = self.engin_utils.read_assigned_vehicles_by_name(engineer)
            except AttributeError:
                error_msg = f"Engineer {engineer} does not exist in the database."
                self.send_error_msg(error_msg, client_port)
                return

            if not cars:
                error_msg = f"No vehicles are assigned to engineer {engineer}"
                self.send_error_msg(error_msg, client_port)
                return

            msg["status"] = "success"
            msg["vehicles"] = [car.to_json() for car in cars]
            logging.info(f"Successfully read vehicles engineer {engineer} is assigned to")
        
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
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
            self.send_error_msg(error_text.format("model"), client_port)
            return
        
        try:
            quantity = job_json['quantity']
        except:
            self.send_error_msg("quantity", client_port)
            return

        try:
            price = job_json['price']
        except:
            self.send_error_msg("price", client_port)
            return

        try:
            manufacture_year = job_json['manufacture_year']
        except:
            self.send_error_msg("manufacture_year", client_port)
            return
        
        try:
            manufacture_month = job_json["manufacture_month"]
        except:
            self.send_error_msg("manufacture_month", client_port)
            return
        
        try:
            manufacture_date = job_json["manufacture_date"]
        except:
            self.send_error_msg("manufacture_date", client_port)
            return

        try:
            full_manufacture_date = date(manufacture_year, manufacture_month, manufacture_date)
        except ValueError as err:
            self.send_error_msg(f"ValueError: {err}", client_port)
            return
        new_car = self.call_with_lock(self.car_utils.add_vehicle_db, model, quantity, price, full_manufacture_date)

        # If it already exists, let client know we updated quantity and return
        if new_car is None:
            text = f"Vehicle model {model} manufactured on {full_manufacture_date} already exists in the database.\n" + \
                   f"Updated quantity of {model} vehicles by {quantity}."
            logging.info(text)
            msg["status"] = "updated"
            msg["text"] = text
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return
            return

        # Else, let client know new vehicle was added
        new_port = self.get_unused_port()
        logging.info(f"Successfully added new vehicle {model} manufactured on {full_manufacture_date} to the database.")
        msg["status"] = "success"
        msg["port"] = new_port
        new_car_json = new_car.to_json()
        success = self.try_send_message("localhost", client_port, {**msg, **new_car_json})
        if not success:
            return

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
            self.send_error_msg(text, client_port)
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
                self.send_error_msg(text, client_port)
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
                    self.call_with_lock(self.car_utils.update_vehicle_db, new_car.id, engineers=new_engins)
                    logging.info(f"Engineer {name} successfully assigned to new vehicle.")

            # Send both lists in final message to client once done
            msg["status"] = "success"
            msg["assigned"] = assigned_names
            msg["unassigned"] = unassigned_names
            logging.info("Finished assigning engineers to the new vehicle.")
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return

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
            self.send_error_msg(error_msg, client_port)
            return
        models_deleted = self.call_with_lock(self.car_utils.delete_vehicle_by_model, model)
        if models_deleted:
            logging.info(f"Successfully deleted all {model} model vehicles.")
            msg["status"] = "success"
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return
        else:
            error_msg = f"No vehicles of model {model} existed in the database to be deleted."
            self.send_error_msg(error_msg, client_port)
        return

    def query_vehicle(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            model = job_json["model"]
        except:
            error_msg = "Client vehicle read job has no entry for \"model\""
            self.send_error_msg(error_msg, client_port)
            return
        cars = []
        if model == "":
            try:
                id = job_json["id"]
            except:
                error_msg = "Client vehicle read job entered a blank model name, but did not have an entry for \"id\""
                self.send_error_msg(error_msg, client_port)
                return
            logging.info(f"Attempting to read vehicle id {id} from the database.")
            car = self.car_utils.read_vehicle_by_id(id)
            if car is None:
                error_msg = f"No vehicle with id {id} exists in the database."
                self.send_error_msg(error_msg, client_port)
                return
            msg["status"] = "success"
            msg["vehicles"] = [car.to_json()]
            logging.info(f"Successfully read vehicle id {id} from the database:" + str(car))
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return
            return
        
        elif model == "all":
            logging.info("Attempting to read all vehicles from the database.")
            cars = self.car_utils.read_vehicles_all()

        else:
            logging.info(f"Attempting to read all {model} model vehicles from the database.")
            cars = self.car_utils.read_vehicles_by_model(model)
        
        if not cars:
            error_msg = f"No cars with model {model} were found in the database."
            self.send_error_msg(error_msg, client_port)
        
        logging.info(f"Vehicle read on {model} model vehicles successful.")
        msg["status"] = "success"
        msg["vehicles"] = [car.to_json() for car in cars]
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return

    def update_vehicle(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            vehicle_id = job_json["id"]
        except:
            error_msg = "Client update vehicle job did not have an entry for \"id\""
            self.send_error_msg(error_msg, client_port)
            return
        
        logging.info(f"Attempting to update vehicle with id {vehicle_id}")

        curr_car = self.car_utils.read_vehicle_by_id(vehicle_id)

        if curr_car is None:
            error_msg = f"No vehicle with id {vehicle_id} exists in the database. Cannot update a vehicle that doesn't exist."
            self.send_error_msg(error_msg)
            return

        model = quantity = price = manufacture_year = manufacture_month = manufacture_date = engineer_names = engineers = None

        missing_entry_msg = "Client did not provide an entry for \"{entry_name}\". Skipping update for \"{entry_name}\" in the database."
        try:
            model = job_json["model"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "model"))
        
        try:
            quantity = job_json["quantity"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "quantity"))

        try:
            price = job_json["price"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "price"))

        try:
            manufacture_year = job_json["manufacture_year"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "manufacture_year"))
            manufacture_year = curr_car.manufacture_date.year
        
        try:
            manufacture_month = job_json["manufacture_month"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "manufacture_month"))
            manufacture_month = curr_car.manufacture_date.month
        
        try:
            manufacture_date = job_json["manufacture_date"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "manufacture_date"))
            manufacture_date = curr_car.manufacture_date.day
        
        try:
            engineer_names = job_json["engineers"]
            engineers = []
            for name in engineer_names:
                engin = self.engin_utils.read_engineer_by_name(name)
                if engin is not None:
                    engineers.append(engin)
            engineers = None if not engineers else engineers
        except:
            logging.info(missing_entry_msg.format("engineers"))
        
        full_manufacture_date = None
        try:
            full_manufacture_date = date(manufacture_year, manufacture_month, manufacture_date)
        except:
            logging.info("Client left one of the manufacture date fields empty. Skipping update for manufacture date fields.")

        car = self.call_with_lock(self.car_utils.update_vehicle_db, vehicle_id, model, quantity, price, full_manufacture_date, engineers)

        if car is None:
            error_msg = f"There was an issue updating vehicle id {vehicle_id}. Most likely cause is that no vehicle with id {vehicle_id} exists in the database."
            self.send_error_msg(error_msg, client_port)
            return
        
        msg["status"] = "success"
        msg["vehicle"] = car.to_json()
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return

    def add_engineer(self, job_json, client_port):
        msg = {
            'status': None
        }
        
        # Attempt to add an engineer to the database
        error_text = "Client engineer insert job has no entry for \"{}\""
        try:
            engin_name = job_json["name"]
        except:
            self.send_error_msg(error_text.format("name"), client_port)
            return
        
        try:
            birth_year = job_json["birth_year"]
        except:
            self.send_error_msg(error_text.format("birth_year"), client_port)
            return

        try:
            birth_month = job_json["birth_month"]
        except:
            self.send_error_msg(error_text.format("birth_month"), client_port)
            return

        try:
            birth_date = job_json["birth_date"]
        except:
            self.send_error_msg(error_text.format("birth_date"), client_port)
            return
        
        full_birth_date = date(birth_year, birth_month, birth_date)
        
        new_engin = self.call_with_lock(self.engin_utils.add_engineer_db, engin_name, full_birth_date)

        if new_engin is None:
            text = f"Engineer named {engin_name} already exists in the database.\n" + \
                   f"Aborted adding duplicate engineer {engin_name} to the database."
            self.send_error_msg(text, client_port)
            return

        new_port = self.get_unused_port()
        text = f"Successfully added new engineer {engin_name} to the database!"
        logging.info(text)
        msg["status"] = "success"
        msg["port"] = new_port
        new_engin_json = new_engin.to_json()
        success = self.try_send_message("localhost", client_port, {**msg, **new_engin_json})
        if not success:
            return

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
            self.send_error_msg(text, client_port)
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
                self.send_error_msg(text, client_port)
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
                    self.call_with_lock(self.car_utils.update_vehicle_db, car.id, engineers=new_engins_list)
                    assignment_msg = f"Successfully assigned {engin_name} to vehicle {car_model} manufactured on {car.manufacture_date}"
                    logging.info(assignment_msg)
                assigned.append(car_model)
            
            msg["status"] = "success"
            msg["assigned"] = assigned
            msg["unassigned"] = unassigned
            logging.info(f"Finished assigning vehicles to the new engineer {engin_name}")
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return

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
            self.send_error_msg(error_msg, client_port)
            return
        engin = self.engin_utils.read_engineer_by_name(name)
        if engin is None:
            error_msg = f"Engineer {name} doesn't exist in the database. Aborted deleting non-existant engineer."
            self.send_error_msg(error_msg, client_port)
            return
        self.call_with_lock(self.engin_utils.delete_engineer_by_name, name)
        logging.info(f"Successfully deleted engineer {name} from the database.")
        msg["status"] = "success"
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return
        return


    def query_engineer(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            name = job_json["name"]
        except:
            error_msg = "Client engineer read job has no entry for \"name\""
            self.send_error_msg(error_msg, client_port)
            return
        
        if name == "":
            try:
                id = job_json["id"]
            except:
                error_msg = "Client left engineer name blank, but did not provide an entry for \"id\""
                self.send_error_msg(error_msg, client_port)
                return
            logging.info(f"Attempting to read engineer with id {id} from the database.")
            engin = self.engin_utils.read_engineer_by_id(id)
            if engin is None:
                error_msg = f"No engineer with id {id} exists in the database"
                self.send_error_msg(error_msg, client_port)
                return
            msg["status"] = "success"
            msg["engineers"] = [engin.to_json()]
            logging.info(f"Successfully read engineer with id {id}:" + str(engin))
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return
        elif name == "all":
            logging.info("Attempting to read all engineers.")
            engins = self.engin_utils.read_all_engineers()
            msg["engineers"] = [eng.to_json() for eng in engins]
        
        else:
            logging.info(f"Attempting to read engineer named {name}")
            engin = self.engin_utils.read_engineer_by_name(name)
            if engin is None:
                error_msg = f"No engineer named {name} exists in the database"
                self.send_error_msg(error_msg, client_port)
                return
            msg["engineers"] = [engin.to_json()]
        
        logging.info(f"Engineer(s) successfully read from the database.")
        msg["status"] = "success"
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return

    def update_engineer(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            engin_id = job_json["id"]
        except:
            error_msg = "Client update engineer job did not include an entry for \"id\""
            self.send_error_msg(error_msg, client_port)
            return

        logging.info(f"Attempting to update engineer with ID {engin_id}")

        curr_engin = self.engin_utils.read_engineer_by_id(engin_id)

        if curr_engin is None:
            error_msg = f"No engineer with ID {engin_id} exists in the database. Cannot update information for an engineer that doesn't exist."
            self.send_error_msg(error_msg)
            return

        name = birth_year = birth_month = birth_date = vehicle_models = None

        missing_entry_msg = "Client did not provide a field \"{entry_name}\" for engineer update job. Skipping update for \"{entry_name}\""

        try:
            name = job_json["name"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "name"))

        try:
            birth_year = job_json["birth_year"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "birth_year"))
            birth_year = curr_engin.birthday.year
        
        try:
            birth_month = job_json["birth_month"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "birth_month"))
            birth_month = curr_engin.birthday.month
        
        try:
            birth_date = job_json["birth_date"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "birth_date"))
            birth_date = curr_engin.birthday.day

        vehicles_assigned = []
        vehicles_unassigned = []
        try:
            vehicle_models = job_json["vehicles"]
            logging.info(f"Attempting to update vehicle assignments for engineer with ID {engin_id}")
            # Remove engineer from models not in the vehicle_models list
            # Add engineer to models in the vehicle_models list
            all_cars = self.car_utils.read_vehicles_all()
            for car in all_cars:
                if car.model in vehicle_models:
                    new_engins = car.engineers + [curr_engin]
                    self.call_with_lock(self.car_utils.update_vehicle_db, car.id, engineers=new_engins)
                    vehicles_assigned.append(car.model)
                    logging.info(f"Successfully assigned engineer with ID {engin_id} to vehicle model {car.model}")
                else:
                    try:
                        car.engineers.remove(curr_engin)
                        self.call_with_lock(self.car_utils.update_vehicle_db, car.id, engineers=car.engineers)
                        vehicles_unassigned.append(car.model)
                        logging.info(f"Successfully un-assigned engineer with ID {engin_id} from vehicle model {car.model}")
                    except:
                        logging.info(f"Engineer with ID {engin_id} was already not assigned to car model {car.model}")

        except:
            logging.info(missing_entry_msg.format(entry_name = "vehicles"))

        
        
        full_birth_date = date(birth_year, birth_month, birth_date)

        engin_updated = self.call_with_lock(self.engin_utils.update_engineer_by_id, engin_id, name, full_birth_date)

        if engin_updated is None:
            error_msg = f"There was an issue updating engineer with ID {engin_id}. Most likely cause is a non-existant engineer with ID {engin_id}"
            self.send_error_msg(error_msg, client_port)
            return
        
        if vehicles_assigned:
            msg["assigned_models"] = vehicles_assigned

        if vehicles_unassigned:
            msg["unassigned_models"] = vehicles_unassigned

        msg["status"] = "success"
        msg["engineer"] = engin_updated.to_json()
        success_msg = f"Successfully updated info for engineer with ID {engin_id}.\nEngineer new info:\n{engin_updated.to_json()}"
        logging.info(success_msg)
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return
        

    def add_laptop(self, job_json, client_port):
        msg = {
            "status": None
        }

        # Attempt to add a laptop to the database
        error_text = "Client laptop insert job has no entry for \"{}\""
        try:
            model = job_json["model"]
        except:
            self.send_error_msg(error_text.format("model"), client_port)
            return
        
        try:
            loan_year = job_json["loan_year"]
        except:
            self.send_error_msg(error_text.format("loan_year"), client_port)
            return

        try:
            loan_month = job_json["loan_month"]
        except:
            self.send_error_msg(error_text.format("loan_month"), client_port)
            return
        
        try:
            loan_date = job_json["loan_date"]
        except:
            self.send_error_msg(error_text.format("loan_date"), client_port)
            return
        
        try:
            engin_name = job_json["engineer"]
        except:
            self.send_error_msg(error_text.format("engineer"), client_port)
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
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return

            client_response = self.get_client_response(new_sock)
            try:
                proceed = client_response["response"]
            except:
                error_msg = "Client response has no entry \"response\" to let the server know whether to add the laptop or not."
                self.send_error_msg(error_msg, client_port)
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
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return

            client_response = self.get_client_response(new_sock)

            try:
                replace = client_response["response"]
            except:
                error_msg = "Client response has no entry \"response\" to let the server know whether to replace the engineer's currently loaned laptop."
                self.send_error_msg(error_msg, client_port)
                new_sock.close()
                self.used_ports.remove(new_port)
            
            if replace == 'n':
                logging.info("Client chose not to replace the engineer's current laptop.\nAborted adding new laptop")
                new_sock.close()
                self.used_ports.remove(new_port)
            
        # Finally, add the laptop and send success/error back to client
        new_laptop = self.call_with_lock(self.laptop_utils.add_laptop_db, model, date(loan_year, loan_month, loan_date), engin_name)
        if new_laptop is None:
            error_msg = "Laptop already exists in the database. Aborted adding the duplicate laptop."
            self.send_error_msg(error_msg, client_port)
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
        success = self.try_send_message("localhost", client_port, {**msg, **new_laptop_json})
        if not success:
            return
        
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
            self.send_error_msg(error_msg, client_port)
            return
        
        if engin_name == "":
            try:
                laptop_id = job_json["id"]
            except:
                error_msg = "Client unowned laptop delete job had no entry for \"id\""
                self.send_error_msg(error_msg, client_port)
                return
            
            try:
                logging.info(f"Attempting to delete laptop with id {laptop_id}")
                self.call_with_lock(self.laptop_utils.delete_laptop_by_id, laptop_id)
                success_msg = f"Successfully deleted laptop with id {laptop_id}"
                logging.info(success_msg)
                msg["status"] = "success"
                success = self.try_send_message("localhost", client_port, msg)
                if not success:
                    return
                return
            except UnmappedInstanceError:
                error_msg = f"Laptop with id {laptop_id} has already been deleted from the database."
                self.send_error_msg(error_msg, client_port)
                return
        else:
            logging.info(f"Attempting to delete laptop loaned by {engin_name}")
            self.call_with_lock(self.laptop_utils.delete_laptop_by_owner, engin_name)
            logging.info(f"Successfully deleted laptop loaned by {engin_name}")
            msg["status"] = "success"
            success =self.try_send_message("localhost", client_port, msg)
            if not success:
                return

    def query_laptop(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            model = job_json["model"]
        except:
            error_msg = "Client laptop read job had no entry for \"model\""
            self.send_error_msg(error_msg, client_port)
            return
        
        if model == "":
            try:
                engin_name = job_json["engineer"]
            except:
                error_msg = "Client laptop read job left model blank, but did not provide an entry for \"engineer\""
                self.send_error_msg(error_msg, client_port)
                return
            
            logging.info(f"Attempting to read laptop loaned by engineer {engin_name}")
            laptop = self.laptop_utils.read_laptop_by_owner(engin_name)
            if laptop is None:
                error_msg = f"No laptop is loaned by engineer {engin_name}"
                self.send_error_msg(error_msg, client_port)
                return
            msg["status"] = "success"
            msg["laptops"] = [laptop.to_json()]
            logging.info(f"Successfully read laptop loaned by engineer {engin_name}")
            success = self.try_send_message("localhost", client_port, msg)
            if not success:
                return
            return

        elif model == "all":
            logging.info("Attempting to read all laptops")
            laptops = self.laptop_utils.read_all_laptops()
            if not laptops:
                error_msg = "No laptops exist in the database"
                self.send_error_msg(error_msg, client_port)
                return
            msg["laptops"] = [lap.to_json() for lap in laptops]
            logging.info("Successfully read all laptops")
        
        else:
            logging.info(f"Attempting to read laptops with model {model}")
            laptops = self.laptop_utils.read_laptops_by_model(model)
            if not laptops:
                error_msg = f"No laptops of model {model} exist in the database"
                self.send_error_msg(error_msg, client_port)
                return
            msg["laptops"] = [lap.to_json() for lap in laptops]
            logging.info(f"Successfully read laptops with model {model}")
        
        msg["status"] = "success"
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return
        
    def update_laptop(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            laptop_id = job_json["id"]
        except:
            error_msg = "Client update laptop job has no entry for \"id\""
            self.send_error_msg(error_msg, client_port)
            return
        
        logging.info(f"Attempting to update laptop ID {laptop_id} in the database.")

        curr_laptop = self.laptop_utils.read_laptop_by_id(laptop_id)

        if curr_laptop is None:
            error_msg = f"No laptop exists with ID {laptop_id}. Cannot update a laptop that doesn't exist."
            self.send_error_msg(error_msg, client_port)
            return

        model = loan_year = loan_month = loan_date = engineer_name = None
        
        missing_entry_msg = "Client update laptop job gave no entry for \"{entry_name}\". Skipping update for \"{entry_name}\""
        try:
            model = job_json["model"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "model"))
        
        try:
            loan_year = job_json["loan_year"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "loan_year"))
            loan_year = curr_laptop.date_loaned.year
        
        try:
            loan_month = job_json["loan_month"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "loan_moth"))
            loan_month = curr_laptop.date_loaned.month

        try:
            loan_date = job_json["loan_date"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "loan_date"))
            loan_date = curr_laptop.date_loaned.day

        try:
            engineer_name = job_json["engineer"]
        except:
            logging.info(missing_entry_msg.format(entry_name = "engineer"))
        
        full_loan_date = date(loan_year, loan_month, loan_date)

        updated_laptop = self.call_with_lock(self.laptop_utils.update_laptop_by_id, laptop_id, model, full_loan_date, engineer_name)

        if updated_laptop is None:
            error_msg = f"There was a problem updating laptop ID {laptop_id}.\nMost likely cause is a non-existant laptop with ID {laptop_id}"
            self.send_error_msg(error_msg, client_port)
            return
        
        msg["status"] = "success"
        msg["laptop"] = updated_laptop.to_json()
        success_msg = f"Successfully updated info for laptop ID {laptop_id}\nNew laptop info:{updated_laptop.to_json()}"
        logging.info(success_msg)
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return

    def add_contact_details(self, job_json, client_port):
        msg = {
            "status": None
        }

        error_msg = "Client contact details insert job has no entry for \"{}\""
        try:
            engin_name = job_json["engineer"]
        except:
            self.send_error_msg(error_msg.format("engineer"), client_port)
            return
        
        try:
            phone_number = job_json["phone_number"]
        except:
            self.send_error_msg(error_msg.format("phone_number"), client_port)
            return

        try:
            address = job_json["address"]
        except:
            self.send_error_msg(error_msg.format("address"), client_port)
            return
        
        # Attempt to add the new contact details, report error to client if duplicate or engineer doesn't exist
        engin = self.engin_utils.read_engineer_by_name(engin_name)
        if engin is None:
            error_msg = f"Engineer {engin_name} does not exist in the database. Contact details cannot be added for a non-existant engineer."
            self.send_error_msg(error_msg, client_port)
            return
        
        new_contact = self.call_with_lock(self.contact_utils.add_contact_details_db, phone_number, address, engin_name)
        if new_contact is None:
            error_msg = f"Detected duplicate contact details. Aborted adding duplicate."
            self.send_error_msg(error_msg, client_port)
            return
        
        success_msg = f"Successfully added contact details for engineer {engin_name}"
        new_contact_json = new_contact.to_json()
        logging.info(success_msg)
        msg["status"] = "success"
        success = self.try_send_message("localhost", client_port, {**msg, **new_contact_json})
        if not success:
            return
        return
     

    def delete_contact_details(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            engin_name = job_json["engineer"]
        except:
            error_msg = "Client contact details delete job had no entry for \"engineer\""
            self.send_error_msg(error_msg, client_port)
            return
        
        if engin_name == "":
            try:
                contact_id = job_json["id"]
            except:
                error_msg = f"Client response ommitted engineer name but did not have an entry for contact details \"id\""
                self.send_error_msg(error_msg, client_port)
                return
            
            try:
                logging.info(f"Attempting to delete contact details with ID {contact_id}")
                self.call_with_lock(self.contact_utils.delete_contact_details_by_id, contact_id)
                success_msg = f"Successfully deleted contact details with ID {contact_id}"
                msg["status"] = "success"
                success = self.try_send_message("localhost", client_port, msg)
                if not success:
                    return
                return
            except UnmappedInstanceError:
                error_msg = f"Contact details with ID {contact_id} has already been deleted from the database."
                self.send_error_msg(error_msg, client_port)
                return
        else:
            engin = self.engin_utils.read_engineer_by_name(engin_name)
            if engin is None:
                error_msg = f"Engineer {engin_name} does not exist in the database.\nAborted deleting contact details for non-existant engineer {engin_name}"
                self.send_error_msg(error_msg, client_port)
                return
            logging.info(f"Attempting to delete contact details for engineer {engin_name}")

            try:
                self.call_with_lock(self.contact_utils.delete_contact_details_by_engin_id, engin.id)
                logging.info(f"Successfully deleted all contact details for engineer {engin_name}")
                msg["status"] = "success"
                success = self.try_send_message("localhost", client_port, msg)
                if not success:
                    return
                return
            except UnmappedInstanceError:
                error_msg = f"Engineer {engin_name} has no contact details to delete. Aborted deleting non-existant contact details."
                self.send_error_msg(error_msg, client_port)
                return


    def query_contact_details(self, job_json, client_port):
        msg = {
            "status": None
        }

        try:
            engin_name = job_json["engineer"]
        except:
            error_msg = "Client contact details read job had no entry \"engineer\" for engineer name"
            self.send_error_msg(error_msg, client_port)
            return
        
        if engin_name == "":
            try:
                id = job_json["id"]
            except:
                error_msg = "Client contact details read job left engineer name blank, but did not provide an entry \"id\" for contact details id."
                self.send_error_msg(error_msg, client_port)
                return
            logging.info(f"Attempting to read contact details with id {id}")
            contact = self.contact_utils.read_contact_details_by_id(id)
            if contact is None:
                error_msg = f"No contact details with id {id} exists in the database."
                self.send_error_msg(error_msg, client_port)
                return
            logging.info(f"Successfully read contact details with id {id}")
            msg["contact_details"] = [contact.to_json()]
        
        elif engin_name == "all":
            logging.info("Attempting to read all contact details.")
            contacts = self.contact_utils.read_all_contact_details()
            if not contacts:
                error_msg = "No contact details exist in the database."
                self.send_error_msg(error_msg, client_port)
                return
            logging.info("Successfully read all contact details.")
            msg["contact_details"] = [contact.to_json() for contact in contacts]

        else:
            logging.info(f"Attempting to read contact details for engineer {engin_name}")
            engin = self.engin_utils.read_engineer_by_name(engin_name)
            if engin is None:
                error_msg = f"No engineer named {engin_name} exists in the database. Cannot read contact details for non-existant engineer."
                self.send_error_msg(error_msg, client_port)
                return
            contacts = self.contact_utils.read_contact_details_by_engin_id(engin.id)
            if not contacts:
                error_msg = f"No contact details exist for engineer {engin_name}"
                self.send_error_msg(error_msg, client_port)
                return
            logging.info(f"Successfully read contact details for engineer {engin_name}")
            msg["contact_details"] = [contact.to_json() for contact in contacts]
        
        msg["status"] = "success"
        success = self.try_send_message("localhost", client_port, msg)
        if not success:
            return

@click.command()
@click.argument("port", nargs=1, type=int)
@click.option("-s", "--single-thread", is_flag=True)
def main(port, single_thread):
    Server(port, single_thread)

if __name__ == "__main__":
    main()