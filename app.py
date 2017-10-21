import sseclient
import urllib3
import certifi
import json
import pprint
import collections
import os

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

COMBINATION   = collections.deque(json.loads(os.environ.get("COMBINATION")))
ALWAYS_UNLOCK = os.environ.get('ALWAYS_UNLOCK',False)
WEBHOOK_DATA  = json.loads(os.environ.get('WEBHOOK_DATA'))
WEBHOOK_URL   = os.environ.get('WEBHOOK_URL')

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

    tumbler = collections.deque(len(COMBINATION)*[0],len(COMBINATION))

    for event in client.events(): # returns a generator
        event_type = event.event
        print "event: ", event_type
        if event_type == 'open': # not always received here 
            print "The event stream has been opened"
        elif event_type == 'put':
            print "The data has changed (or initial data sent)"
            data = json.loads(event.data)
            tumbler.append(data["data"]) 
            print "tumbler is now {0}".format(tumbler)
            if (tumbler == COMBINATION or ALWAYS_UNLOCK):
                print "Lock unlocked!"
                http.request('POST', WEBHOOK_URL, fields=WEBHOOK_DATA)   
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
