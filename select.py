"""Select platform for FranklinWH operating mode."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.select import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SelectEntity,
)
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    FranklinCoordinator,
    get_coordinator,
)
from .franklin_client import (
    MODE_EMERGENCY_BACKUP,
    MODE_OPTIONS,
    MODE_SELF_CONSUMPTION,
    MODE_TIME_OF_USE,
    AccountLockedException,
    DeviceTimeoutException,
    FranklinAPIError,
    GatewayOfflineException,
    InvalidCredentialsException,
    Mode,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): cv.time_period,
    }
)

MODE_FACTORY = {
    MODE_TIME_OF_USE: Mode.time_of_use,
    MODE_SELF_CONSUMPTION: Mode.self_consumption,
    MODE_EMERGENCY_BACKUP: Mode.emergency_backup,
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the FranklinWH select platform."""
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    gateway: str = config[CONF_ID]
    update_interval: timedelta = config["update_interval"]

    coordinator = await get_coordinator(
        hass, username, password, gateway,
        update_interval=update_interval,
    )

    _LOGGER.debug("Setting up FranklinWH select platform")
    async_add_entities([FranklinModeSelect(coordinator)])


class FranklinModeSelect(CoordinatorEntity[FranklinCoordinator], SelectEntity):
    """Select entity for FranklinWH operating mode."""

    _attr_options = MODE_OPTIONS
    _attr_name = "FranklinWH Operating Mode Select"
    _attr_unique_id = "franklin_operating_mode_select"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data and self.coordinator.data.mode:
            return self.coordinator.data.mode
        return None

    async def async_select_option(self, option: str) -> None:
        if option not in MODE_FACTORY:
            raise HomeAssistantError(f"Invalid FranklinWH mode: {option}")

        mode_obj = MODE_FACTORY[option]()
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_mode, mode_obj
            )
        except (
            DeviceTimeoutException,
            GatewayOfflineException,
            AccountLockedException,
            InvalidCredentialsException,
            FranklinAPIError,
        ) as err:
            raise HomeAssistantError(f"Failed to set FranklinWH mode: {err}") from err

        await self.coordinator.async_request_refresh()
