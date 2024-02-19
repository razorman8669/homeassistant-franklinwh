"""Platform for sensor integration."""
from __future__ import annotations

import franklinwh

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
        UnitOfPower,
        UnitOfEnergy,
        PERCENTAGE,
        CONF_ACCESS_TOKEN,
        CONF_ID,
        )

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Required(CONF_ID): cv.string,
            }
        )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    access_token: str = config[CONF_ACCESS_TOKEN]
    gateway: str = config[CONF_ID]

    add_entities([
        FranklinBatterySensor(access_token, gateway),
        HomeLoadSensor(access_token, gateway)
        ])


# TODO(richo) Figure out how to have a singleton cache for the franklin data

class FranklinBatterySensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "state of charge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, token, gateway):
        self._client = franklinwh.Client(token, gateway)

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._client.get_stats()
        self._attr_native_value = stats.current.battery_soc

class HomeLoadSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "Home Load"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, token, gateway):
        self._client = franklinwh.Client(token, gateway)

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._client.get_stats()
        self._attr_native_value = stats.current.home_load
