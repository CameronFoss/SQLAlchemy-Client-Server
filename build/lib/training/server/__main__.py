import socket
import threading
import logging
import click
from time import sleep
from sys import stdin
from select import select
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
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

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
        pass

    def query_vehicle(self, job_json, client_port):
        pass

    def add_engineer(self, job_json, client_port):
        pass

    def delete_engineer(self, job_json, client_port):
        pass

    def query_engineer(self, job_json, client_port):
        pass

    def add_laptop(self, job_json, client_port):
        pass

    def delete_laptop(self, job_json, client_port):
        pass

    def query_laptop(self, job_json, client_port):
        pass

    def add_contact_details(self, job_json, client_port):
        pass

    def delete_contact_details(self, job_json, client_port):
        pass

    def query_contact_details(self, job_json, client_port):
        pass

@click.command()
@click.argument("port", nargs=1, type=int)
def main(port):
    Server(port)

if __name__ == "__main__":
    main()