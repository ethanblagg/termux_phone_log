import signal
import argparse
from PhoneLog import PhoneLogger

# ========================== Parse Args ==========================
parser = argparse.ArgumentParser(description='Inputs for Phone Logger')
parser.add_argument('-d', '--delay', type=int, default=10, help='Delay between reads (Read takes approx 5s)')
parser.add_argument('-f', '--log_frequency', type=int, default=1, help='Log writes to database every [f] writes')
parser.add_argument('-r', '--retries', type=int, default=5, help='Number of retries on timeout before exit')
parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Log information verbosely')
parser.add_argument('-w', '--wait_time', type=int, default=20, help='Number of seconds to wait for data read/write to complete before retry')
args = parser.parse_args();

delay = abs(args.delay)
log_freq = abs(args.log_frequency)
retries_allowed = abs(args.retries)
verbose = args.verbose
wait_time = abs(args.wait_time)

config_file = '/data/data/com.termux/files/home/phone-logger/pl.conf'
freq_ctr = 0

pl = PhoneLogger(config_file, delay, log_freq, retries_allowed, verbose, wait_time)

signal.signal(signal.SIGINT, pl.sigint_handler)
signal.signal(signal.SIGALRM, pl.alarm_handler)

pl.connect_to_db()


# Loop to get and log data
while 1:

    # Get data from phone 
    pl.read_phone_data() 

    # send data to database
    pl.write_to_db()
    


        

    
