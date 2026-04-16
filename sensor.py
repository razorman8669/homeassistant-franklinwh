"""Sensor platform for FranklinWH."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    FranklinEntity,
    get_coordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(seconds=MIN_UPDATE_INTERVAL)),
        ),
        vol.Optional("tolerate_stale_data", default=False): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the FranklinWH sensor platform."""
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    gateway: str = config[CONF_ID]
    update_interval: timedelta = config["update_interval"]
    tolerate_stale_data: bool = config["tolerate_stale_data"]

    coordinator = await get_coordinator(
        hass, username, password, gateway,
        update_interval=update_interval,
        tolerate_stale_data=tolerate_stale_data,
    )

    _LOGGER.debug("Setting up FranklinWH sensor platform")

    async_add_entities([
        FranklinBatterySensor(coordinator),
        HomeLoadSensor(coordinator),
        BatteryUseSensor(coordinator),
        GridUseSensor(coordinator),
        SolarProductionSensor(coordinator),
        BatteryChargeSensor(coordinator),
        BatteryDischargeSensor(coordinator),
        GeneratorUseSensor(coordinator),
        GridExportSensor(coordinator),
        GridImportSensor(coordinator),
        HomeUseSensor(coordinator),
        GeneratorDailyUseSensor(coordinator),
        SolarUseSensor(coordinator),
        Sw1LoadSensor(coordinator),
        Sw1UseSensor(coordinator),
        Sw2LoadSensor(coordinator),
        Sw2UseSensor(coordinator),
        V2LUseSensor(coordinator),
        V2LExportSensor(coordinator),
        V2LImportSensor(coordinator),
    ])


class FranklinBatterySensor(FranklinEntity, SensorEntity):
    """Battery state of charge."""

    _attr_name = "FranklinWH State of Charge"
    _attr_unique_id = "franklinwh_state_of_charge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.battery_soc
        return None


class HomeLoadSensor(FranklinEntity, SensorEntity):
    """Instantaneous home power draw."""

    _attr_name = "FranklinWH Home Load"
    _attr_unique_id = "franklinwh_home_load"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.home_load
        return None


class BatteryUseSensor(FranklinEntity, SensorEntity):
    """Battery charge/discharge rate (sign-inverted for dashboard convention)."""

    _attr_name = "FranklinWH Battery Use"
    _attr_unique_id = "franklinwh_battery_use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.battery_use * -1
        return None


class GridUseSensor(FranklinEntity, SensorEntity):
    """Grid power usage (sign-inverted for dashboard convention)."""

    _attr_name = "FranklinWH Grid Use"
    _attr_unique_id = "franklinwh_grid_use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.grid_use * -1
        return None


class SolarProductionSensor(FranklinEntity, SensorEntity):
    """Instantaneous solar production."""

    _attr_name = "FranklinWH Solar Production"
    _attr_unique_id = "franklinwh_solar_production"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.solar_production
        return None


class BatteryChargeSensor(FranklinEntity, SensorEntity):
    """Total energy charged to battery today."""

    _attr_name = "FranklinWH Battery Charge"
    _attr_unique_id = "franklinwh_battery_charge"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.battery_charge
        return None


class BatteryDischargeSensor(FranklinEntity, SensorEntity):
    """Total energy discharged from battery today."""

    _attr_name = "FranklinWH Battery Discharge"
    _attr_unique_id = "franklinwh_battery_discharge"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.battery_discharge
        return None


class GridImportSensor(FranklinEntity, SensorEntity):
    """Total energy imported from grid today."""

    _attr_name = "FranklinWH Grid Import"
    _attr_unique_id = "franklinwh_grid_import"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.grid_import
        return None


class GridExportSensor(FranklinEntity, SensorEntity):
    """Total energy exported to grid today."""

    _attr_name = "FranklinWH Grid Export"
    _attr_unique_id = "franklinwh_grid_export"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.grid_export
        return None


class HomeUseSensor(FranklinEntity, SensorEntity):
    """Total home energy consumption today."""

    _attr_name = "FranklinWH Home Daily Use"
    _attr_unique_id = "franklinwh_home_daily_use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.home_use
        return None


class GeneratorDailyUseSensor(FranklinEntity, SensorEntity):
    """Total generator energy today."""

    _attr_name = "FranklinWH Generator Daily Use"
    _attr_unique_id = "franklinwh_generator_daily_use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.generator
        return None


class SolarUseSensor(FranklinEntity, SensorEntity):
    """Total solar energy produced today."""

    _attr_name = "FranklinWH Solar Daily Use"
    _attr_unique_id = "franklinwh_solar_daily_use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.solar
        return None


class GeneratorUseSensor(FranklinEntity, SensorEntity):
    """Instantaneous generator power output."""

    _attr_name = "FranklinWH Generator Use"
    _attr_unique_id = "franklinwh_generator_use"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.generator_production
        return None


class Sw1LoadSensor(FranklinEntity, SensorEntity):
    """Instantaneous power on switch 1."""

    _attr_name = "FranklinWH Switch 1 Load"
    _attr_unique_id = "franklinwh_switch_1_load"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.switch_1_load
        return None


class Sw1UseSensor(FranklinEntity, SensorEntity):
    """Lifetime energy usage by switch 1."""

    _attr_name = "FranklinWH Switch 1 Lifetime Use"
    _attr_unique_id = "franklinwh_switch_1_lifetime_use"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.switch_1_use
        return None


class Sw2LoadSensor(FranklinEntity, SensorEntity):
    """Instantaneous power on switch 2."""

    _attr_name = "FranklinWH Switch 2 Load"
    _attr_unique_id = "franklinwh_switch_2_load"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.switch_2_load
        return None


class Sw2UseSensor(FranklinEntity, SensorEntity):
    """Lifetime energy usage by switch 2."""

    _attr_name = "FranklinWH Switch 2 Lifetime Use"
    _attr_unique_id = "franklinwh_switch_2_lifetime_use"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.switch_2_use
        return None


class V2LUseSensor(FranklinEntity, SensorEntity):
    """Instantaneous V2L power."""

    _attr_name = "FranklinWH V2L Use"
    _attr_unique_id = "franklinwh_v2l_use"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.current.v2l_use
        return None


class V2LExportSensor(FranklinEntity, SensorEntity):
    """Total energy delivered to V2L."""

    _attr_name = "FranklinWH V2L Export"
    _attr_unique_id = "franklinwh_v2l_export"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.v2l_export
        return None


class V2LImportSensor(FranklinEntity, SensorEntity):
    """Total energy drawn from V2L."""

    _attr_name = "FranklinWH V2L Import"
    _attr_unique_id = "franklinwh_v2l_import"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if self.coordinator.data and self.coordinator.data.stats:
            return self.coordinator.data.stats.totals.v2l_import
        return None
