__author__ = 'ryanplyler'
import threading
import yaml
import socket
import importlib
import select
import os

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
        self.i = com[0] # readable pipe for control thread communication


        self.inputs = [self.sock, self.i]

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
                elif s == self.i:
                    cmd = os.read(self.i, 64)
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

# todo: create the communicator class
class Communicator:
    #todo: simplify the Communicator structure to contain both the in and out pipes for the 2 threads
    # todo: and not rely on the Channel class
    """ A class that hold two Channel class for two way communication
        between threads.
        Example:
            Thread-1
            and Thread-2

            Thread 1 is the main thread.
            For Thread 1 to communicate with Thread-2, he has to send a message on master_send
            And that value can be read from the Thread-2 with master_recv

            For Thread-2 to send a message back to Thread-1, he has to send a message on slave_send
            and Thread-1 can receive that message on recv_slave

            Theoretically...

            Diagram:
                Send:
                Thread-1 --> Thread-2 use master_send()
                Recv:
                Thread-2 <-- Thread-1 use recv_master()

                Send:
                Thread-2 --> Thread-1 use slave_send()
                Recv:
                Thread-1 <-- Thread-2 use recv_slave()
    """

    def __init__(self, buffer_len=64):
        self.buffer_len = buffer_len
        self.pipe1 = os.pipe()
        self.pipe2 = os.pipe()

        # The two endpoints, a master and a slave
        self.master_pipeout = self.pipe1[1] # the masters output
        self.slave_pipein = self.pipe1[0]  # = the slave's input

        self.slave_pipeout = self.pipe2[1] # the slave's output
        self.master_pipein = self.pipe2[0] # = the master's input

    def send_to_master(self, bytes):
        os.write(self.slave_pipeout, bytes)

    def send_to_slave(self, bytes):
        os.write(self.master_pipeout, bytes)

    def recv_from_master(self):
        return os.read(self.slave_pipein, self.buffer_len)

    def recv_from_slave(self):
        return os.read(self.master_pipein, self.buffer_len)


# There server class
class Server:
    def __init__(self, name, config_filename):
        with open(config_filename) as configfile:
            config = yaml.load(configfile.read())
        self.config = config
        self.IP = self.config['global']['bound_ip']
        self.PORT = self.config['global']['server_port']
        self.stopped = False
        self.TERM = self.config['global']['message_terminator']



        # Create the sockets
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.IP, self.PORT))
        self.server_sock.listen(10)

        print("netcmd server started on {}:{}".format(config['global']['bound_ip'], config['global']['server_port']))

        self.client_list = []

    def run(self):
        # todo: begin implementation for max connections
        while not self.stopped:
            try:

                sock, addr = self.server_sock.accept()
                # Create the communicator
                com = os.pipe()
                print("Accepted connection from", addr)
                # Create the receiver thread
                handle = Receiver(sock, addr, self.config, com)
                handle.start()
                self.client_list.append(handle)


            except(KeyboardInterrupt):
                print("\nShutting down...")
                self.stop_handles(self.client_list)
                self.stopped = True

    def stop_handles(self, client_list):
       # for i in range(0, len(client_list)):
            #client_list[i].stop("Stopping connection %s" % repr(client_list[i].addr),
             #                   "Server stopped at console")

       # For each thread in the client_list, send its com input a 'stop' signal
        for i in range(0, len(client_list)):
            os.write(client_list[i].com[1], b'stop')


if __name__ == "__main__":
    # Create Server
    server = Server("netcmd server", 'server.yml')
    server.run()
    s = Communicator()

    print("Done.")