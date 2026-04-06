"""Switch platform for FranklinWH smart circuits."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SWITCHES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    FranklinCoordinator,
    get_coordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SWITCHES): cv.ensure_list(vol.In([1, 2, 3])),
        vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): cv.time_period,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the FranklinWH switch platform."""
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    gateway: str = config[CONF_ID]
    name: str = config[CONF_NAME]
    update_interval: timedelta = config["update_interval"]

    switches: list[int] = [x - 1 for x in config[CONF_SWITCHES]]

    coordinator = await get_coordinator(
        hass, username, password, gateway,
        update_interval=update_interval,
    )

    async_add_entities([
        SmartCircuitSwitch(coordinator, name, switches),
    ])


class SmartCircuitSwitch(CoordinatorEntity[FranklinCoordinator], SwitchEntity):
    """Representation of a FranklinWH smart circuit switch."""

    def __init__(
        self,
        coordinator: FranklinCoordinator,
        name: str,
        switches: list[int],
    ) -> None:
        super().__init__(coordinator)
        self._switches = switches
        self._attr_name = f"FranklinWH {name}"
        self._is_on: bool | None = False

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data and self.coordinator.data.switch_state:
            values = [self.coordinator.data.switch_state[i] for i in self._switches]
            if all(values):
                return True
            if not any(values):
                return False
            return None
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        switches = [None, None, None]
        for i in self._switches:
            switches[i] = True
        await self.hass.async_add_executor_job(
            self.coordinator.client.set_smart_switch_state, switches
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        switches = [None, None, None]
        for i in self._switches:
            switches[i] = False
        await self.hass.async_add_executor_job(
            self.coordinator.client.set_smart_switch_state, switches
        )
        await self.coordinator.async_request_refresh()
