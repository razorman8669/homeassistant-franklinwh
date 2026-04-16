"""DataUpdateCoordinator for FranklinWH integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .franklin_client import (
    AccountLockedException,
    Client,
    DeviceTimeoutException,
    FranklinData,
    GatewayOfflineException,
    InvalidCredentialsException,
    TokenFetcher,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "franklin_wh"
DEFAULT_UPDATE_INTERVAL = 60
MIN_UPDATE_INTERVAL = 15
# Franklin cloud often returns HTTP 200 with code 102 ("device timed out") when
# the gateway is slow; poll_bundle runs several MQTT round-trips per cycle.
MAX_RETRIES = 4
# Exponential backoff ceiling between attempts (seconds).
_BACKOFF_CAP = 30


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

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry entry grouping all FranklinWH entities together."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.gateway)},
            name=f"FranklinWH ({self.client.gateway})",
            manufacturer="FranklinWH",
            model="aPower Home Power Solution",
            configuration_url="https://energy.franklinwh.com/",
        )

    async def _async_update_data(self) -> FranklinData:
        try:
            data = await self._poll_with_retries()
        except (
            AccountLockedException,
            InvalidCredentialsException,
        ) as err:
            # Auth errors are terminal for this config; do not keep stale data.
            raise UpdateFailed(f"Authentication error: {err}") from err
        except (
            DeviceTimeoutException,
            GatewayOfflineException,
        ) as err:
            if self.tolerate_stale_data and self._last_good_data is not None:
                _LOGGER.info(
                    "FranklinWH API unavailable (%s); keeping last successful data",
                    err,
                )
                return self._last_good_data
            raise UpdateFailed(
                f"FranklinWH API unavailable after {MAX_RETRIES} attempts ({err}). "
                "If this is frequent, set tolerate_stale_data: true on the sensor platform."
            ) from err
        except Exception as err:
            if self.tolerate_stale_data and self._last_good_data is not None:
                # Full traceback at debug so real bugs aren't silently swallowed
                # when tolerate_stale_data hides them from users.
                _LOGGER.debug(
                    "Unexpected error polling FranklinWH; keeping last successful data",
                    exc_info=True,
                )
                _LOGGER.info(
                    "Unexpected error polling FranklinWH (%s); keeping last successful data",
                    err,
                )
                return self._last_good_data
            raise UpdateFailed(f"Error polling FranklinWH: {err}") from err

        self._last_good_data = data
        return data

    async def _poll_with_retries(self) -> FranklinData:
        """Poll the API with bounded retries.

        Bounded both by ``MAX_RETRIES`` and by a soft time budget derived from
        the configured ``update_interval``, so a pathological slow-gateway cycle
        can't run for several minutes and trample the next scheduled update.
        """
        loop = asyncio.get_running_loop()
        interval_s = (
            self.update_interval.total_seconds()
            if self.update_interval is not None
            else DEFAULT_UPDATE_INTERVAL
        )
        # Reserve ~90% of the interval for this cycle; floor of 30s so very
        # short intervals still have room for a single retry.
        deadline = loop.time() + max(interval_s * 0.9, 30)

        last_exc: DeviceTimeoutException | GatewayOfflineException = (
            DeviceTimeoutException("FranklinWH poll never ran")
        )

        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    _LOGGER.debug(
                        "FranklinWH retry budget exhausted after %d attempt(s)",
                        attempt,
                    )
                    break
                delay = min(_BACKOFF_CAP, 2**attempt, max(1, int(remaining)))
                _LOGGER.debug(
                    "FranklinWH poll retry %d/%d after %ds backoff",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)

            try:
                return await self.hass.async_add_executor_job(
                    self.client.poll_bundle
                )
            except (DeviceTimeoutException, GatewayOfflineException) as err:
                last_exc = err
                # Per-attempt detail is debug-only; HA logs UpdateFailed at
                # error when all attempts are exhausted.
                _LOGGER.debug(
                    "FranklinWH poll attempt %d/%d failed: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    err,
                )

        raise last_exc


class FranklinEntity(CoordinatorEntity[FranklinCoordinator]):
    """Base coordinator-backed entity with device registry wiring.

    Using a small base class avoids repeating ``_attr_device_info`` setup
    across every sensor/switch/select and keeps grouping consistent.
    """

    def __init__(self, coordinator: FranklinCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info


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

    The first platform to call this fixes the update_interval and
    tolerate_stale_data settings for the coordinator's lifetime. If a later
    platform requests different values, we log a warning so the user knows
    their second ``configuration.yaml`` stanza is effectively ignored.
    """
    hass.data.setdefault(DOMAIN, {})
    key = _coordinator_key(username, gateway)

    existing = hass.data[DOMAIN].get(key)
    if existing is not None:
        if existing.update_interval != update_interval:
            _LOGGER.warning(
                "FranklinWH: ignoring update_interval=%s for gateway %s; "
                "an earlier platform already fixed it at %s",
                update_interval,
                gateway,
                existing.update_interval,
            )
        if existing.tolerate_stale_data != tolerate_stale_data:
            _LOGGER.warning(
                "FranklinWH: ignoring tolerate_stale_data=%s for gateway %s; "
                "an earlier platform already fixed it at %s",
                tolerate_stale_data,
                gateway,
                existing.tolerate_stale_data,
            )
        return existing

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
