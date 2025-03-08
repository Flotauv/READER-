#!/bin/python3

import can
import time
import signal

interfaz = "mcp0"
logFile = "can.log"

exit_main = False

def handle_sigint(sig, frame):
    global exit_main
    exit_main = True

# MAIN
if __name__ == "__main__":

    # Set handler for Ctrl+C (SIGINT) to gracefully stop the application
    signal.signal(signal.SIGINT, handle_sigint)

    # Initialize can bus
    can_bus = can.interface.Bus(channel=interfaz, interface='socketcan', fd=True)

    # Open log file
    with open(logFile, "w") as outfile:
        while not exit_main:
            # Get message from bus
            try:
                message = can_bus.recv(timeout=1.0)  # Set a timeout (in seconds)
            except can.CanError:
                print("Error on receive message")
                continue

            # If something is received
            if message is not None:
                # Write message to log file
                outfile.write(f"{message.timestamp:.6f}|{message.arbitration_id:03X}#{message.dlc:02X}\n")
                outfile.flush()

    # Shutdown can bus
    can_bus.shutdown()
    
    # Close log file
    outfile.close()