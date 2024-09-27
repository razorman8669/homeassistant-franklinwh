# Franklin WH

This implements a collection of sensors, and a switch implementation for the Franklin WH home energy system.

# Installation

Using Studio Code Server integration in HA, open the terminal and run:
```
git clone https://github.com/razorman8669/homeassistant-franklinwh config/custom_components/franklin_wh
```

Then Restart HA.

# Configuration

To add the basic sensors to your home assitant add the following to your `configuration.yaml` file:

It is very strongly recommended to put your password in secrets.yaml to avoid accidentally revealing it.

Example sensors configuration.yaml entry.

```yaml
sensor:
  - platform: franklin_wh
    username: "email@domain.com"
    password: !secret franklinwh_password
    id: 1005xxxxxxxxxxx
```

And to add switches, see below as an example, The switches in the example is the smart circuits that should be
bound to that virtual switch.


```yaml
switch:
  - platform: franklin_wh
    username: "email@domain.com"
    password: !secret franklinwh_password
    id: 1005xxxxxxxxxxx
    switches: [3]
    name: "FWH switch1"
  - platform: franklin_wh
    username: "email@domain.com"
    password: !secret franklinwh_password
    id: 1005xxxxxxxxxxx
    switches: [1, 2]
    name: "FWH switch2"
```
