"""DataUpdateCoordinator for FranklinWH integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .franklin_client import (
    AccountLockedException,
    Client,
    DeviceTimeoutException,
    GatewayOfflineException,
    InvalidCredentialsException,
    Stats,
    TokenFetcher,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "franklin_wh"
DEFAULT_UPDATE_INTERVAL = 60
MAX_RETRIES = 3
RETRY_DELAY = 2


@dataclass
class FranklinData:
    """Bundled result from a single poll cycle."""

    stats: Stats | None
    switch_state: tuple[bool, ...] | None
    mode: str | None
    mode_soc: int | None


class FranklinCoordinator(DataUpdateCoordinator[FranklinData]):
    """Single coordinator that polls one FranklinWH gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
        update_interval: timedelta,
        tolerate_stale_data: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            always_update=False,
        )
        self.client = client
        self.tolerate_stale_data = tolerate_stale_data
        self._last_good_data: FranklinData | None = None

    async def _async_update_data(self) -> FranklinData:
        try:
            data = await self._poll_with_retries()
        except (
            AccountLockedException,
            InvalidCredentialsException,
        ) as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except (
            DeviceTimeoutException,
            GatewayOfflineException,
        ) as err:
            if self.tolerate_stale_data and self._last_good_data is not None:
                _LOGGER.warning(
                    "FranklinWH API unavailable (%s); returning stale data", err
                )
                return self._last_good_data
            raise UpdateFailed(
                f"FranklinWH API unavailable after {MAX_RETRIES} retries: {err}"
            ) from err
        except Exception as err:
            if self.tolerate_stale_data and self._last_good_data is not None:
                _LOGGER.warning(
                    "Unexpected error polling FranklinWH (%s); returning stale data",
                    err,
                )
                return self._last_good_data
            raise UpdateFailed(f"Error polling FranklinWH: {err}") from err

        self._last_good_data = data
        return data

    async def _poll_with_retries(self) -> FranklinData:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                _LOGGER.warning(
                    "FranklinWH poll retry %d/%d", attempt + 1, MAX_RETRIES
                )
                await asyncio.sleep(RETRY_DELAY)
            try:
                return await self.hass.async_add_executor_job(
                    self.client.poll_bundle
                )
            except (DeviceTimeoutException, GatewayOfflineException) as err:
                _LOGGER.warning("FranklinWH poll attempt %d failed: %s", attempt + 1, err)
                last_exc = err
        raise last_exc  # type: ignore[misc]


def _coordinator_key(username: str, gateway: str) -> str:
    return f"{username}_{gateway}"


async def get_coordinator(
    hass: HomeAssistant,
    username: str,
    password: str,
    gateway: str,
    update_interval: timedelta = timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
    tolerate_stale_data: bool = False,
) -> FranklinCoordinator:
    """Get or create a shared FranklinCoordinator for a gateway.

    The first platform that calls this determines the update_interval and
    tolerate_stale_data setting for the coordinator's lifetime.
    """
    hass.data.setdefault(DOMAIN, {})
    key = _coordinator_key(username, gateway)

    if key in hass.data[DOMAIN]:
        return hass.data[DOMAIN][key]

    fetcher = TokenFetcher(username, password)
    client = await hass.async_add_executor_job(Client, fetcher, gateway)

    coordinator = FranklinCoordinator(
        hass,
        client,
        update_interval=update_interval,
        tolerate_stale_data=tolerate_stale_data,
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][key] = coordinator
    return coordinator
