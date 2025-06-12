"""Platform for sensor and select integration."""
from __future__ import annotations
from threading import Lock
import time

from .franklin_client import (
    Client,
    TokenFetcher,
    DeviceTimeoutException,
    GatewayOfflineException,
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
        Sw1LoadSensor(cache),
        Sw1UseSensor(cache),
        Sw2LoadSensor(cache),
        Sw2UseSensor(cache),
        V2LUseSensor(cache),
        V2LExportSensor(cache),
        V2LImportSensor(cache),
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
        retries = 3
        for attempt in range(retries):
            try:
                self.data = self.update_func()
                return
            except (DeviceTimeoutException, GatewayOfflineException) as e:
                _LOGGER.warning(f"API fetch failed: {e}, attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(1)  # Short delay before retry
        _LOGGER.error("All fetch attempts failed, keeping last known data")

    def fetch(self):
        with self.mutex:
            now = time.monotonic()
            if now > self.last_fetched + UPDATE_INTERVAL:
                self.last_fetched = now
                self._fetch()
            if now > self.last_fetched + 300:  # 5 minutes
                _LOGGER.warning("Cached data is older than 5 minutes")
            return self.data

class FranklinBatterySensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH State of Charge"
    _attr_unique_id = "franklinwh_state_of_charge"
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
        if stats is not None:
            self._attr_native_value = stats.current.battery_soc
        else:
            _LOGGER.warning("No data available for FranklinWH State of Charge")

class HomeLoadSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Home Load"
    _attr_unique_id = "franklinwh_home_load"
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
        if stats is not None:
            self._attr_native_value = stats.current.home_load
        else:
            _LOGGER.warning("No data available for FranklinWH Home Load")

class BatteryUseSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Battery Use"
    _attr_unique_id = "franklinwh_battery_use"
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
        if stats is not None:
            self._attr_native_value = stats.current.battery_use * -1
        else:
            _LOGGER.warning("No data available for FranklinWH Battery Use")

class GridUseSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Grid Use"
    _attr_unique_id = "franklinwh_grid_use"
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
        if stats is not None:
            self._attr_native_value = stats.current.grid_use * -1
        else:
            _LOGGER.warning("No data available for FranklinWH Grid Use")

class SolarProductionSensor(SensorEntity):
    """Shows the current state of charge of the battery"""

    _attr_name = "FranklinWH Solar Production"
    _attr_unique_id = "franklinwh_solar_production"
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
        if stats is not None:
            self._attr_native_value = stats.current.solar_production
        else:
            _LOGGER.warning("No data available for FranklinWH Solar Production")

class BatteryChargeSensor(SensorEntity):
    """Shows the charging stats of the battery"""

    _attr_name = "FranklinWH Battery Charge"
    _attr_unique_id = "franklinwh_battery_charge"
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
        if stats is not None:
            self._attr_native_value = stats.totals.battery_charge
        else:
            _LOGGER.warning("No data available for FranklinWH Battery Charge")

class BatteryDischargeSensor(SensorEntity):
    """Shows the charging stats of the battery"""

    _attr_name = "FranklinWH Battery Discharge"
    _attr_unique_id = "franklinwh_battery_discharge"
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
        if stats is not None:
            self._attr_native_value = stats.totals.battery_discharge
        else:
            _LOGGER.warning("No data available for FranklinWH Battery Discharge")

class GridImportSensor(SensorEntity):
    """Shows the Grid Import"""

    _attr_name = "FranklinWH Grid Import"
    _attr_unique_id = "franklinwh_grid_import"
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
        if stats is not None:
            self._attr_native_value = stats.totals.grid_import
        else:
            _LOGGER.warning("No data available for FranklinWH Grid Import")

class GridExportSensor(SensorEntity):
    """Shows the Grid Export totals"""

    _attr_name = "FranklinWH Grid Export"
    _attr_unique_id = "franklinwh_grid_export"
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
        if stats is not None:
            self._attr_native_value = stats.totals.grid_export
        else:
            _LOGGER.warning("No data available for FranklinWH Grid Export")

class HomeUseSensor(SensorEntity):
    """Shows the Home Use daily totals"""

    _attr_name = "FranklinWH Home Daily Use"
    _attr_unique_id = "franklinwh_home_daily_use"
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
        if stats is not None:
            self._attr_native_value = stats.totals.home_use
        else:
            _LOGGER.warning("No data available for FranklinWH Home Daily Use")

class GeneratorDailyUseSensor(SensorEntity):
    """Shows the Generator Total daily use"""

    _attr_name = "FranklinWH Generator Daily Use"
    _attr_unique_id = "franklinwh_generator_daily_use"
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
        if stats is not None:
            self._attr_native_value = stats.totals.generator
        else:
            _LOGGER.warning("No data available for FranklinWH Generator Daily Use")

class SolarUseSensor(SensorEntity):
    """Shows the charging stats of the battery"""

    _attr_name = "FranklinWH Solar Daily Use"
    _attr_unique_id = "franklinwh_solar_daily_use"
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
        if stats is not None:
            self._attr_native_value = stats.totals.solar
        else:
            _LOGGER.warning("No data available for FranklinWH Solar Daily Use")

class GeneratorUseSensor(SensorEntity):
    """Shows the current power output of the generator"""

    _attr_name = "FranklinWH Generator Use"
    _attr_unique_id = "franklinwh_generator_use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.current.generator_production
        else:
            _LOGGER.warning("No data available for FranklinWH Generator Use")

class Sw1LoadSensor(SensorEntity):
    """Shows the current power use by switch 1"""

    _attr_name = "FranklinWH Switch 1 Load"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.current.switch_1_load

class Sw1UseSensor(SensorEntity):
    """Shows the lifetime energy usage by switch 1"""

    _attr_name = "FranklinWH Switch 1 Lifetime Use"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.totals.switch_1_use


class Sw2LoadSensor(SensorEntity):
    """Shows the current power use by switch 2"""

    _attr_name = "FranklinWH Switch 2 Load"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.current.switch_2_load

class Sw2UseSensor(SensorEntity):
    """Shows the lifetime energy usage by switch 1"""

    _attr_name = "FranklinWH Switch 2 Lifetime Use"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.totals.switch_2_use


class V2LUseSensor(SensorEntity):
    """Shows the current power use by the car switch"""

    _attr_name = "FranklinWH V2L Use"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.current.v2l_use

class V2LExportSensor(SensorEntity):
    """Shows the lifetime energy exported to the car switch"""

    _attr_name = "FranklinWH V2L Export"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.totals.v2l_export

class V2LImportSensor(SensorEntity):
    """Shows the lifetime energy exported to the car switch"""

    _attr_name = "FranklinWH V2L Import"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, cache):
        self._cache = cache

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        stats = self._cache.fetch()
        if stats is not None:
            self._attr_native_value = stats.totals.v2l_import
