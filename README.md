# nest-combolock
Turns my Nest thermostat into a combination lock.

I built this so that I can disable my alarm system from the top of the stairs using my thermostat. Read more about why I would do something so ridiculous [here](https://medium.com/@rowborg/using-my-nest-thermostat-as-a-combination-lock-d536e615cbbf).

This is a python3 app that is easy to run or to deploy to Heroku. It's hard coded to integrate with Alarm.com using [this package](https://github.com/Xorso/pyalarmdotcom) but you can make it do whatever you want when the combination is entered.

All you need to do is set the following environment variables:

```
ALARMDOTCOM_USERNAME: Your username for Alarm.com
ALARMDOTCOM_PASSWORD: Your password for Alarm.com
COMBINATION:          [X,X,X] # your combination, can be as short or long as you like
NEST_TOKEN:           Your OAuth token for the Nest API
THERMOSTAT_ID:        Your nest thermostat ID.
```

Enjoy!
