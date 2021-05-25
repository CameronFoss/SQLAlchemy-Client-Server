from json.decoder import JSONDecodeError
import slash
import socket
from training.sock_utils import send_message, get_data_from_connection, decode_message_chunks
from training.tests.server_tests_base import ServerTestsBase

engineer_tuple = ("name", "birth_year", "birth_month", "birth_date")
engineer_update_tuple = ("id",) + engineer_tuple
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
valid_engineer_deletes = ["Cameron Foss", "Prerna Sancheti", "Jaivenkatram Harirao"]
invalid_engineer_deletes = ["Steven Universe", "Autumn Tedrow", ""]
valid_engineer_updates = [
    (1, "Steven Universe", 2010, 1, 1), # update all
    (1, "Steven Universe", None, None, None), # only name
    (1, None, 2010, None, None), # only birth year
    (1, None, None, 1, None), # only birth month
    (1, None, None, None, 31), # only birth date
    (1, None, 2010, 1, 1) # full birthday
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

    def delete_engineer(self, name):
        delete_msg = {
            "data_type": "engineer",
            "action": "delete",
            "port": self.my_port,
            "name": name
        }
        print(f"Asking server to delete engineer named {name}")
        send_message("localhost", self.server_port, delete_msg)

    def update_engineer(self, id, name, birth_year, birth_month, birth_date):
        update_msg = {
            "data_type": "engineer",
            "action": "update",
            "port": self.my_port,
            "id": id
        }
        if name is not None:
            update_msg["name"] = name
        if birth_year is not None:
            update_msg["birth_year"] = birth_year
        if birth_month is not None:
            update_msg["birth_month"] = birth_month
        if birth_date is not None:
            update_msg["birth_date"] = birth_date
        if self.vehicles is not None:
            update_msg["vehicles"] = self.vehicles
        
        print(f"Asking server to update engineer: {update_msg}")
        send_message("localhost", self.server_port, update_msg)

    def read_vehicles_by_engineer(self, name):
        read_msg = {
            "data_type": "vehicle_engineers",
            "action": "read",
            "port": self.my_port,
            "engineer": name
        }
        print(f"Asking server to read vehicles assigned to engineer {name}: {read_msg}")
        send_message("localhost", self.server_port, read_msg)

    @slash.parametrize(engineer_update_tuple, valid_engineer_updates)
    def test_update_valid_engineer(self, id, name, birth_year, birth_month, birth_date):
        curr_test_input = "Current test input:\n" + \
                          f"ID: {id}\n" + \
                          f"Name: {name}\n" + \
                          f"Birth Year: {birth_year}\n" + \
                          f"Birth Month: {birth_month}\n" + \
                          f"Birth Date: {birth_date}\n" + \
                          f"Vehicles: {self.vehicles}\n"
        slash.logger.error(curr_test_input)
        # Need to read previously assigned vehicles before update for later comparison
        prev_vehicles = None
        if name is not None:
            self.read_vehicles_by_engineer(name)

            read_response = self.get_server_response()
            assert read_response

            read_status = self.check_server_status(read_response)

            try:
                if read_status:
                    prev_vehicles = read_response["vehicles"]
                    prev_vehicles = [car["name"] for car in prev_vehicles]
            except:
                slash.logger.error(f"Server read for vehicles assigned to engineer {name} marked success, but did not provide an entry for \"vehicles\"")
                assert False


        self.update_engineer(id, name, birth_year, birth_month, birth_date)

        server_response = self.get_server_response()
        assert server_response

        status = self.check_server_status(server_response)
        assert status

        try:
            updated_engin = server_response["engineer"]
            slash.logger.error(f"Got updated engineer response: {updated_engin}")
        except KeyError:
            slash.logger.error("Server marked update success, but did not include an entry for \"engineer\"")
            assert False
        
        missing_entry_msg = "Server updated engineer response did not include an entry for \"{}\""
        try:
            updated_name = updated_engin["name"]
            if name is not None:
                assert updated_name == name
        except KeyError:
            slash.logger.error(missing_entry_msg.format("name"))
            assert False
        
        try:
            updated_year = updated_engin["birth_year"]
            if birth_year is not None:
                assert birth_year == updated_year
        except KeyError:
            slash.logger.error(missing_entry_msg.format("birth_year"))
            assert False
        
        try:
            updated_month = updated_engin["birth_month"]
            if birth_month is not None:
                assert updated_month == birth_month
        except KeyError:
            slash.logger.error(missing_entry_msg.format("birth_month"))
            assert False
        
        try:
            updated_date = updated_engin["birth_date"]
            if birth_date is not None:
                assert updated_date == birth_date
        except KeyError:
            slash.logger.error(missing_entry_msg.format("birth_date"))
            assert False
        

        if self.vehicles is not None:
            entry_seen = False
            try:
                assigned_vehicles = server_response["assigned_models"]
                entry_seen = True
                for model in assigned_vehicles:
                    assert model in self.default_vehicle_models
                    assert model in self.engineers
            except KeyError:
                slash.logger.error(missing_entry_msg.format("assigned_models"))

            if prev_vehicles is not None:
                try:
                    unassigned_vehicles = server_response["unassigned_models"]
                    entry_seen = True
                    for model in unassigned_vehicles:
                        assert model in prev_vehicles
                except KeyError:
                    slash.logger.error(missing_entry_msg.format("unassigned_models"))
            
            assert entry_seen

    @slash.skipped
    @slash.parametrize("name", invalid_engineer_deletes)
    def test_delete_invalid_engineer(self, name):
        curr_test_input = "Current test input:\n" + \
                          f"Name: {name}\n"
        slash.logger.error(curr_test_input)
        self.delete_engineer(name)

        server_response = self.get_server_response()
        assert server_response

        status = self.check_server_status(server_response)
        assert not status # Expect to error out for invalid engineer deletions

    @slash.skipped
    @slash.parametrize("name", valid_engineer_deletes)
    def test_delete_valid_engineer(self, name):
        curr_test_input = "Current test input:\n" + \
                          f"Name: {name}\n"
        slash.logger.error(curr_test_input)
        self.delete_engineer(name)

        server_response = self.get_server_response()
        assert server_response

        status = self.check_server_status(server_response)
        assert status

        read_msg = {
            "data_type": "engineer",
            "action": "read",
            "port": self.my_port,
            "name": name
        }

        send_message("localhost", self.server_port, read_msg)

        read_response = self.get_server_response()
        assert read_response

        read_status = self.check_server_status(read_response)
        assert not read_status # Expect to error out when we read the engineer we just deleted


    @slash.skipped
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

    @slash.skipped
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