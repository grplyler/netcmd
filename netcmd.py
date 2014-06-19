__author__ = 'ryanplyler'
import threading
import actions
import yaml
import socket
import importlib
import sys
import binascii
from time import sleep
import select
import asyncore

# Global settings
# todo: Write a command and control client for operation pdisk and server nodes to go on the two machines
# The command a control client should connect to all the servers at once
# Simple capabilities that a commands and response of the status of pdisk should be available
#TERM = '\r\n'

# Debugging test function


class Receiver(threading.Thread):
    def __init__(self, sock, addr, config):
        self.sock = sock
        self.addr = addr
        self.config = config
        self.stopped = False
        # Need to convert string '\r\n' to literal
        self.TERM = self.config['global']['message_terminator']
        threading.Thread.__init__(self)

        #self.socklist = [self.sock, self.signal_sock]

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
        # todo: Use select for asychonus reception off the socket
        # Otherwise the stopped flag doesn't work
        while not self.stopped:
            print("looping")

            try:
                inputready, outputready, exceptready = select.select([self.sock], [], [self.sock])
            except (OSError):
                print("Socket Disconnected")


            print("Passed select")

            for s in inputready:
                if s == self.sock:
                    # Do the reading
                    data = self.sock.recv(1024)
                    data = data[:-2].decode('UTF-8')
                    print("Received", data, "from", addr)


            # Determine what the message means
            if data in self.config['messages']:
                self.process_msg(data)

            # If connection is ended by the client
            elif data == "quit":
                # Shutdown the Connection and Thread
                print("Disconnecting", addr)
                self.sendline('Disconnecting...')
                self.stop()

            # If connection is ended by the server console (Ctrl-C)
            elif self.stopped:
                # Stop the connection and thread
                self.stop()

            # Unknown message received
            else:
                print("Unknown message:", data)
                self.sendline('Message not understood, see server.yaml')

    def stop(self, console_msg, client_reason):
        print(console_msg)
        self.sendline(client_reason)
        self.sock.shutdown(0)
        self.sock.close()
        self.stopped = True

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
        self.sock.send(bytes(msg + self.TERM, 'utf-8'))

    def get_action(self, action_string):
        mod_name, func_name = action_string.rsplit('.')
        mod = importlib.import_module(mod_name)
        func = getattr(mod, func_name)
        return func

# There asyncore server class
class Server(asyncore.dispatcher):
    def __init__(self, name, config):
        self.config = config
        self.IP = self.config['global']['bound_ip']
        self.PORT = self.config['global']['server_port']

        # Stopping flag
        self.stopped = False

        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind((IP, PORT))
        self.listen(10)

    def handle_accepted(self, sock, addr):
        handler =

    def load_config(self, filename):
        with open(filename, 'r') as configfile:
            config = yaml.load(configfile.read())

        return config

if __name__ == "__main__":
    with open('server.yaml') as configfile:
        config = yaml.load(configfile.read())

    # Create the server
    server = Server("netcmd server", config)

    # Start the async loop
    asyncore.loop()




