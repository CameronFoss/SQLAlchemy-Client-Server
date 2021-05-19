import slash
from training.server.__main__ import Server
from training.server.reset import reset_db

vehicle_tuple = ("model", "quantity", "price", "manufacture_year", "manufacture_month", "manufacture_date")
# TODO: think of more corner case vehicle additions, particularly those that should raise exceptions
non_default_vehicles = [
    ("Civic", "3", "23000", "2017", "4", "31")
]

class ServerVehicleTests(slash.Test):
    def before(self):
        reset_db()

    def after(self):
        reset_db()

    @slash.parametrize(vehicle_tuple, non_default_vehicles)
    def test_add_new_vehicle(self, model, quantity, price, manufacture_year, manufacture_month, manufacture_date):
        pass