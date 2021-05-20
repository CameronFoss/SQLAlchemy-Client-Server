import slash
from training.server.__main__ import Server
from training.server.reset import reset_db

vehicle_tuple = ("model", "quantity", "price", "manufacture_year", "manufacture_month", "manufacture_date")
non_default_vehicles = [
    ("Civic", 3, 23000, 2017, 4, 31),
    ("Rando", -1, 10000, 2021, 5, 20), # negative quantity
    ("Cruze", 1, -10, 2021, 4, 23), # negative price
    ("Bad Year", 1, 10000, 2022, 1, 1), # year out of range
    ("Civic", 2, 24500, 2018, 7, 11), # duplicate model
]
engineer_names = [
    ["Cameron Foss", "Prerna Sancheti"], # normal case, engins both exist
    ["Steven Universe"], # 1 non-present engineer
    ["Garnet", "Pearl"], # multiple non-present engineers
    ["Jaivenkatram Harirao", "Garnet", "Pearl", "Cameron Foss", "Autumn Tedrow", "Prerna Sancheti"], # mix of present and non-present engineers
    [], # no engineer assignment
]

# TODO: test cases for bad client messages (e.g. wrong data_type/action, missing entries, etc)

class ServerVehicleTests(slash.Test):
    def __init__(self):
        self.engineers = []
        reset_db()

    @slash.parametrize("engineers", engineer_names)
    def before(self, new_engineers):
        self.engineers = new_engineers

    def after(self):
        reset_db()

    @slash.parametrize(vehicle_tuple, non_default_vehicles)
    def test_add_new_vehicle(self, model, quantity, price, manufacture_year, manufacture_month, manufacture_date):
        pass