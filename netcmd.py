__author__ = 'ryanplyler'

# stdlib imports
import threading
import socket
import importlib
import select
import os

# third party imports
import yaml

# my code imports
from rcode.ipc.compipes import CommunicatorTwoWay


# Global settings
# todo: Write a command and control client for operation pdisk and server nodes to go on the two machines
# The command a control client should connect to all the servers at once
# Simple capabilities that a commands and response of the status of pdisk should be available
#TERM = '\r\n'

# Debugging test function


class Receiver(threading.Thread):
    def __init__(self, sock, addr, config, com):
        threading.Thread.__init__(self)
        self.sock = sock
        self.addr = addr
        self.config = config
        self.com = com

        self.inputs = [self.sock, self.com.slave_pipein]

        self.stopped = False
        # Need to convert string '\r\n' to literal
        self.TERM = self.config['global']['message_terminator']


        #self.socklist = [self.sock, self.signal_sock]

    def run(self):
        # Send connection acknowledgement
        self.sendline('You have connected')
        self.sendline('Here is a list of available commands:')
        self.send_commands()

        # Check is authentication is required
        if self.config['global']['require_auth']:
            # Authenticate the user
            # todo: add a timeout to authentication
            print("Authenticating client", self.addr)
            self.sock.send(b'Please enter access password: ')
            passwd = self.sock.recv(64)
            passwd = passwd[:-2].decode('UTF-8')
            if passwd == self.config['global']['auth_password']:
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
        # Otherwise the stopped flag doesn't work
        while not self.stopped:

            inputready, outputready, exceptready = select.select(self.inputs, [], [self.sock])

            for s in inputready:
                if s == self.sock:
                    # Do the reading

                    data = self.sock.recv(1024)
                    # todo: fix error where it cannot decode a Ctrl-C from the client
                    data = data[:-2].decode('UTF-8')
                    print("Received", data, "from", self.addr)

                    #Process default commands first
                    if data == "quit":
                        # Shutdown the Connection and Thread
                        self.stop("Client %s requested quit" % repr(self.addr), "Disconnecting...")
                        data = None

                    # Determine what the message means
                    elif data in self.config['messages']:
                        # Send command reception acknowledgement
                        self.send_ack(data)
                        self.process_msg(data)
                        data = None

                    # If connection is ended by the client


                    # If connection is ended by the server console (Ctrl-C)
                    elif self.stopped:
                        # Stop the connection and thread
                        self.stop()
                        data = None

                    # Unknown message received
                    else:
                        print("Unknown message:", data)
                        self.sendline('Message not understood, see server.yml')

                # If the control thread requests termination
                elif s == self.com.slave_pipein:
                    cmd = self.com.recv_from_master()
                    if cmd == b'stop':
                        self.stop("Shutting down receiver thread for %s" % repr(self.addr), "Server stopped at terminal")


    def stop(self, console_msg, client_reason):
        print(console_msg)
        self.sendline(client_reason)
        self.sock.shutdown(0)
        self.sock.close()
        self.stopped = True

    def send_commands(self):
        for i in self.config['messages']:
            self.sendline("\t" + i + " - " + self.config['messages'][i]['help'])

    def send_ack(self, msg):
        ack = self.config['messages'][msg]['ack']
        self.sendline(ack)

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

# Communicator named changed to TwoWay and stored in rcode.ipc.compipes

# There server class
class Server:
    def __init__(self, name, config_filename):

        # Setup config and settings
        self.config = self.load_config(config_filename)
        self.IP = self.config['global']['bound_ip']
        self.PORT = self.config['global']['server_port']
        self.TERM = self.config['global']['message_terminator']

        # Status Flags
        self.stopped = False

        # Create the server socket
        self.server_sock = self.create_socket(self.IP, self.PORT)

        print("netcmd server started on {}:{}".format(self.config['global']['bound_ip'],
                                                      self.config['global']['server_port']))

        # object local storage
        self.client_list = []

    def run(self):
        # todo: begin implementation for max connections
        while not self.stopped:
            try:

                sock, addr = self.server_sock.accept()
                # Create the communicator
                com = CommunicatorTwoWay(64)
                print("Accepted connection from", addr)
                # Create the receiver thread
                handle = Receiver(sock, addr, self.config, com)
                handle.start()
                self.client_list.append(handle)


            except(KeyboardInterrupt):
                print("\nShutting down...")
                self.stop_handles(self.client_list)
                self.stopped = True

    def create_socket(self, IP, PORT):
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((IP, PORT))
            server_sock.listen(10)
        except:
            server_sock = False
        return server_sock

    def load_config(self, config_filename):
        with open(config_filename) as configfile:
            config = yaml.load(configfile.read())

        return config

    def stop_handles(self, client_list):
       # for i in range(0, len(client_list)):
            #client_list[i].stop("Stopping connection %s" % repr(client_list[i].addr),
             #                   "Server stopped at console")

       # For each thread in the client_list, send its com input a 'stop' signal
        for i in range(0, len(client_list)):
            client_list[i].com.send_to_slave(b'stop')


if __name__ == "__main__":
    # Create Server
    server = Server("netcmd server", 'server.yml')
    server.run()

    print("Done.")