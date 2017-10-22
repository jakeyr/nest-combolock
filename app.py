import sseclient
import urllib3
import certifi
import json
import pprint
import collections
import os
import aiohttp
import asyncio
import pyalarmdotcom
import logging

from itertools import islice

# initialize logger and set log level based on DEBUG mode
_LOGGER = logging.getLogger(__name__)

DEBUG = os.environ.get('DEBUG',False)

logging.basicConfig(level=(logging.DEBUG if DEBUG else logging.INFO), 
                    format='%(relativeCreated)6d %(threadName)s %(message)s')

# set HTTP logging based on DEBUG mode
if DEBUG:
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

# get the Nest API auth token from the environment
TOKEN = os.environ.get("NEST_TOKEN")

# also retrive the right thermostat ID from the environment
NEST_API_URL  = 'https://developer-api.nest.com/devices/thermostats/{0}/target_temperature_f'.format(os.environ.get('THERMOSTAT_ID'))

# other environment variables
COMBINATION   = list(json.loads(os.environ.get("COMBINATION")))
ALWAYS_UNLOCK = os.environ.get('ALWAYS_UNLOCK',False)
ADC_USER      = os.environ.get('ALARMDOTCOM_USERNAME')
ADC_PASS      = os.environ.get('ALARMDOTCOM_PASSWORD')

def window(seq, n=2):
    "Returns a sliding window (of width n) over data from the iterable"
    "   s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...                   "
    it = iter(seq)
    result = tuple(islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result

def new_tumbler():
    "Returns a new empty deque representing a tumbler."
    return collections.deque(20*[0],20)

def lock_is_open(combo, tumbler):
    "Check if the tumbler contains the combination besed on"
    "a simple combination lock algorithm"
    
    # grab the last number
    final = tumbler[-1]
    
    # cut the list down to only the numbers that are "edges", 
    # i.e. numbers where the lock changed direction
    #
    # also add in the final digit because we may have stopped on that one
    check = [x[1] for x in window(tumbler,3) if max(x) == x[1] or min(x) == x[1]] + [final]

    _LOGGER.info("check list is {0}".format(check))

    # convert the list to check into windows of len(combo) size
    # this allows us to use a simple "in" operator to check if the combo
    # is inside the list
    check = [x for x in window(check,len(combo))]
    
    # is the combo present in the tumbler?
    found = (tuple(combo) in check)
    
    _LOGGER.debug("found {0} in {1}?: ${2}".format(combo,check,found))
    
    return found

async def get_data_stream(session, loop, token, api_endpoint):
    """ 
    Listens to a Nest thermostat and disarms the alarm if the
    right combination is found inside the stream of changing temperatures.
    """

    # initialize an empty tumbler
    tumbler = new_tumbler()


    # set up the HTTP call to the Nest API
    headers = {
        'Authorization': "Bearer {0}".format(token),
        'Accept': 'text/event-stream'
    }

    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',
                               ca_certs=certifi.where())

    # call Nest API and get back a blocking generator of Nest events
    response = http.request('GET', api_endpoint, headers=headers, preload_content=False)
    client   = sseclient.SSEClient(response)

    # loop over the generator indefinitely and handle the incoming events
    for event in client.events(): 
        event_type = event.event
        
        _LOGGER.debug("event: {0}".format(event_type))
        
        # most of these events don't matter to us
        if event_type == 'open':
            _LOGGER.info("The event stream has been opened")
        elif event_type == 'keep-alive':
            _LOGGER.info("No data updates. Receiving an HTTP header to keep the connection open.")
        elif event_type == 'auth_revoked':
            _LOGGER.error("The API authorization has been revoked.")
            _LOGGER.error("revoked token: ", event.data)
        elif event_type == 'error':
            _LOGGER.error("Error occurred, such as connection closed.")
            _LOGGER.error("error message: ", event.data)

        # ok, this is the event we care about
        elif event_type == 'put':
            _LOGGER.debug("The data has changed (or initial data sent)")

            data = json.loads(event.data)    

            # put the new value into the tumbler
            tumbler.append(data["data"])        

            _LOGGER.info("Tumbler is now {0}".format(tumbler))

            if (lock_is_open(COMBINATION, list(tumbler)) or ALWAYS_UNLOCK):

                # zero out the tumbler
                tumbler = new_tumbler()

                _LOGGER.info("Lock unlocked!")

                # make an HTTP request to Alarm.com to disarm the alarm
                adc = pyalarmdotcom.Alarmdotcom(ADC_USER,ADC_PASS,session,loop)
                await adc.async_login()
                await adc.async_alarm_disarm()
        else:
            _LOGGER.error("Unknown event, no handler for it.")

async def main(loop):
    async with aiohttp.ClientSession() as session:
        await get_data_stream(session, loop, TOKEN, NEST_API_URL)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
