import socket
import json

def send_message(host, port, msg_dict):
    """Connect to sock via host and port and sends a message to sock."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    msg_json = json.dumps(msg_dict)
    sock.sendall(msg_json.encode('utf-8'))
    # Close the socket so 'data' will be null in get_data_from_connection
    sock.close()


def decode_message_chunks(chunks):
    """Decode message chunks into a Python dictionary."""
    msg_bytes = b''.join(chunks)
    msg_str = msg_bytes.decode("utf-8")
    # Note: caller needs to catch errors thrown by json.loads
    return json.loads(msg_str)


def get_data_from_connection(sock):
    """Accept a client connection and get data until they close the socket."""
    try:
        clientsocket, address = sock.accept()
    except socket.timeout:
        return []
    print("Connection from", address[0])
    message_chunks = []
    while True:
        try:
            data = clientsocket.recv(4096)
        except socket.timeout:
            continue
        if not data:
            break
        message_chunks.append(data)
    clientsocket.close()
    return message_chunks
