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
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    FranklinCoordinator,
    FranklinEntity,
    get_coordinator,
)
from .franklin_client import (
    AccountLockedException,
    DeviceTimeoutException,
    FranklinAPIError,
    GatewayOfflineException,
    InvalidCredentialsException,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SWITCHES): cv.ensure_list(vol.In([1, 2, 3])),
        vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(seconds=MIN_UPDATE_INTERVAL)),
        ),
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


class SmartCircuitSwitch(FranklinEntity, SwitchEntity):
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
        # NOTE: intentionally no _attr_unique_id — the existing switch entity
        # relies on HA's name-based entity_id, and adding a unique_id now would
        # re-register it and break saved automations/dashboards. See project
        # history for the "preserve existing entity_ids" constraint.

    @property
    def available(self) -> bool:
        """Only available once the coordinator has produced switch data."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.switch_state is not None
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None or data.switch_state is None:
            # No data yet / data missing -> HA shows ``unavailable`` rather
            # than a misleading "off".
            return None
        try:
            values = [data.switch_state[i] for i in self._switches]
        except IndexError:
            _LOGGER.debug(
                "FranklinWH switch_state has fewer entries than expected: %s",
                data.switch_state,
            )
            return None
        if all(values):
            return True
        if not any(values):
            return False
        # Mixed state across ganged switches -> unknown.
        return None

    async def _set_state(self, turn_on: bool) -> None:
        switches: list[bool | None] = [None, None, None]
        for i in self._switches:
            switches[i] = turn_on
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_smart_switch_state, tuple(switches)
            )
        except RuntimeError as err:
            # Raised by the client when merged switches 1+2 would be set to
            # different values; surface as a clean HA error rather than an
            # unhandled traceback in the UI.
            raise HomeAssistantError(str(err)) from err
        except (
            DeviceTimeoutException,
            GatewayOfflineException,
            AccountLockedException,
            InvalidCredentialsException,
            FranklinAPIError,
        ) as err:
            raise HomeAssistantError(
                f"Failed to change FranklinWH switch: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)
