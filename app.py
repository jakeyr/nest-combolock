import sseclient
import urllib3
import certifi
import json
import pprint
import collections
import os

from itertools import islice


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
WEBHOOK_DATA  = json.loads(os.environ.get('WEBHOOK_DATA'))
WEBHOOK_URL   = os.environ.get('WEBHOOK_URL')

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

def lock_is_open(combo, tumbler):
    final = tumbler[-1]
    rest  = tumbler[:-1]
    check = [x[1] for x in window(rest,3) if max(x) == x[1] or min(x) == x[1]] + [final]
    check = [x for x in window(check,len(combo))]
    print "check list is {0}".format(check)
    found = (tuple(combo) in check)
    print "found {0} in {1}?: ${2}".format(combo,check,found)
    return found

def get_data_stream(token, api_endpoint):
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

    tumbler = collections.deque(20*[0],20)

    for event in client.events(): # returns a generator
        event_type = event.event
        
        print "event: ", event_type
        
        if event_type == 'open': # not always received here 
            print "The event stream has been opened"
        elif event_type == 'put':
            print "The data has changed (or initial data sent)"

            data = json.loads(event.data)    

            tumbler.append(data["data"])        

            if (lock_is_open(COMBINATION, list(tumbler)) or ALWAYS_UNLOCK):
                print "Lock unlocked!"
                r = http.request('POST', WEBHOOK_URL, fields=WEBHOOK_DATA)
                print r.status
        
        elif event_type == 'keep-alive':
            print "No data updates. Receiving an HTTP header to keep the connection open."
        elif event_type == 'auth_revoked':
            print "The API authorization has been revoked."
            print "revoked token: ", event.data
        elif event_type == 'error':
            print "Error occurred, such as connection closed."
            print "error message: ", event.data
        else:
            print "Unknown event, no handler for it."

get_data_stream(TOKEN, NEST_API_URL)
