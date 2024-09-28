"""Platform for sensor and select integration."""
from __future__ import annotations
from threading import Lock
import time

from .franklin_client import (
    Client,
    TokenFetcher,
    Mode,
    MODE_TIME_OF_USE,
    MODE_SELF_CONSUMPTION,
    MODE_EMERGENCY_BACKUP,
    MODE_OPTIONS
)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.select import SelectEntity
from homeassistant.const import (
        UnitOfPower,
        UnitOfEnergy,
        PERCENTAGE,
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_ID,
        )

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_ID): cv.string,
            }
        )

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor and select platform."""
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    gateway: str = config[CONF_ID]

    fetcher = TokenFetcher(username, password)
    client = Client(fetcher, gateway)
    cache = CachingClient(client.get_stats)

    _LOGGER.debug('setting up franklin platform')

    entities = [
        FranklinBatterySensor(cache),
        HomeLoadSensor(cache),
        BatteryUseSensor(cache),
        GridUseSensor(cache),
        SolarProductionSensor(cache),
        BatteryChargeSensor(cache),
        BatteryDischargeSensor(cache),
        GeneratorUseSensor(cache),
        GridExportSensor(cache),
        GridImportSensor(cache),
        HomeUseSensor(cache),
        GeneratorDailyUseSensor(cache),
        SolarUseSensor(cache),
        # Pass hass to the select entity
        FranklinModeSelect(hass, client)
    ]

    add_entities(entities)


UPDATE_INTERVAL = 60
class CachingClient(object):
    def __init__(self, update_func):
        self.mutex = Lock()
        self.update_func = update_func
        self.last_fetched = 0
        self.data = None

    def _fetch(self):
        self.data = self.update_func()

    def fetch(self):
        with self.mutex:
            now = time.monotonic()
            if now > self.last_fetched + UPDATE_INTERVAL:
                self.last_fetched = now
                self._fetch()
            return self.data
# TODO(richo) Figure out how to have a singleton cache for the franklin data


class FranklinModeSelect(SelectEntity):
    """Representation of a select entity to change the FranklinWH operating mode."""

    def __init__(self, hass: HomeAssistant, client):
        self._client = client
        self._attr_options = MODE_OPTIONS
        self._attr_name = "FranklinWH Operating Mode"
        self._attr_current_option = None
        self.hass = hass  # Store hass instance for async calls

    @property
    def name(self):
        """Return the name of the entity."""
        return self._attr_name

    @property
    def options(self):
        """Return the list of available options."""
        return self._attr_options

    @property
    def current_option(self):
        """Return the current selected option."""
        return self._attr_current_option

    async def async_update(self):
        """Fetch the current mode from the client asynchronously."""
        try:
            mode_data = await self.hass.async_add_executor_job(self._client.get_mode)
            mode, soc = mode_data
            self._attr_current_option = mode
        except Exception as e:
            _LOGGER.error(f"Error updating FranklinWH operating mode: {e}")

    async def async_select_option(self, option):
        """Change the operating mode to the selected option asynchronously."""
        if option not in self._attr_options:
            _LOGGER.error(f"Invalid option selected: {option}")
            return
        try:
            # Create the appropriate Mode object
            if option == MODE_TIME_OF_USE:
                mode_obj = Mode.time_of_use()
            elif option == MODE_SELF_CONSUMPTION:
                mode_obj = Mode.self_consumption()
            elif option == MODE_EMERGENCY_BACKUP:
                mode_obj = Mode.emergency_backup()
            else:
                _LOGGER.error(f"Invalid mode selected: {option}")
                return

            # Set the mode via the client in an executor
            await self.hass.async_add_executor_job(self._client.set_mode, mode_obj)
            # Update the current option
            self._attr_current_option = option
            # Optionally, force an update to refresh the state
            await self.async_update()
        except Exception as e:
            _LOGGER.error(f"Error setting FranklinWH operating mode: {e}")


class FranklinBatterySensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH State of Charge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.current.battery_soc

class HomeLoadSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Home Load"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.current.home_load

class BatteryUseSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Battery Use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.current.battery_use * -1

class GridUseSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Grid Use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.current.grid_use * -1

class SolarProductionSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Solar Production"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.current.solar_production

class BatteryChargeSensor(SensorEntity):
    """Shows the charging stats of the battery"""

    _attr_name = "FranklinWH Battery Charge"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.battery_charge

class BatteryDischargeSensor(SensorEntity):
    """Shows the charging stats of the battery"""

    _attr_name = "FranklinWH Battery Discharge"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.battery_discharge

class GridImportSensor(SensorEntity):
    """Shows the Grid Import"""

    _attr_name = "FranklinWH Grid Import"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.grid_import

class GridExportSensor(SensorEntity):
    """Shows the Grid Export totals"""

    _attr_name = "FranklinWH Grid Export"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.grid_export

class HomeUseSensor(SensorEntity):
    """Shows the Home Use daily totals"""

    _attr_name = "FranklinWH Home Daily Use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.home_use

class GeneratorDailyUseSensor(SensorEntity):
    """Shows the Generator Total daily use"""

    _attr_name = "FranklinWH Generator Daily Use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.generator

class SolarUseSensor(SensorEntity):
    """Shows the charging stats of the battery"""

    _attr_name = "FranklinWH Solar Daily Use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        self._attr_native_value = stats.totals.solar

class GeneratorUseSensor(SensorEntity):
    """Shows the current power output of the generator"""

    _attr_name = "FranklinWH Generator Use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        stats = self._cache.fetch()
        self._attr_native_value = stats.current.generator_production
