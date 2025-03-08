import time, datetime, queue, traceback
import multiprocessing as mp

# Custom modules
import can                                                # Custom modified version of python-can
from utils import updateSystemDate, getFilename           # Custom utility functions


class Can_Logger:
    '''
        Can_Logger class manages the logging of messages from multiple CAN buses.

        Key functionalities include:
            - Initialize and start CAN bus processes
            - Start a writer process for logging CAN messages
            - Synchronize timestamping between CAN buses
            - Renew the writer file periodically
    '''

    # Constructor
    def __init__(self, config, debug_logger, led_manager, stop_event):
        '''
            Initialize the Can_Logger object.
                :param config: Configuration object read from config.ini
                :param debug_logger: Logger object for debugging
                :param stop_event: Event to signal the workers to stop
        '''

        self.config = config
        self.logger = debug_logger
        self.led_manager = led_manager
        self.stop_event = stop_event

        # Get list of CAN buses
        self.can_list = list(vars(self.config.can).keys())

        # Internal signal events
        self.timestamp_event = mp.Event()   # Event to synchronize timestamping
        self.record_writer = mp.Event()     # Event to control writer's state

        # CAN buses and processes
        self.can_buses = []                 # List of CAN bus objects
        self.can_processes = []             # List of processes for CAN buses

        # Writer process and queue
        self.writer = None                  # Reference to writer instance object (BLFWriter)
        self.writer_process = None          # Reference to writer process child
        self.msg_queue = mp.Queue()         # Queue from CAN buses process to writer process
        

    def initialize_can_process(self):
        '''
            Initialize CAN bus processes for each CAN interface specified in the config.
        '''
        # Loop through each CAN interface in the config
        for key, value in vars(self.config.can).items():
            self.logger.info(f"CAN_{key}: {value}")
             # If the CAN interface is enabled
            if value:
                try:
                    # Initialize a CAN bus and add it to the list of CAN buses
                    bus = can.interface.Bus(channel=key, interface='socketcan', fd=True)
                    self.can_buses.append(bus)

                    # Start a process to log messages received from the CAN bus and add it to the list of processes
                    proc = mp.Process(target=self._can_process_handler, args=(bus, self.msg_queue,), name=f"can_bus{key}_log_process")
                    proc.start()
                    self.can_processes.append(proc)
                    self.logger.info(f"logbus {key} created")

                except Exception as error:
                    self.logger.error(f"Error on create process {key} error: {error}")
                    self.logger.error(traceback.format_exc())
                    return False
                
        return True


    def _can_process_handler(self, bus, message_queue):
        '''
            Handler for CAN bus processes. Log messages from a specific CAN bus channel.
            Key functionalities include:
                - Wait for timestamp_event for synchronization
                - Write messages from the queue to a file

            :param bus: CAN bus object
            :param message_queue: Queue from CAN buses process to writer process
        '''

        reading = False

        time_stats = datetime.datetime.now() #TODO: Just for statistics
        sended_bits = 0 #TODO: Just for statistics

        while not self.stop_event.is_set():
            try:
                # Receive message from bus with timeout
                message = bus.recv(0.5)

                # If something is received
                if message is not None:

                    # In system is not synchronized
                    if not self.timestamp_event.is_set():
                        # Look for a timestamped frame
                        timestamped_frame = hex(int(self.config.general.timestamped_frame, base=16))
                        message_id = hex(message.arbitration_id)
                        if message_id == timestamped_frame:
                            # Timestamped frame received, synchronize system time
                            self.logger.info(f"can {bus.channel[3]} - Timestamped frame received.")
                            if not updateSystemDate(message):
                                self.logger.error("Error updating system date")
                                self.logger.error(traceback.format_exc())
                                continue
                            self.logger.info("System date updated")
                            time.sleep(1)
                            self.timestamp_event.set()
                    
                    # Toggle channel LED
                    if not reading and self.record_writer.is_set():
                        self.led_manager.set_chan_status(self.can_list[int(bus.channel[3])], "GREEN")
                        reading = True
                    elif reading and not self.record_writer.is_set():
                        self.led_manager.set_chan_status(self.can_list[int(bus.channel[3])], "RED")
                        reading = False
                    
                    # If system is synchronized, and writer is initialized, put message into queue
                    if self.record_writer.is_set():
                        # Check if queue is full
                        if message_queue.full():
                            self.logger.critical("Queue full, danger of data loss.")
                        else:
                            message_queue.put(message)
                            sended_bits += len(message.data)
                else:
                    self.logger.info("Empty")

            except Exception as error:
                self.logger.error(f"log bus error on channel {bus.channel[3]}: {error}")
                self.logger.error(traceback.format_exc())
            
            # TODO: Show statistics
            if self.config.logger.log_debug:
                time_diff = (datetime.datetime.now() - time_stats).total_seconds()
                if time_diff > 1:
                    #Calculated bits per second
                    bits_per_second = int(sended_bits / time_diff)
                    #Calculated kB per second
                    self.logger.info(f"Sent {bits_per_second} bits in {time_diff} seconds ({bits_per_second / 1024:.2f} kbps)")
                    time_stats = datetime.datetime.now()
                    sended_bits = 0
        
        # Turn off channel LED
        self.led_manager.set_chan_status(self.can_list[int(bus.channel[3])], "OFF")

        # MSG exit
        self.logger.info(f"Exiting log bus {bus.channel[3]}")
        return 0
    


    def initialize_writer_process(self):
        '''
            Initialize the process responsible for writing logged messages to file.
        '''
        # Create a new writer instance and start the writer process
        self.writer_process = mp.Process(target=self._writer_process_handler, args=(self.msg_queue,), name="writer_process")
        self.writer_process.start()



    def _writer_process_handler(self, message_queue):
        '''
            Handler for the writer process. Write messages from the queue to a file.
            Key functionalities include:
                - Wait for timestamp_event for synchronization
                - Initialize the writer after synchronization
                - Write messages from the queue to a file
                - Renew the writer file periodically

            :param message_queue: Queue from CAN buses process to writer process
        '''

        # Wait for timestamp_event for synchronization
        self.logger.info("Waiting for timestamp_event for sync...")
        while not self.timestamp_event.is_set():
            time.sleep(1)
            # Exit if stop_event is set
            if self.stop_event.is_set():
                self.logger.info("Stop event set, stopping writer process.")
                return

        # Initialize the writer after synchronization
        try:
            self._init_writer()
            time.sleep(1)
            self.record_writer.set()
            self.logger.info("Writer initialized")
            self.led_manager.set_status("Writing")
        except Exception as error:
            self.logger.error(f"Writer initialization error: {error}")
            self.logger.error(traceback.format_exc())

        # Main loop for writing messages from the queue to a file
        start_time = datetime.datetime.now()
        time_stats = datetime.datetime.now() #TODO: Just for statistics
        sended_bits = 0 #TODO: Just for statistics
        while not self.stop_event.is_set():
            if message_queue.full():
                self.logger.critical("Queue full, danger of data loss.")

            try:
                # Retrieve message from queue with timeout
                message = message_queue.get(timeout=0.5)
                if message is not None:
                    sended_bits += len(message.data)
                    self.writer.on_message_received(message)
            # If is empty, not throw an error
            except queue.Empty:
                self.logger.info("Queue empty")
                pass
            except Exception as error:
                self.logger.error(f"Writer process error: {error}")

            # Renew writer file after a specified duration
            time_diff = (datetime.datetime.now() - start_time).total_seconds()
            if time_diff > int(self.config.general.seconds_per_log):
                self.renew_writer()
                start_time = datetime.datetime.now()
            
            # TODO: Show statistics
            if self.config.logger.log_debug:
                time_diff = (datetime.datetime.now() - time_stats).total_seconds()
                if time_diff > 1:
                    #Calculated bits per second
                    bits_per_second = int(sended_bits / time_diff)
                    #Calculated kb per second
                    self.logger.info(f"Sent {bits_per_second} bits in {time_diff} seconds ({bits_per_second / 1024 :.2f} kbps)")
                    # Show queue size on Mb
                    self.logger.info(f"Queue size: {message_queue.qsize() / 1024 / 1024 :.2f} Mb")
                    time_stats = datetime.datetime.now()
                    sended_bits = 0



    def renew_writer(self):
        '''
            Change the writer file when has reached the specified duration.
            Key functionalities include:
                - Stop the current writer
                - Initialize a new writer
        '''
        self.logger.info("Changing writer file...")
        
        try:
            self.record_writer.clear()
            self.led_manager.set_status("OFF")
            # Stop the current writer
            self.writer.stop()
            # Initialize a new writer
            self._init_writer()
            self.record_writer.set()
            self.led_manager.set_status("Writing")
            return True
        
        except Exception as error:
            self.logger.error(f"Writer renew error: {error}")
            self.logger.error(traceback.format_exc())
            return False


    def _init_writer(self):
        '''
            Initialize a writer object to store the CAN messages in a new log file.
        '''
        try:
            self.logger.info("Timestamped frame received, starting to log data.")
            filepath, filename = getFilename(self.config)
            self.logger.info(f"file path set: {filepath}{filename}")
            self.writer = can.BLFWriter(
                f"{filepath}{filename}",
                max_container_size=int(self.config.writer.writer_buffer_size),
                compression_level=int(self.config.writer.compression_level)
                )
        except Exception as error:
            self.logger.error(f"Writer initialization error: {error}")
            self.logger.error(traceback.format_exc())
            return False


    def stop(self):
        '''
            Stop all CAN bus processes and the writer process in a safe way.
        '''

        try:
            self.logger.info(f"Stopping can_rec_proc: shutting down can buses.")
            # Stop all CAN bus processes
            for can_proc in self.can_processes:
                can_proc.terminate()
                can_proc.join()
                self.logger.info(f"CAN {can_proc.name} process stopped.")
            # Shutdown all CAN buses
            for can_bus in self.can_buses:
                can_bus.shutdown()
                self.logger.info(f"CAN {can_bus.channel[3]} bus stopped.")
        except Exception as error:
            self.logger.error(error)
            self.logger.error(traceback.format_exc())

        # Stop the writer process
        try:
            if self.writer:
                self.logger.info("Stopping writer process...")
                self.led_manager.set_status("OFF")
                self.writer.stop()
        except Exception as error:
            self.logger.error(error)
            self.logger.error(traceback.format_exc())
        