from json.decoder import JSONDecodeError
import slash
import socket
from training.sock_utils import send_message, get_data_from_connection, decode_message_chunks

class ServerTestsBase(slash.Test):
    listen_port = 6001

    def __init__(self, test_method_name, fixture_store, fixture_namespace, variation):
        super().__init__(test_method_name, fixture_store, fixture_namespace, variation)
        self.engineers = []
        self.default_engineer_names = {"Prerna Sancheti", "Cameron Foss", "Jaivenkatram Harirao"}
        self.default_vehicle_models = {"Fusion", "Explorer", "Bronco", "Mustang Shelby GT500"}
        self.server_port = 6000
        self.my_port = ServerTestsBase.listen_port
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.bind(("localhost", ServerTestsBase.listen_port))
        print("Bound socket")
        self.listen_sock.listen()
        self.listen_sock.settimeout(1)
        ServerTestsBase.listen_port += 1

    def __del__(self):
        self.listen_sock.close()

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