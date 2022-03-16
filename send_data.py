"""Define rountines to enable data transfer between a PC and a Raspberry Pi.

Set up a TCP connection between a server and client.
"""

import os
import re
import socket
import subprocess


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

    def recv(self, save_f):
        """Waits for a connection request, and saves a received image file."""

        self.conn, _ = self.socket.accept()
        img_f = open(save_f, "wb")
        # Accept,  write image data locally from the client with a buffer.
        while True:
            data = self.conn.recv(_CONNECTION_BUFFER_SIZE)
            if not data:
                break
            img_f.write(data)
        img_f.close()
        self.recv_data_count += 1
        return True

    def send(self, f):
        """Sends file data to an accepted connection."""

        if not self.conn:
            raise ConnectionError("Request to send to non-existent client")

        data_f = open(f, "rb")
        self.conn.sendfile(data_f)
        self.conn.close()


class ClientPortal:
    def __init__(self, save_dir=os.curdir,
                 server_hostname="raspberrypi.lan"):
        """Binds the server to all available interfaces."""

        # Create a socket.
        self.save_dir = save_dir
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Use the ping subprocess to get the IP address of Raspberry Pi.
            response = subprocess.check_output(
                ["ping", "-c", '3', server_hostname],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
        except subprocess.CalledProcessError:
            raise ConnectionAbortedError("Unable to establish connection")

        # Parse the repsonse from ping to collect the IPv4 address.
        if response == '':
            raise ConnectionAbortedError("Unable to establish connection")
        server_addr = re.search(
            '(?:[0-9]{1,3}\.){3}[0-9]{1,3}|$',
            response
        ).group()
        if server_addr == '':
            raise ConnectionAbortedError("Unable to establish connection")

        # Connect the socket to the client using the collect IP address.
        self.socket.connect((server_addr, _SERVER_PORT))

    def make_request(self, send_f, recv_f):
        """Sends an image to the server to be processed and saves response."""

        req_f = open(send_f, "rb")
        self.socket.sendfile(req_f)
        req_f.close()

        # Tell the server that it's done sending data, but can still receive.
        self.socket.shutdown(socket.SHUT_WR)

        # Receive and save the server's response.
        resp_f = open(recv_f, "wb")
        with self.socket:
            # Accept,  write image data locally from the client with a buffer.
            while True:
                data = self.socket.recv(_CONNECTION_BUFFER_SIZE)
                if not data:
                    break
                resp_f.write(data)
        resp_f.close()
