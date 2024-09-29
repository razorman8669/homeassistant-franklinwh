"""Platform for the select integration for FranklinWH."""
from __future__ import annotations
from homeassistant.components.select import (
    SelectEntity,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
)
from homeassistant.core import HomeAssistant

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from time import time

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .franklin_client import (
    Client,
    TokenFetcher,
    Mode,
    MODE_TIME_OF_USE,
    MODE_SELF_CONSUMPTION,
    MODE_EMERGENCY_BACKUP,
    MODE_OPTIONS
)

import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.const import (
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_ID,
        )

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
    """Set up the FranklinWH select platform."""
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    gateway: str = config[CONF_ID]

    fetcher = TokenFetcher(username, password)
    client = Client(fetcher, gateway)

    _LOGGER.debug("Setting up FranklinWH select platform")

    # Add select entity to Home Assistant
    add_entities([FranklinModeSelect(client)])

class FranklinModeSelect(SelectEntity):
    """Representation of a select entity to change the FranklinWH operating mode."""

    def __init__(self, client):
        self._client = client
        self._attr_options = MODE_OPTIONS
        self._attr_name = "FranklinWH Operating Mode Select"
        self._attr_unique_id = (
            f"franklin_operating_mode_select"
        )

        self._attr_current_option = None
        self._last_fetched = 0  # Timestamp of the last fetch
        self._cache_duration = 60  # Cache data for 60 seconds
        self._cached_mode = None  # Cache the last mode
        _LOGGER.debug("Initializing FranklinWH Mode Select Entity")

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

    def update(self):
        """Fetch the current mode from the client, respecting the cache duration."""
        current_time = time()
        if current_time - self._last_fetched < self._cache_duration:
            # Use cached data if last fetch was within 60 seconds
            _LOGGER.debug("Using cached mode data.")
            self._attr_current_option = self._cached_mode
            return

        # Otherwise, fetch the data from the API
        try:
            mode, soc = self._client.get_mode()
            self._attr_current_option = mode
            self._cached_mode = mode  # Cache the mode data
            self._last_fetched = current_time  # Update the last fetched timestamp
            _LOGGER.debug(f"Fetched new mode data: {mode}")
        except Exception as e:
            _LOGGER.error(f"Error updating FranklinWH operating mode: {e}")

    def select_option(self, option):
        """Change the operating mode to the selected option."""
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
            # Set the mode via the client
            self._client.set_mode(mode_obj)
            # Update the current option
            self._attr_current_option = option
            self._cached_mode = option  # Cache the newly set mode
            self._last_fetched = time()  # Reset the cache timer
        except Exception as e:
            _LOGGER.error(f"Error setting FranklinWH operating mode: {e}")
 # type: ignore
