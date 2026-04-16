"""
FranklinWH API client.
Based on https://github.com/richo/franklinwh-python
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import typing
import zlib
from dataclasses import dataclass

import requests

_LOGGER = logging.getLogger(__name__)

# Connect, read — sendMqtt can sit behind a slow gateway; 102 timeouts are often
# application-level, but a longer read avoids aborting healthy slow responses.
REQUEST_TIMEOUT = (15, 75)


def to_hex(inp):
    return f"{inp:08X}"


@dataclass
class Current:
    solar_production: float
    generator_production: float
    battery_use: float
    grid_use: float
    home_load: float
    battery_soc: float
    switch_1_load: float
    switch_2_load: float
    v2l_use: float


@dataclass
class Totals:
    battery_charge: float
    battery_discharge: float
    grid_import: float
    grid_export: float
    solar: float
    generator: float
    home_use: float
    switch_1_use: float
    switch_2_use: float
    v2l_export: float
    v2l_import: float


@dataclass
class Stats:
    current: Current
    totals: Totals


@dataclass
class FranklinData:
    """Bundled result from a single coordinator poll cycle.

    Lives in the client (not the coordinator) so that the client can both
    produce and type it without creating a circular import with the HA-side
    coordinator module.
    """

    stats: "Stats | None"
    switch_state: "tuple[bool, ...] | None"
    mode: str | None
    mode_soc: int | None


MODE_TIME_OF_USE = "time_of_use"
MODE_SELF_CONSUMPTION = "self_consumption"
MODE_EMERGENCY_BACKUP = "emergency_backup"

MODE_OPTIONS = [
    MODE_TIME_OF_USE,
    MODE_SELF_CONSUMPTION,
    MODE_EMERGENCY_BACKUP,
]

DEFAULT_URL_BASE = "https://energy.franklinwh.com/"

MODE_MAP = {
    9322: MODE_TIME_OF_USE,
    9323: MODE_SELF_CONSUMPTION,
    9324: MODE_EMERGENCY_BACKUP,
    105249: MODE_TIME_OF_USE,
    122324: MODE_SELF_CONSUMPTION,
    55842: MODE_EMERGENCY_BACKUP,
}


class Mode:
    @staticmethod
    def time_of_use(soc=15):
        mode = Mode(soc)
        mode.currendId = 105249
        mode.workMode = 1
        return mode

    @staticmethod
    def emergency_backup(soc=100):
        mode = Mode(soc)
        mode.currendId = 55842
        mode.workMode = 3
        return mode

    @staticmethod
    def self_consumption(soc=20):
        mode = Mode(soc)
        mode.currendId = 122324
        mode.workMode = 2
        return mode

    def __init__(self, soc):
        self.soc = soc
        self.currendId = None
        self.workMode = None

    def payload(self, gateway):
        return {
            "currendId": str(self.currendId),
            "gatewayId": gateway,
            "lang": "EN_US",
            "oldIndex": "1",  # Who knows if this matters
            "soc": str(self.soc),
            "stromEn": "0",
            "workMode": str(self.workMode),
        }


class TokenExpiredException(Exception):
    """Raised when the token has expired."""


class AccountLockedException(Exception):
    pass


class InvalidCredentialsException(Exception):
    pass


class DeviceTimeoutException(Exception):
    pass


class GatewayOfflineException(Exception):
    pass


class FranklinAPIError(Exception):
    """Raised for unexpected API response codes or malformed responses."""


class TokenFetcher:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def get_token(self):
        return TokenFetcher.login(self.username, self.password)

    @staticmethod
    def login(username: str, password: str):
        url = DEFAULT_URL_BASE + "hes-gateway/terminal/initialize/appUserOrInstallerLogin"
        pw_hash = hashlib.md5(bytes(password, "ascii")).hexdigest()
        form = {
            "account": username,
            "password": pw_hash,
            "lang": "en_US",
            "type": 1,
        }
        try:
            res = requests.post(url, data=form, timeout=REQUEST_TIMEOUT)
            res.raise_for_status()
            body = res.json()
        except requests.RequestException as err:
            raise DeviceTimeoutException(f"Login request failed: {err}") from err
        except (ValueError, KeyError) as err:
            raise FranklinAPIError(f"Invalid login response: {err}") from err

        if body.get("code") == 401:
            raise InvalidCredentialsException(body.get("message", "Invalid credentials"))
        if body.get("code") == 400:
            raise AccountLockedException(body.get("message", "Account locked"))
        if body.get("code") != 200:
            raise FranklinAPIError(f"Unexpected login response code {body.get('code')}: {body.get('message')}")

        return body["result"]["token"]


def retry(func, fltr, refresh_func):
    """Tries calling func, and if filter fails it calls refresh func then tries again.

    A refresh failure is surfaced as ``TokenExpiredException`` so callers can
    distinguish it from a normal API error; this avoids silently swallowing
    auth failures inside an otherwise successful-looking retry.
    """
    res = func()
    if fltr(res):
        return res
    try:
        refresh_func()
    except (AccountLockedException, InvalidCredentialsException):
        raise
    except Exception as err:
        raise TokenExpiredException(f"Token refresh failed: {err}") from err
    return func()


class Client:
    def __init__(self, fetcher: TokenFetcher, gateway: str, url_base: str = DEFAULT_URL_BASE):
        self.fetcher = fetcher
        self.gateway = gateway
        self.url_base = url_base
        # Serialize token refreshes across threads so concurrent platforms
        # don't stampede the login endpoint or race on ``self.token``.
        self._token_lock = threading.Lock()
        self.token: str | None = None
        self.refresh_token()
        self.snno = 0

    def _post(self, url, payload):
        def __post():
            try:
                res = requests.post(
                    url,
                    headers={"loginToken": self.token, "Content-Type": "application/json"},
                    data=payload,
                    timeout=REQUEST_TIMEOUT,
                )
                res.raise_for_status()
                return res.json()
            except requests.Timeout as err:
                raise DeviceTimeoutException(f"POST request timed out: {err}") from err
            except requests.RequestException as err:
                raise FranklinAPIError(f"POST request failed: {err}") from err
            except ValueError as err:
                raise FranklinAPIError(f"Invalid JSON in POST response: {err}") from err

        return retry(__post, lambda j: j.get("code") != 401, self.refresh_token)

    def _post_form(self, url, payload):
        def __post():
            try:
                res = requests.post(
                    url,
                    headers={
                        "loginToken": self.token,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "optsource": "3",
                    },
                    data=payload,
                    timeout=REQUEST_TIMEOUT,
                )
                res.raise_for_status()
                return res.json()
            except requests.Timeout as err:
                raise DeviceTimeoutException(f"POST form request timed out: {err}") from err
            except requests.RequestException as err:
                raise FranklinAPIError(f"POST form request failed: {err}") from err
            except ValueError as err:
                raise FranklinAPIError(f"Invalid JSON in POST form response: {err}") from err

        return retry(__post, lambda j: j.get("code") != 401, self.refresh_token)

    def _get(self, url):
        params = {"gatewayId": self.gateway, "lang": "en_US"}

        def __get():
            try:
                res = requests.get(
                    url,
                    params=params,
                    headers={"loginToken": self.token},
                    timeout=REQUEST_TIMEOUT,
                )
                res.raise_for_status()
                return res.json()
            except requests.Timeout as err:
                raise DeviceTimeoutException(f"GET request timed out: {err}") from err
            except requests.RequestException as err:
                raise FranklinAPIError(f"GET request failed: {err}") from err
            except ValueError as err:
                raise FranklinAPIError(f"Invalid JSON in GET response: {err}") from err

        return retry(__get, lambda j: j.get("code") != 401, self.refresh_token)

    def refresh_token(self) -> None:
        """Refresh the auth token.

        Guarded by a lock so concurrent callers don't race on ``self.token``.
        Serial duplicate logins are accepted as the cost of simplicity.
        """
        with self._token_lock:
            self.token = self.fetcher.get_token()

    def get_smart_switch_state(self):
        # TODO(richo) This API is super in flux, both because of how vague the
        # underlying API is and also trying to figure out what to do with
        # inconsistency.
        # Whether this should use the _switch_status() API is super unclear.
        # Maybe I will reach out to FranklinWH once I have published.
        status = self._status()
        switches = map(lambda x: x == 1, status["pro_load"])
        return tuple(switches)

    def set_smart_switch_state(self, state: tuple[typing.Optional[bool], typing.Optional[bool], typing.Optional[bool]]):
        """Set the state of the smart circuits.

        Setting a value in the state tuple to True will turn on that circuit,
        setting to False will turn it off. Setting to None will make it
        unchanged.
        """
        payload = self._switch_status()
        payload["opt"] = 1
        payload.pop("modeChoose")
        payload.pop("result")

        if payload["SwMerge"] == 1:
            if state[0] != state[1]:
                raise RuntimeError(
                    "Smart switches 1 and 2 are merged! Setting them to "
                    "different values could do bad things to your house. Aborting."
                )

        for i in range(3):
            sw = i + 1
            mode_key = f"Sw{sw}Mode"
            msg_type = f"Sw{sw}MsgType"
            pro_load = f"Sw{sw}ProLoad"

            if state[i] is not None:
                payload[msg_type] = 1
                if state[i] is True:
                    payload[mode_key] = 1
                    payload[pro_load] = 0
                elif state[i] is False:
                    payload[mode_key] = 0
                    payload[pro_load] = 1

        wire_payload = self._build_payload(311, payload)
        data = self._mqtt_send(wire_payload)["result"]["dataArea"]
        return json.loads(data)

    # Sends a 203 which is a high level status
    def _status(self):
        payload = self._build_payload(203, {"opt": 1, "refreshData": 1})
        data = self._mqtt_send(payload)["result"]["dataArea"]
        _LOGGER.debug("FRANKLIN_DATA: %s", data)
        return json.loads(data)

    # Sends a 311 which appears to be a more specific switch command
    def _switch_status(self):
        payload = self._build_payload(311, {"opt": 0, "order": self.gateway})
        data = self._mqtt_send(payload)["result"]["dataArea"]
        return json.loads(data)

    # Sends a 353 which grabs real-time smart-circuit load information
    # https://github.com/richo/homeassistant-franklinwh/issues/27#issuecomment-2714422732
    def _switch_usage(self):
        payload = self._build_payload(353, {"opt": 0, "order": self.gateway})
        data = self._mqtt_send(payload)["result"]["dataArea"]
        return json.loads(data)

    def set_mode(self, mode):
        url = self.url_base + "hes-gateway/terminal/tou/updateTouMode"
        payload = mode.payload(self.gateway)
        res = self._post_form(url, payload)
        return res

    def get_mode(self) -> tuple[str, int | None]:
        status = self._switch_status()
        mode_name = MODE_MAP.get(status["runingMode"], "unknown_mode")
        if mode_name == MODE_TIME_OF_USE:
            return (mode_name, status["touMinSoc"])
        elif mode_name == MODE_SELF_CONSUMPTION:
            return (mode_name, status["selfMinSoc"])
        elif mode_name == MODE_EMERGENCY_BACKUP:
            return (mode_name, status["backupMaxSoc"])
        return ("unknown_mode", None)

    def get_stats(self) -> Stats:
        """Get current statistics for the FHP.

        This includes instantaneous measurements for current power, as well as
        totals for today (in local time).
        """
        data = self._status()
        swdata = self._switch_usage()

        return Stats(
            Current(
                data["p_sun"],
                data["p_gen"],
                data["p_fhp"],
                data["p_uti"],
                data["p_load"],
                data["soc"],
                swdata["SW1ExpPower"],
                swdata["SW2ExpPower"],
                swdata["CarSWPower"],
            ),
            Totals(
                data["kwh_fhp_chg"],
                data["kwh_fhp_di"],
                data["kwh_uti_in"],
                data["kwh_uti_out"],
                data["kwh_sun"],
                data["kwh_gen"],
                data["kwh_load"],
                swdata["SW1ExpEnergy"],
                swdata["SW2ExpEnergy"],
                swdata["CarSWExpEnergy"],
                swdata["CarSWImpEnergy"],
            ),
        )

    def poll_bundle(self) -> "FranklinData":
        """Single method that fetches stats, switch state, and mode in one go.

        Deduplicates internal API calls: _status() is called once for stats and
        switch state, _switch_usage() for energy data, _switch_status() for
        mode info.
        """
        data = self._status()
        swdata = self._switch_usage()

        stats = Stats(
            Current(
                data["p_sun"],
                data["p_gen"],
                data["p_fhp"],
                data["p_uti"],
                data["p_load"],
                data["soc"],
                swdata["SW1ExpPower"],
                swdata["SW2ExpPower"],
                swdata["CarSWPower"],
            ),
            Totals(
                data["kwh_fhp_chg"],
                data["kwh_fhp_di"],
                data["kwh_uti_in"],
                data["kwh_uti_out"],
                data["kwh_sun"],
                data["kwh_gen"],
                data["kwh_load"],
                swdata["SW1ExpEnergy"],
                swdata["SW2ExpEnergy"],
                swdata["CarSWExpEnergy"],
                swdata["CarSWImpEnergy"],
            ),
        )

        switch_state = tuple(x == 1 for x in data["pro_load"])

        try:
            sw_status = self._switch_status()
            mode_name = MODE_MAP.get(sw_status["runingMode"], "unknown_mode")
            if mode_name == MODE_TIME_OF_USE:
                mode_soc = sw_status.get("touMinSoc")
            elif mode_name == MODE_SELF_CONSUMPTION:
                mode_soc = sw_status.get("selfMinSoc")
            elif mode_name == MODE_EMERGENCY_BACKUP:
                mode_soc = sw_status.get("backupMaxSoc")
            else:
                mode_soc = None
        except Exception:
            _LOGGER.debug("Could not fetch mode info during poll_bundle", exc_info=True)
            mode_name = None
            mode_soc = None

        return FranklinData(
            stats=stats,
            switch_state=switch_state,
            mode=mode_name,
            mode_soc=mode_soc,
        )

    def next_snno(self):
        self.snno += 1
        return self.snno

    def _build_payload(self, ty, data):
        blob = json.dumps(data, separators=(",", ":")).encode("utf-8")
        crc = to_hex(zlib.crc32(blob))
        length = len(blob)
        ts = int(time.time())

        temp = json.dumps({
            "lang": "EN_US",
            "cmdType": ty,
            "equipNo": self.gateway,
            "type": 0,
            "timeStamp": ts,
            "snno": self.next_snno(),
            "len": length,
            "crc": crc,
            "dataArea": "DATA",
        })
        # We do it this way because without a canonical way to generate JSON we
        # can't risk reordering breaking the CRC.
        return temp.replace('"DATA"', blob.decode("utf-8"))

    def _mqtt_send(self, payload):
        url = self.url_base + "hes-gateway/terminal/sendMqtt"
        # _post already maps requests.Timeout -> DeviceTimeoutException and
        # other transport/JSON errors -> FranklinAPIError; let those propagate
        # unchanged rather than masking them as a device timeout.
        res = self._post(url, payload)

        code = res.get("code")
        if code == 102:
            raise DeviceTimeoutException(res.get("message", "Device timeout"))
        if code == 136:
            raise GatewayOfflineException(res.get("message", "Gateway offline"))
        if code != 200:
            raise FranklinAPIError(
                f"Unexpected MQTT response code {code}: {res.get('message')}"
            )
        if "result" not in res or "dataArea" not in res.get("result", {}):
            raise FranklinAPIError("Malformed MQTT response: missing result.dataArea")
        return res


class UnknownMethodsClient(Client):
    """A client that also implements some methods that don't obviously work, for research purposes."""

    def get_controllable_loads(self):
        url = self.url_base + "hes-gateway/terminal/selectTerGatewayControlLoadByGatewayId"
        params = {"id": self.gateway, "lang": "en_US"}
        headers = {"loginToken": self.token}
        res = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        return res.json()

    def get_accessory_list(self):
        url = self.url_base + "hes-gateway/terminal/getIotAccessoryList"
        params = {"gatewayId": self.gateway, "lang": "en_US"}
        headers = {"loginToken": self.token}
        res = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        return res.json()

    def get_equipment_list(self):
        url = self.url_base + "hes-gateway/manage/getEquipmentList"
        params = {"gatewayId": self.gateway, "lang": "en_US"}
        headers = {"loginToken": self.token}
        res = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        return res.json()
