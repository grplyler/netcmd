__author__ = 'ryanplyler'
import threading
import actions
import yaml
import socket
import importlib
import sys
import binascii
from time import sleep

# Global settings
# todo: find a way to store a literal '\r\n' in yaml
#TERM = '\r\n'

# Debugging test function


class Receiver(threading.Thread):
    def __init__(self, sock, addr, config):
        self.sock = sock
        self.addr = addr
        self.config = config
        self.stopped = False
        # Need to convert string '\r\n' to literal
        #self.TERM = self.config['global']['message_terminator']
        threading.Thread.__init__(self)

    def run(self):
        # Send connection acknowledgement
        self.sendline('You have connected')

        # Check is authentication is required
        if config['global']['require_auth']:
            # Authenticate the user
            # todo: add a timeout to authentication
            print("Authenticating client", self.addr)
            self.sock.send(b'Please enter access password: ')
            passwd = self.sock.recv(64)
            passwd = passwd[:-2].decode('UTF-8')
            if passwd == config['global']['auth_password']:
                print("Access granted to", self.addr)
                self.sendline("Access Granted.")
                self.sendline("Here is a list of available commands:")

                # Send available commands to user
                self.send_commands()
            else:
                print("Access denied for", self.addr)
                self.sendline("Wrong password!!! Access denied.")
                self.sendline("Disconnecting...")
                self.sock.shutdown(0)
                self.sock.close()
                self.stopped = True


        # Wait for incoming message (Loop while client is connected)
        # todo: Perform check from control C sent by the client and disconnect
        while not self.stopped:
            data = self.sock.recv(1024)
            data = data[:-2].decode('UTF-8')
            print("Received", data, "from", addr)


            # Determine what the message means
            if data in self.config['messages']:
                self.process_msg(data)

            elif data == "quit":
                # Shutdown the Connection and Thread
                print("Disconnecting", addr)
                self.sendline('Disconnecting...')
                self.sock.shutdown(0)
                self.sock.close()
                self.stopped = True
                break

            # Unknown message received
            else:
                print("Unknown message:", data)
                self.sendline('Message not understood, see server.yaml')

    def send_commands(self):
        for i in self.config['messages']:
            self.sendline(i)

    def process_msg(self, data):
        action = self.get_action(self.config['messages'][data]['action'])

        # Execute the action function
        output, response, error = action(self.config)

        # Check for errors
        if error:
            # Return error to client
            self.sendline(self.config['messages'][data]['error'])
            # Print error in server output
            print(self.config['messages'][data]['error'])
        else:
            # Display server output
            print(output)

            # Send response to client
            self.sendline(response)

    def sendline(self, msg):
        self.sock.send(bytes(msg + TERM, 'utf-8'))

    def get_action(self, action_string):
        mod_name, func_name = action_string.rsplit('.')
        mod = importlib.import_module(mod_name)
        func = getattr(mod, func_name)
        return func


if __name__ == "__main__":
    with open('server.yaml') as configfile:
        config = yaml.load(configfile.read())

    # Get Settings
    IP = config['global']['bound_ip']
    PORT = config['global']['server_port']
    stopped = False
    TERM = config['global']['message_terminator']

    # Create the sockets
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((IP, PORT))
    server.listen(10)
    print("netcmd server started on port", PORT)



    # Create Thread Pool
    thread_pool = []

    while not stopped:
        sock, addr = server.accept()
        print("Accepted connection from", addr)
        # todo: Authenicate user
        # Create the receiver thread
        connection = Receiver(sock, addr, config)
        connection.start()

        # Wait for single thread to stop
        #connection.join()

