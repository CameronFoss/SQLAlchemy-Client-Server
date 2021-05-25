from json.decoder import JSONDecodeError
import slash
import socket
from training.sock_utils import send_message, get_data_from_connection, decode_message_chunks
from training.tests.server_tests_base import ServerTestsBase

engineer_tuple = ("name", "birth_year", "birth_month", "birth_date")
valid_engineer_adds = [
    ("Steven Universe", 2010, 10, 1), 
    ("Autumn Tedrow", 2021, 12, 31), # latest accepted birth date
    ("Greg DeMayo", 1920, 1, 1) # earliest accepted birth date
]
invalid_engineer_adds = [
    ("Cameron Foss", 1998, 12, 1), # duplicate engineer
    ("Bad Year", 2022, 1, 1), # year out of range
    ("Bad Month", 2021, 13, 1), # month out of range
    ("Bad Date", 2021, 1, 32), # date out of range
    ("Impossible Date", 2021, 2, 31), # full date impossible (February 31st)
    ("", 2021, 5, 25) # empty name
]
vehicle_models = [
    ["Fusion"],
    ["Fusion", "Explorer"],
    ["Bronco", "Explorer"],
    ["Bronco", "Mustang Shelby GT500"],
    ["Fancy New Model"],
    ["Bronco", "Fancy New Model", "Explorer", "Fusion", "This doesn't exist"],
    None
]

class ServerEngineerTests(ServerTestsBase):
    def __init__(self, test_method_name, fixture_store, fixture_namespace, variation):
        super().__init__(test_method_name, fixture_store, fixture_namespace, variation)
        self.vehicles = []

    def __del__(self):
        self.listen_sock.close()
    
    @slash.parametrize("models", vehicle_models)
    def before(self, models):
        self.vehicles = models
        print("Resetting database before test")
        self.request_db_reset()
        print("Finished resetting database in \"before\" method.")

    def after(self):
        pass

    def add_engineer(self, name, birth_year, birth_month, birth_date):
        add_msg = {
            "data_type": "engineer",
            "action": "add",
            "port": self.my_port,
            "name": name,
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_date": birth_date
        }
        print(f"Asking server to add engineer: {add_msg}")
        send_message("localhost", self.server_port, add_msg)

    #@slash.skipped
    @slash.parametrize(engineer_tuple, invalid_engineer_adds)
    def test_add_invalid_engineer(self, name, birth_year, birth_month, birth_date):
        curr_test_input = "Current test input:\n" + \
                          f"Name: {name}\n" + \
                          f"Birth Year: {birth_year}\n" + \
                          f"Birth Month: {birth_month}\n" + \
                          f"Birth Date: {birth_date}\n" + \
                          f"Vehicles: {self.vehicles}\n"
        slash.logger.error(curr_test_input)
        self.add_engineer(name, birth_year, birth_month, birth_date)

        server_response = self.get_server_response()
        assert server_response

        status = self.check_server_status(server_response)
        assert not status # Expect to error out for all invalid cases

    #@slash.skipped
    @slash.parametrize(engineer_tuple, valid_engineer_adds)
    def test_add_valid_engineer(self, name, birth_year, birth_month, birth_date):
        curr_test_input = "Current test input:\n" + \
                          f"Name: {name}\n" + \
                          f"Birth Year: {birth_year}\n" + \
                          f"Birth Month: {birth_month}\n" + \
                          f"Birth Date: {birth_date}\n" + \
                          f"Vehicles: {self.vehicles}\n"
        slash.logger.error(curr_test_input)

        self.add_engineer(name, birth_year, birth_month, birth_date)

        server_response = self.get_server_response()
        assert server_response

        status = self.check_server_status(server_response)
        assert status

        missing_entry_msg = "Server response marked as success, but is missing an entry for engineer \"{}\""
        try:
            new_name = server_response["name"]
        except:
            slash.logger.error(missing_entry_msg.format("name"))
            assert False
        assert new_name == name

        try:
            new_year = server_response["birth_year"]
        except:
            slash.logger.error(missing_entry_msg.format("birth_year"))
            assert False
        assert new_year == birth_year

        try:
            new_month = server_response["birth_month"]
        except:
            slash.logger.error(missing_entry_msg.format("birth_month"))
            assert False
        assert new_month == birth_month

        try:
            new_date = server_response["birth_date"]
        except:
            slash.logger.error(missing_entry_msg.format("birth_date"))
            assert False
        assert new_date == birth_date

        try:
            new_server_port = server_response["port"]
        except:
            slash.logger.error(missing_entry_msg.format("port"))
            assert False

        assign_vehicles_msg = {
            "response": "y",
            "vehicles": self.vehicles
        }

        if self.vehicles is None:
            assign_vehicles_msg["response"] = "n"
        
        refused = True
        timeout_counter = 0
        timeout_max = 20
        while refused:
            if timeout_counter > timeout_max:
                slash.logger.error(f"Server timed out too many times while trying to send vehicle assignment message to port {new_server_port}")
            try:
                send_message("localhost", new_server_port, assign_vehicles_msg)
                refused = False
            except:
                timeout_counter += 1
                continue

        print(f"Asking server to assign vehicles: {assign_vehicles_msg}")
        
        if self.vehicles is not None:
            vehicle_assign_response = self.get_server_response()
            assert vehicle_assign_response
    
            vehicle_assign_status = self.check_server_status(vehicle_assign_response)
            assert vehicle_assign_status
        
            try:
                assigned = vehicle_assign_response["assigned"]
            except:
                slash.logger.error("Server assign vehicle response did not include an entry for \"assigned\" vehicles")
                assert False

            try:
                unassigned = vehicle_assign_response["unassigned"]
            except:
                slash.logger.error("Server assign vehicle response did not include an entry for \"unassigned\" vehicles")
                assert False

            for model in assigned:
                assert model in self.default_vehicle_models

            for model in unassigned:
                assert model not in self.default_vehicle_models