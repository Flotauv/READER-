import logging, signal, time, os, sys
import multiprocessing as mp

# For debugging system statistics
import psutil

# Custom modules
from utils import *
from can_logger import Can_Logger
from led_manager import Led_Manager

# GENERAL CONFIGS
CONFIG_FILE = 'config.ini'
DEBUG_FILE = 'debug.log'

MAIN_PID = os.getpid()  # Store the main process ID
EXIT_MAIN = False  # Flag to control the main loop

# GLOBAL SIGNALS
stop_event = mp.Event()  # Event to signal the workers to stop

# Change to script directory
os.chdir(sys.path[0])
os.nice(-20)

def main():

    global config
    global logger
    global can_logger
    global led_manager

    # Load configuration file
    config = load_config(CONFIG_FILE)

    # Setup logging configuration
    logger = logging.getLogger(__name__)
    if config.logger.log_debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format=config.logger.log_format,
            datefmt=config.logger.date_format,
            filename=config.logger.log_path if config.logger.log_file else None,
            encoding='utf-8'
        )

    logger.info("[*] ------------- NEW RUN -------------")

    # Configure GPIO pins. Placeholder for future enhancements.
    led_manager = Led_Manager(config, logger)
    logger.info("GPIO pins configured.")
    
    # Set handler for Ctrl+C (SIGINT) to gracefully stop the application
    signal.signal(signal.SIGINT, handle_sigint)

    # Initialize CAN_Logger object
    can_logger = Can_Logger(config, logger, led_manager, stop_event)

    # Start processes for CAN_Logger
    if not can_logger.initialize_can_process():
        logger.error("Error on initializing CAN processes")
        return False

    # Start writer process for logging CAN messages
    can_logger.initialize_writer_process()

    # Main loop to keep the application running until Ctrl+C is pressed
    # and all has been stopped in a safe way
    while not EXIT_MAIN:
        time.sleep(1)
        # Display system statistics if debug logging is enabled
        if config.logger.log_debug:
            show_proc_statistics()

    # End of main function
    logger.info("[*] ------------- END OF RUN -------------")


def handle_sigint(sig, frame):
    '''
        Handler for Ctrl+C user interruption to stop all processes gracefully.
    '''
    global stop_event
    global EXIT_MAIN
    
    # Just father initiate the shutdown
    if os.getpid() == MAIN_PID:

        logger.info("Ctrl+C caught, stopping all processes...")

        stop_event.set()    # Signal the workers to stop
        can_logger.stop()   # Stop can_logger
        EXIT_MAIN = True    # Exit for main process

    else:
        # Just for childs
        pass


def show_proc_statistics():
    '''
        debug function for statistics
        Display statistics of CPU, RAM, and HDD usage along with network traffic.
    '''

    # Get CPU usage
    cpu_usage = psutil.cpu_percent()
    # Get RAM usage
    ram_usage = psutil.virtual_memory().percent
    # Get HDD usage
    hdd_usage = psutil.disk_usage('/').percent
    # Get network statistics
    traffic = psutil.net_io_counters()
    # Display statistics in log
    logger.info(f" ( CPU: {cpu_usage}%, RAM: {ram_usage}%, HDD: {hdd_usage}%, Traffic: {traffic.bytes_recv/(1024*1024*1024):.2f} Mbps, Errors: {traffic.errin}  )")



if __name__ == "__main__":
    main()