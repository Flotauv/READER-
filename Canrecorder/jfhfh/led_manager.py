import RPi.GPIO as GPIO
import traceback



class Led_Manager:
    '''
        Manages the GPIO pins for controlling the LEDs.
    '''

    def __init__(self, config, logger):

        self.config = config
        self.logger = logger

        # statusRGB shows the status of the Datalogger (three possible states):
        #   - Green:  powered on,
        #   - Red:    starting up,
        #   - Purple: log file saved.  
        # Map statusRGB pins to GPIO pins
        self.statusRGB = {
            "R": 1,      # GPIO01
            "G": 5,      # GPIO05
            "B": 6       # GPIO06
        }

        # channelsRGB shows the status of each CAN-FD bus
        # Map channelsRGB pins to GPIO pins
        base_gpios = [
            [27, 15],    # GPIO27, GPIO15
            [0, 22],     # GPIO00, GPIO22
            [3, 2],      # GPIO03, GPIO02
            [14, 4]      # GPIO14, GPIO04
        ]
        self.channelsRGB = {}
        try:
            for index, (key, value) in enumerate(vars(self.config.can).items()):
                if value:
                    self.channelsRGB[key] = base_gpios[index]
        except Exception as e:
            self.logger.error("Can't configure GPIO LEDs: {e}")
            self.logger.error(traceback.format_exc())

        # Initialize GPIO pins
        try:
            # Set GPIO pins
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Set `statusRGB` pins as OUT pins
            for pin in self.statusRGB.values():
                GPIO.setup(pin, GPIO.OUT)
            
            # Datalogger OFF --> `statusRGB` turned off 
            self.set_status("OFF")

            # Set `channelsRGB` pins as OUT pins
            for key, value in self.channelsRGB.items():
                for i in range(len(value)):
                    GPIO.setup(value[i], GPIO.OUT)
                # Turn off all `channelsRGB` pins
                self.set_chan_status(key,"OFF")
            
            # Set status RGB to `Starting`
            self.set_status("Starting")

        except Exception as e:
            self.logger.error("Can't configure GPIO LEDs: {e}")
            self.logger.error(traceback.format_exc())

        except RuntimeWarning as e:
            self.logger.debug(f"GPIO channel already in use: {e}")
            self.logger.error(traceback.format_exc())


    def set_status(self, status):
        '''
            Set the status LED.
                :param status: Status to set the LED. Possible values are:
                    - "OFF": Turn off the status LED.
                    - "ON": Set green the status LED.
                    - "Writing": Set purple the status LED.
                    - "Starting": Set red the status LED.
        '''

        if status == "OFF":  # Turn off the status LED
            GPIO.output(self.statusRGB["R"], GPIO.LOW)
            GPIO.output(self.statusRGB["G"], GPIO.LOW)
            GPIO.output(self.statusRGB["B"], GPIO.LOW)

        elif status == "ON":  # Set green the status LED
            GPIO.output(self.statusRGB["R"], GPIO.LOW)
            GPIO.output(self.statusRGB["G"], GPIO.HIGH)
            GPIO.output(self.statusRGB["B"], GPIO.LOW)

        elif status == "Writing":  # Set purple the status LED
            GPIO.output(self.statusRGB["R"], GPIO.HIGH)
            GPIO.output(self.statusRGB["G"], GPIO.LOW)
            GPIO.output(self.statusRGB["B"], GPIO.HIGH)

        elif status == "Starting":  # Set red the status LED
            GPIO.output(self.statusRGB["R"], GPIO.HIGH)
            GPIO.output(self.statusRGB["G"], GPIO.LOW)
            GPIO.output(self.statusRGB["B"], GPIO.LOW)

        else:
            self.logger.error(f"Unknown status: {status}")

    def set_chan_status(self, channel, status):
        '''
            Set the channel LED.
                :param channel: Channel to set the LED.
                :param status: Status to set the LED. Possible values are:
                    - "OFF": Turn off the channel LED.
                    - "RED": Set red the channel LED.
                    - "GREEN": Set green the channel LED.
        '''

        if status == "OFF":  # Turn off the channel LED
            GPIO.output(self.channelsRGB[channel][0], GPIO.LOW)
            GPIO.output(self.channelsRGB[channel][1], GPIO.LOW)

        elif status == "RED":  # Set red the channel LED
            GPIO.output(self.channelsRGB[channel][0], GPIO.HIGH)
            GPIO.output(self.channelsRGB[channel][1], GPIO.LOW)

        elif status == "GREEN":  # Set green the channel LED
            GPIO.output(self.channelsRGB[channel][0], GPIO.LOW)
            GPIO.output(self.channelsRGB[channel][1], GPIO.HIGH)

        else:
            self.logger.error(f"Unknown channel status: {status}")

