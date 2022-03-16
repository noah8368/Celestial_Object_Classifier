"""Define rountines to enable data transfer between a PC and a Raspberry Pi.

Set up a TCP connection between a server and client.
"""

import os
import socket


_CONNECTION_BUFFER_SIZE = 4096
_SERVER_PORT = 5000


class ServerPortal:
    def __init__(self, save_dir=os.curdir):
        """Inits a server object bound to all available interfaces."""

        self.recv_data_count = 0
        self.save_dir = save_dir
        self.conn = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('', _SERVER_PORT))
        self.socket.listen()

    def recv(self):
        """Waits for a connection request, and saves a received image file."""

        self.conn, _ = self.socket.accept()
        img_f_name = str(self.recv_data_count) + ".jpeg"
        img_f_path = os.path.join(os.curdir, self.save_dir, img_f_name)
        print("CONNECTION ACCEPTED")
        img_f = open(img_f_path, "wb")
        # Accept,  write image data locally from the client with a buffer.
        while True:
            print("CHECKING CONNECTION")
            data = self.conn.recv(_CONNECTION_BUFFER_SIZE)
            print("Receiving data request...")
            if not data:
                print("DATA RECEPTION FINISHED")
                break
            print("WRITING DATA")
            img_f.write(data)
            print("FINISHED WRITING DATA")
        print("GOT OUT OF LOOP")
        img_f.close()
        print("FINISHED RECEVING DATA")
        self.recv_data_count += 1
        return True

    def send(self, f):
        """Sends file data to an accepted connection."""

        if not self.conn:
            raise ConnectionError("Request to send to non-existent client")

        data_f = open(f, "rb")
        self.conn.sendfile(data_f)
        self.conn.close()
        print("SENT DATA")


class ClientPortal:
    def __init__(self, save_dir=os.curdir):
        """Binds the server to all available interfaces."""

        self.save_dir = save_dir
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # TODO: Use a ping subprocess to get the IP address of Raspberry Pi.
        server_addr = "127.0.0.1"
        self.socket.connect((server_addr, _SERVER_PORT))

    def make_request(self, send_f, recv_f):
        """Sends an image to the server to be processed and saves response."""

        req_f = open(send_f, "rb")
        self.socket.sendfile(req_f)
        req_f.close()

        # Tell the server that it's done sending data, but can still receive.
        self.socket.shutdown(socket.SHUT_WR)

        print("SENT FILE")

        # Receive and save the server's response.
        resp_f = open(recv_f, "wb")
        with self.socket:
            # Accept,  write image data locally from the client with a buffer.
            while True:
                data = self.socket.recv(_CONNECTION_BUFFER_SIZE)
                print("Receiving data response..." + str(data))
                if not data:
                    print("DATA RECEPTION FINISHED")
                    break
                resp_f.write(data)
        resp_f.close()
        print("REQUEST SUCCESSFULLY COMPLETED")
