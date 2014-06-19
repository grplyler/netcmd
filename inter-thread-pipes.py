__author__ = 'ryanplyler'

# Create a seperate thread and give it a subprocess.Popen pipe to receive signals on
# Process the sockets (or Pipes) with select.select()
# When a certain signal is sent by the main thread, stop the thread with stopped flag

# Update: Maybe you io instead of pipes
# Update 1.5: Use os.pipe
# Update 2: Use named pipes or sockets for inter thread communication as they can be used with select

import pipes
import select
import threading
import io
import os
import sys
import socket


class MyThread(threading.Thread):
    def __init__(self, channel):
        threading.Thread.__init__(self)
        self.channel = channel
        self.stopped = False

        self.inputs = [self.channel]

    def run(self):
        print("Thread-1 Started")
        while not self.stopped:
            inputready, outputready, errors = select.select(self.inputs, [], [])
            for i in inputready:
                if i == self.channel:
                    signal = os.read(readable_pipe, 64)
                    print("The thread received stuff on the pipe: %s" % signal)
                    if signal == b'stop':
                        print("Stop command received.")
                        print("Exiting.")
                        self.stopped = True
                        break



if __name__ == "__main__":

    # Create the communication socket (UNIX)
    com = os.pipe()
    readable_pipe = com[0]
    writeable_pipe = com[1]

    t = MyThread(readable_pipe)
    t.start()

    stopped = False

    while not stopped:
        command = input("Command to send to thread: ")
        os.write(writeable_pipe, bytes(command, 'UTF-8'))







