from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ADDRESS, DOMAIN


class TrumaLevelControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    def _next_bottle_title(self) -> str:
        """Return Flasche 1, Flasche 2, ... for multiple LevelControl devices."""
        used = {entry.title for entry in self._async_current_entries()}
        number = 1
        while f"Flasche {number}" in used:
            number += 1
        return f"Flasche {number}"

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        title = self._next_bottle_title()
        self.context["title_placeholders"] = {"name": title}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        if self._discovery_info is None:
            return self.async_abort(reason="discovery_error")
        title = self._next_bottle_title()
        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={CONF_ADDRESS: self._discovery_info.address},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": title,
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._next_bottle_title(),
                data={CONF_ADDRESS: address},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
        )
