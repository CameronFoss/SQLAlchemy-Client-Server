from json.decoder import JSONDecodeError
from logging import critical
import slash
import socket
import multiprocessing
from training.server.__main__ import Server
from training.sock_utils import send_message, get_data_from_connection, decode_message_chunks

vehicle_tuple = ("model", "quantity", "price", "manufacture_year", "manufacture_month", "manufacture_date")
valid_vehicle_adds = [
    ("Civic", 3, 23000, 2017, 4, 30),
    ("Fusion", 2, 23000, 2019, 5, 5), # expect quantity to increase
    ("Max Date", 1, 1000, 2021, 12, 31), # latest accepted manufacture date
    ("Min Date", 1, 1000, 1920, 1, 1), # earliest accepted manufacture date
    ("Min Quantity", 0, 1000, 2020, 4, 4), # lowest quantity accepted
    ("Min Price", 0, 1, 2020, 5, 5) # lowest price accepted
]
bad_vehicles = [
    ("Rando", -1, 10000, 2021, 5, 20), # negative quantity
    ("Cruze", 1, -10, 2021, 4, 23), # negative price
    ("Bad Year", 1, 10000, 2022, 1, 1), # year out of range
    ("Bad Month", 1, 10000, 2020, 13, 1), # month out of range
    ("Bad Day", 1, 10000, 2020, 1, 32), # day out of range
    ("", 1, 1000, 2021, 5, 21) # empty model given
]
engineer_names = [
    ["Cameron Foss", "Prerna Sancheti"], # normal case, engins both exist
    ["Steven Universe"], # 1 non-present engineer
    ["Garnet", "Pearl"], # multiple non-present engineers
    ["Jaivenkatram Harirao", "Garnet", "Pearl", "Cameron Foss", "Autumn Tedrow", "Prerna Sancheti"], # mix of present and non-present engineers
    [], # unassign all engineers
    None # no engineer assignment
]


# TODO: test cases for bad client messages (e.g. wrong data_type/action, missing entries, etc)

class ServerVehicleTests(slash.Test):
    listen_port = 6001

    def __init__(self, test_method_name, fixture_store, fixture_namespace, variation):
        super().__init__(test_method_name, fixture_store, fixture_namespace, variation)
        self.engineers = []
        self.default_engineer_names = {"Prerna Sancheti", "Cameron Foss", "Jaivenkatram Harirao"}
        self.default_vehicle_models = {"Fusion", "Explorer", "Bronco", "Mustang Shelby GT500"}
        self.server_port = 6000
        self.my_port = ServerVehicleTests.listen_port
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.bind(("localhost", ServerVehicleTests.listen_port))
        print("Bound socket")
        self.listen_sock.listen()
        self.listen_sock.settimeout(1)
        ServerVehicleTests.listen_port += 1
        self.request_db_reset()
        print("Database reset")

    def __del__(self):
        self.listen_sock.close()

    @slash.parametrize("engineers", engineer_names)
    def before(self, engineers):
        self.engineers = engineers

    def after(self):
        print("Trying to reset the database after test")
        self.request_db_reset()
        print("Database reset in \"after\" method")

    def request_db_reset(self):
        msg = {
            "action": "reset"
        }
        send_message("localhost", self.server_port, msg)

    def get_server_response(self):
        server_response = None
        timeout_counter = 0
        timeout_max = 100
        while server_response is None:
            if timeout_counter >= timeout_max:
                slash.logger.error("Timed out too many times while trying to accept a message from the server")
                slash.logger.error("Server is likely not running on port 6000")
                return False

            message_chunks = get_data_from_connection(self.listen_sock)

            if not message_chunks:
                timeout_counter += 1
                continue
                
            try:
                message_dict = decode_message_chunks(message_chunks)
                server_response = message_dict
                print(f"Server Response: {server_response}")
                break
            except JSONDecodeError:
                continue
        return server_response

    def check_server_status(self, server_response):
        try:
            status = server_response["status"]
        except:
            return False
        
        if status == "error":
            slash.logger.error(server_response["text"])
            return False
        
        return status

    # Sends the initial add vehicle message. Caller must grab server response since different tests expect different statuses
    def add_new_vehicle(self, model, quantity, price, manufacture_year, manufacture_month, manufacture_date):
        add_msg = {
            "data_type": "vehicle",
            "action": "add",
            "port": self.my_port,
            "model": model,
            "quantity": quantity,
            "price": price,
            "manufacture_year": manufacture_year,
            "manufacture_month": manufacture_month,
            "manufacture_date": manufacture_date
        }
        print(f"Asking server to add vehicle: {add_msg}")
        send_message("localhost", self.server_port, add_msg)

    @slash.parametrize(vehicle_tuple, valid_vehicle_adds)
    def test_add_valid_vehicle(self, model, quantity, price, manufacture_year, manufacture_month, manufacture_date):
        curr_test_input = "Input for current test:\n" + \
                          f"Model: {model}\n" + \
                          f"Quantity: {quantity}\n" + \
                          f"Price: {price}\n" + \
                          f"Manufacture Year: {manufacture_year}\n" + \
                          f"Manufacture Month: {manufacture_month}\n" + \
                          f"Manufacture Date: {manufacture_date}\n" + \
                          f"Engineers: {self.engineers}"
        slash.logger.error(curr_test_input)
        self.add_new_vehicle(model, quantity, price, manufacture_year, manufacture_month, manufacture_date)

        server_response = self.get_server_response()
        assert server_response

        status = self.check_server_status(server_response)

        assert status

        if model in self.default_vehicle_models:
            print("model is already in the database")
            assert status == "updated"
        
        else:
            assign_engins_msg = {
                "response": "y",
                "engineers": self.engineers
            }

            if self.engineers is None:
                assign_engins_msg["response"] = "n"

            try:
                new_server_port = server_response["port"]
            except:
                print("No port entry")
                slash.logger.error("Server vehicle add response did not inclue an entry \"port\" to let us know where to send assign engineer response")
                assert False

            missing_response_msg = "Server vehicle add response marked success but did not include an entry for \"{entry_name}\""
            try:
                server_model = server_response["model"]
                assert server_model == model
            except:
                slash.logger.error(missing_response_msg.format("model"))
                assert False

            try:
                server_quantity = server_response["quantity"]
                assert server_quantity == quantity
            except:
                slash.logger.error(missing_response_msg.format("quantity"))
                assert False

            try:
                server_price = server_response["price"]
                assert server_price == price
            except:
                slash.logger.error(missing_response_msg.format("price"))
                assert False

            try:
                server_manufacture_year = server_response["manufacture_year"]
                assert server_manufacture_year == manufacture_year
            except:
                slash.logger.error(missing_response_msg.format("manufacture_year"))
                assert False

            try:
                server_manufacture_month = server_response["manufacture_month"]
                assert server_manufacture_month == manufacture_month
            except:
                slash.logger.error(missing_response_msg.format("manufacture_month"))
                assert False

            try:
                server_manufacture_date = server_response["manufacture_date"]
                assert server_manufacture_date == manufacture_date
            except:
                slash.logger.error(missing_response_msg.format("manufacture_date"))
                assert False

            print("Sending engineer assignment message to server")
            send_message("localhost", new_server_port, assign_engins_msg)

            if self.engineers is not None:
                server_response = self.get_server_response()
                status = self.check_server_status(server_response)
                assert status
                try:
                    assigned = server_response["assigned"]
                except:
                    slash.logger.error("Server engineer assignment response did not include an entry \"assigned\" for successfully assigned engineers.")
                    assert False

                try:
                    unassigned = server_response["unassigned"]
                except:
                    slash.logger.error("Server engineer assignment response did not include an entry \"unassigned\" for unsuccessfully assigned engineers.")
                    assert False

                for name in assigned:
                    assert name in self.default_engineer_names

                for name in unassigned:
                    assert name not in self.default_engineer_names
        


        
