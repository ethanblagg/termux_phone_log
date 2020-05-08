import mysql.connector    
from mysql.connector import errorcode
import sys
import signal
import subprocess
import socket
import urllib.request
import json
import configparser
import time
import datetime


class PhoneLogger:
    def __init__(self, config_file, delay, log_freq, retries_allowed, verbose, wait_time):
        self.conf_file_str = config_file
        self.delay = delay
        self.log_freq = log_freq
        self.retries_allowed = retries_allowed
        self.verbose = verbose
        self.wait_time = wait_time
        self.freq_ctr = 0

        self.phone_data = {'time_now':'', 'batt_health':'', 'batt_percent':'', 'batt_plugged':'', 'batt_status':'', 'batt_tempC':'', 'batt_current':'',
                  'latitude':'', 'longitude':'', 'altitude':'', 'accuracy':'', 'vertical_accuracy':'', 'bearing':'', 'speed':'', 'pressure':0}
    


        # ========================= Log to Console =======================
    class LogType:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKGREEN = '\033[92m'
        OKCYAN = '\033[96m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'



    def log(self, msg, log_type=LogType.ENDC):
        t = datetime.datetime.now()
        print("{}[{} Phone-Logger] {}{}".format(log_type, t, self.LogType.ENDC, msg))

    

    # ==================== Interrupt handlers =========================
    
    def sigint_handler(self, sig_num, frame): 
        self.log('Exiting...your mother', self.LogType.HEADER)
        sys.exit(0)
    

    def alarm_handler(self, signum, frame):
        raise TimeoutError
    

    def fatal(self):
        sys.exit(0)



    # ==================== Set DB connection port ====================
    
    def get_ip_port_config(self):

        ip_str = 'ip-remote'
        port_str = 'port-remote'

        try:
            signal.alarm(self.wait_time)
            url = urllib.request.urlopen("http://ipv4.wtfismyip.com/json")
            signal.alarm(0)

            data = json.loads(url.read().decode())
            
            if 'YourFuckingIPAddress' in data:
                
                if "73.14.127.132" in data['YourFuckingIPAddress']:    

                    ip_str = 'ip-local'
                    port_str = 'port-local'

            else:
                self.log("No fucking IP address from wtfismyip.com", self.LogType.WARNING)


        except TimeoutError as e:

            self.log("Unable to figure out my fucking IP. Will pretend I\'m off in the internet", self.LogType.WARNING)

        return ip_str, port_str



    # ======================= Get Database config ====================
    
    def get_db_config(self):

        config = configparser.ConfigParser()
        config.read(self.conf_file_str)

        ip_str, port_str = self.get_ip_port_config()

        if 'db-config' in config:
            try:
                db_config = config['db-config']
                
                self.name = db_config['db']
                self.ip = db_config[ip_str]
                self.port = db_config[port_str]
                self.user = db_config['u']
                self.pw = db_config['p']
                self.table = db_config['t']

            except Exception as e:
                self.log(e)
                self.fatal()



    # ======================= Connect to Database =====================
    def connect_to_db(self):

        self.get_db_config()

        conn_attempts = 0 
        conn_success = False

        while not conn_success:

            try:
                signal.alarm(self.wait_time)
                self.con = mysql.connector.connect(user=self.user, 
                                                   password=self.pw,
                                                   host=self.ip,
                                                   database=self.name,
                                                   port=self.port,
                                                   buffered=True)
                
                self.cursor = self.con.cursor()
                signal.alarm(0)
                conn_success = True
                self.log("Successfully connected to {} on {}".format(self.name, self.ip), self.LogType.OKGREEN)


            except mysql.connector.Error as err:
                
                if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                    self.log("Authentication error. Check username and password.", self.LogType.FAIL)
                
                elif err.errno == errorcode.ER_BAD_DB_ERROR:
                    self.log("Database does not exist.", self.LogType.FAIL)
                
                else:
                    self.log("Unknown connection error: {}".format(err), self.LogType.FAIL)

                self.fatal()


            except TimeoutError as e:
                
                conn_attempts = conn_attempts + 1
                self.log("Timeout {}/{} while attempting connection to host".format(conn_attempts, self.retries_allowed), self.LogType.WARNING)
                
                if conn_attempts >= self.retries_allowed:
                    self.log("Maximum connection attempts allowed. Exiting.", self.LogType.FAIL)
                    self.fatal()


            except Exception as e:

                self.log("Unable to connect.", self.LogType.FAIL)
                self.fatal()


        self.log("Beginning to record phone data to {}".format(self.ip), self.LogType.OKGREEN)
        self.log("Delay between reads: {}s".format(self.delay), self.LogType.OKGREEN)
        self.log("Output activity to console every {} records".format(self.log_freq), self.LogType.OKGREEN)
        self.log("Use Ctrl-C to stop this process (or close shell).", self.LogType.OKGREEN)



    def read_phone_data(self):
        
        if self.verbose:
            self.log('Begin read data from phone', self.LogType.OKBLUE)

        read_attempts = 0 
        read_success = False
        
        while not read_success:
            try:
                signal.alarm(self.wait_time)
                battery_status = json.loads(subprocess.check_output("termux-battery-status", stderr=subprocess.STDOUT, shell=True))
                location = json.loads(subprocess.check_output("termux-location", stderr=subprocess.STDOUT, shell=True))
                sensor_data = json.loads(subprocess.check_output("termux-sensor -n1 -s Barometer", stderr=subprocess.STDOUT, shell=True))
                self.phone_data['time_now'] = datetime.datetime.now()
                signal.alarm(0)

                read_success = True

            except TimeoutError as e:
                read_attempts = read_attempts + 1
                self.log("Timeout {}/{} while attempting to read data from phone".format(read_attempts, self.retries_allowed), self.LogType.WARNING)
                
                if read_attempts >= self.retries_allowed:
                    self.log("Maximum read attempts attempted. Exiting.", self.LogType.FAIL)
                    self.fatal()

            except Exception as e:
                self.log('Error while gathing data', self.LogType.FAIL)
                self.log(e, self.LogType.FAIL)
                self.fatal()

        self.set_phone_data(battery_status, location, sensor_data)



    def set_phone_data(self, battery_status, location, sensor_data):
        try:
            if 'health' in battery_status:
                self.phone_data['batt_health'] = battery_status['health']
                    
            if 'percentage' in battery_status:
                self.phone_data['batt_percent'] = battery_status['percentage']

            if 'plugged' in battery_status:
                self.phone_data['batt_plugged'] = battery_status['plugged']

            if 'status' in battery_status:
                self.phone_data['batt_status'] = battery_status['status']

            if 'temperature' in battery_status:
                self.phone_data['batt_tempC'] = battery_status['temperature']

            if 'current' in battery_status:
                self.phone_data['batt_current'] = battery_status['current']

            if 'latitude' in location:
                self.phone_data['latitude'] = location['latitude']

            if 'longitude' in location:
                self.phone_data['longitude'] = location['longitude']

            if 'altitude' in location:
                self.phone_data['altitude'] = location['altitude']

            if 'accuracy' in location:
                self.phone_data['accuracy'] = location['accuracy']

            if 'vertical_accuracy' in location:
                self.phone_data['vertical_accuracy'] = location['vertical_accuracy']

            if 'bearing' in location:
                self.phone_data['bearing'] = location['bearing']

            if 'speed' in location:
                self.phone_data['speed'] = location['speed']

            if 'BMP280 Barometer' in sensor_data and 'values' in sensor_data['BMP280 Barometer']:
                self.phone_data['pressure'] = sensor_data['BMP280 Barometer']['values'][0]

        except Exception as e:
            self.log('Error while filling dictionary for DB', self.LogType.FAIL)
            self.log(e, self.LogType.FAIL)
            self.fatal()

        
        if self.verbose:
            self.log('Last data read from phone:', self.LogType.OKBLUE)
            self.log(phone_data, self.LogType.OKCYAN)



    def write_to_db(self):

        # ==================== send data to database =======================
        write_attempts = 0
        write_success = False

        while not write_success:

            try:
                add_record = ("INSERT INTO log "
                                    "(log_dt, batt_health, batt_percent, batt_plugged, batt_status, batt_tempC, batt_current, "
                                    "latitude, longitude, altitude, accuracy, vertical_accuracy, bearing, speed, pressure) "
                              "VALUES "
                                    "(%(time_now)s, %(batt_health)s, %(batt_percent)s, %(batt_plugged)s, %(batt_status)s, %(batt_tempC)s, %(batt_current)s, "
                                    "%(latitude)s, %(longitude)s, %(altitude)s, %(accuracy)s, %(vertical_accuracy)s, %(bearing)s, %(speed)s, %(pressure)s)")

                signal.alarm(self.wait_time)
                self.cursor.execute(add_record, self.phone_data)
                self.con.commit()
                signal.alarm(0)

                write_success = True


            except mysql.connector.errors.DatabaseError as e:
                
                if e.errno == 2055:
                    self.log(e, self.LogType.WARNING)
                    self.log('Attempting to reconnect', self.LogType.OKGREEN)
                    self.connect_to_db()

                else:
                    self.fatal()
                    self.log('Problem while attempting to write to DB', self.LogType.FAIL)
                    self.log(e, self.LogType.FAIL)


            except TimeoutError as e:
                write_attempts = write_attempts + 1
                self.log("Timeout {}/{} while sending to server".format(write_attempts, self.retries_allowed), self.LogType.WARNING)

                if write_attempts >= self.retries_allowed:
                    self.log("Maximum send attempts allowed. Exiting.", self.LogType.FAIL)


        self.freq_ctr = self.freq_ctr + 1

        if self.freq_ctr % self.log_freq == 0:
            self.log("{} record(s) stored to database".format(self.log_freq), self.LogType.OKBLUE)
            self.freq_ctr = 0

        self.sleep()



    def sleep(self):

        if self.verbose:
            log("Sleeping for {}s".format(self.delay), self.LogType.OKBLUE)

        time.sleep(self.delay)
