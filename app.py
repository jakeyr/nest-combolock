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


_LOGGER = logging.getLogger(__name__)

# try:
#     import http.client as http_client
# except ImportError:
#     # Python 2
#     import httplib as http_client
# http_client.HTTPConnection.debuglevel = 1

# set the token from your OAuth2 code here
TOKEN = os.environ.get("NEST_TOKEN")

# The API endpoint from where you want to receive events
NEST_API_URL  = 'https://developer-api.nest.com/devices/thermostats/{0}/target_temperature_f'.format(os.environ.get('THERMOSTAT_ID'))

COMBINATION   = list(json.loads(os.environ.get("COMBINATION")))
ALWAYS_UNLOCK = os.environ.get('ALWAYS_UNLOCK',False)
ADC_USER = os.environ.get('ALARMDOTCOM_USERNAME')
ADC_PASS = os.environ.get('ALARMDOTCOM_PASSWORD')

TUMBLER_STOP_INTERVAL = float(os.environ.get('TUMBLER_STOP_INTERVAL',1.5))

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
    return collections.deque(20*[0],20)

def lock_is_open(combo, tumbler):
    
    # remove the last number as that 
    final = tumbler[-1]
    
    check = [x[1] for x in window(tumbler,3) if max(x) == x[1] or min(x) == x[1]] + [final]
    _LOGGER.info("check list is {0}".format(check))
    check = [x for x in window(check,len(combo))]
    found = (tuple(combo) in check)
    _LOGGER.debug("found {0} in {1}?: ${2}".format(combo,check,found))
    return found

async def get_data_stream(session, loop, token, api_endpoint):
    """ Start REST streaming device events given a Nest token.  """
    headers = {
        'Authorization': "Bearer {0}".format(token),
        'Accept': 'text/event-stream'
    }

    url = api_endpoint

    http = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED',
        ca_certs=certifi.where())

    response = http.request('GET', url, headers=headers, preload_content=False)

    client = sseclient.SSEClient(response)

    tumbler = new_tumbler()

    for event in client.events(): # returns a generator
        event_type = event.event
        
        _LOGGER.debug("event: {0}".format(event_type))
        
        if event_type == 'open': # not always received here 
            _LOGGER.info("The event stream has been opened")
        elif event_type == 'put':
            _LOGGER.debug("The data has changed (or initial data sent)")

            data = json.loads(event.data)    

            tumbler.append(data["data"])        

            _LOGGER.info("Tumbler is now {0}".format(tumbler))

            if (lock_is_open(COMBINATION, list(tumbler)) or ALWAYS_UNLOCK):

                # zero out the tumbler
                tumbler = new_tumbler()

                _LOGGER.info("Lock unlocked!")

                adc = pyalarmdotcom.Alarmdotcom(ADC_USER,ADC_PASS,session,loop)
                await adc.async_login()
                await adc.async_alarm_disarm()

        elif event_type == 'keep-alive':
            _LOGGER.info("No data updates. Receiving an HTTP header to keep the connection open.")
        elif event_type == 'auth_revoked':
            _LOGGER.error("The API authorization has been revoked.")
            _LOGGER.error("revoked token: ", event.data)
        elif event_type == 'error':
            _LOGGER.error("Error occurred, such as connection closed.")
            _LOGGER.error("error message: ", event.data)
        else:
            _LOGGER.error("Unknown event, no handler for it.")

async def main(loop):
    level =  logging.DEBUG if os.environ.get('DEBUG',False) else logging.INFO
    logging.basicConfig(level=level, format='%(relativeCreated)6d %(threadName)s %(message)s')
    async with aiohttp.ClientSession() as session:
        await get_data_stream(session, loop, TOKEN, NEST_API_URL)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
