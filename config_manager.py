import configparser
import os

class ConfigManager:
    def __init__(self, config_file="api.ini"):
        self.config = configparser.ConfigParser()
        if os.path.exists(config_file):
            self.config.read(config_file)
        else:
            # Defaults if file is missing (useful for demo mode without config)
            self.config['hotel'] = {'url': 'http://localhost:5000', 'key': 'dummy'}
            self.config['band'] = {'url': 'http://localhost:5001', 'key': 'dummy'}
            self.config['global'] = {'retries': '3', 'delay': '0.1'}

    def get_hotel_config(self):
        return self.config['hotel']

    def get_band_config(self):
        return self.config['band']

    def get_global_config(self):
        return self.config['global']
