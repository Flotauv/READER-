import configparser, subprocess, os, datetime
from types import SimpleNamespace
from can import Message
from FrameInject import create_blf

def load_config(config_file):
    '''
        Load a config file and return a namespace with the values.
        It helps to get values easly. (For examp. config.general.rpi_name)
        
            :param config_file: Path to the config file
            :return: Namespace with the values
    '''
    config = configparser.ConfigParser()
    config.read(config_file)

    # Convert .ini file sections to a SimpleNamespace
    cfg = SimpleNamespace()
    for section in config.sections():
        section_dict = {}
        for key, value in config[section].items():
            # Convert "true" and "false" strings to boolean values
            if value.lower() == 'true':
                section_dict[key] = True
            elif value.lower() == 'false':
                section_dict[key] = False
            else:
                section_dict[key] = value
        setattr(cfg, section.lower(), SimpleNamespace(**section_dict))

    return cfg


def updateSystemDate(message):
    '''
        Syncronize the operating system date based on CAN timesamps.
        This function assures that the system date is always synchronized with the CAN messages.

            :param message: A CAN message from which to extract date and time.
    '''
    # Extract date and time information from the CAN message data
    data = message.data
    print(data)
    data_bits = ''.join([bin(x)[2:].zfill(8) for x in data])
    """
    # Parse year, month, day, hour, minute, and seconds from the data
    # TODO: Probably doesn't work (26 bit for year and seconds?)
    year = '20' + str(int(data_bits[16:26], 2))
    month = str(int(data_bits[32:36], 2)).zfill(2)
    day = str(int(data_bits[40:45], 2)).zfill(2)
    hour = str(int(data_bits[0:5], 2)).zfill(2)
    minute = str(int(data_bits[8:14], 2)).zfill(2)
    seconds = str(int(data_bits[26:32], 2)).zfill(2)

    # Construct a date string and update the system's date using the 'date' command
    date_string = f"{year}-{month}-{day} {hour}:{minute}:{seconds}"
    ret = subprocess.call(['sudo', 'date', '-s', date_string]) #TODO probleme ici 
    """
    return data



def getFilepath(config):
    '''
        Creates a file path to store recordings based on the current date and time.

            :param config: Configuration object containing general and writer settings.
            :return: Tuple with the directory path and filename.
    '''
    prefix = config.general.rpi_name + "_" + datetime.datetime.now().strftime(config.logger.date_format)  # Example: 'RPi1_2024-09-22_11-33-06'
    if filepath == "":
        filepath = config.writer.recordings_dir + prefix + "/"
        os.mkdir(filepath)
    filename = prefix + config.writer.file_format
    return filepath, filename


def getFilename(config):
    """
        Generate the filename and directory path for storing recording files.

            :param config: Configuration object containing general and writer settings.
            :return: Tuple with the directory path and filename.
    """
    prefix = config.general.rpi_name + "_" + datetime.datetime.now().strftime(config.logger.date_format)  # Example: 'RPi1_2024-09-22_11-33-06'
    filepath = config.writer.recordings_dir
    filename = prefix + config.writer.file_format
    return filepath, filename


# --- Test --- 
CONF_FILE="config.ini"
message_test = Message(10,2,True,True,True,data=bytearray("Test",'utf-8'))


print(updateSystemDate(create_blf(CONF_FILE)))