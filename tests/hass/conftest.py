# =============================================================================
# HA automation test harness — shared fixtures
# =============================================================================
# Loads a package file from the GitOps tree into an in-process Home Assistant
# (pytest-homeassistant-custom-component), seeds the state machine with fake
# entities, and records light service calls. No cluster, no real integrations:
# automations only talk to the state machine and the service registry.
#
# The instance is pinned to the cluster's real location (Seattle, from
# kubernetes/flux/vars/cluster-settings.yaml) so sun conditions compute the
# same sunrise/sunset the deployed automations see.
#
# Adding tests for another package: copy the setup_<pkg> helper pattern and
# point it at the new file under
# kubernetes/apps/home/home-assistant/app/config/packages/.
# =============================================================================
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

PACKAGES_DIR = Path(__file__).parents[2] / "kubernetes/apps/home/home-assistant/app/config/packages"

# Entity IDs as deployed (keep in sync with the package under test)
PIR = "binary_sensor.motion_sensor_gen2_motion_detection"
SERENA_MAT = "binary_sensor.master_bedroom_serenawithings_in_bed"
MIKE_MAT = "binary_sensor.master_bedroom_mikewithings_in_bed"
MAIN_LIGHTS = "light.master_bedroom_lights"
BLINDS = "cover.master_blinds"
AUTO_TOGGLE = "input_boolean.master_bed_nightlight_auto"
SEG_SERENA_HB = "light.master_bedroom_wled_master_bed_segment_1"
SEG_SERENA_GROUND = "light.master_bedroom_wled_master_bed_segment_2"
SEG_MIKE_HB = "light.master_bedroom_wled_master_bed_segment_3"
ALL_SEGMENTS = [SEG_SERENA_HB, SEG_SERENA_GROUND, SEG_MIKE_HB]

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def local(hour: int, minute: int = 0, day: int = 5, month: int = 10) -> datetime:
    """Aware datetime in the cluster's timezone (Oct 2026 by default)."""
    return datetime(2026, month, day, hour, minute, tzinfo=LOCAL_TZ)


async def setup_nightlight(hass: HomeAssistant) -> None:
    """Load the master_bed_nightlight package (toggle left at initial off)."""
    raw = yaml.safe_load(
        (PACKAGES_DIR / "master_bed_nightlight.yaml").read_text(encoding="utf-8")
    )
    pkg = raw["master_bed_nightlight"]

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": pkg["input_boolean"]}
    )
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "automation", {"automation": pkg["automation"]})
    await hass.async_block_till_done()


def seed_room(
    hass: HomeAssistant,
    *,
    serena_mat: str = "on",
    mike_mat: str = "on",
    main_lights: str = "off",
    blinds_position: int = 80,
) -> None:
    """Seed the master-bedroom state machine (call AFTER freezer.move_to so
    last_changed lands on the frozen clock). Sun is the real integration —
    do not seed sun.sun."""
    hass.states.async_set(PIR, "off")
    hass.states.async_set(SERENA_MAT, serena_mat)
    hass.states.async_set(MIKE_MAT, mike_mat)
    hass.states.async_set(MAIN_LIGHTS, main_lights)
    hass.states.async_set(
        BLINDS, "open" if blinds_position > 0 else "closed",
        {"current_position": blinds_position},
    )


def fire_motion(hass: HomeAssistant) -> None:
    hass.states.async_set(PIR, "on")


@pytest.fixture
def light_calls(hass: HomeAssistant):
    """Record light.turn_on / light.turn_off service calls."""
    recorded: dict[str, list[ServiceCall]] = {"on": [], "off": []}

    async def turn_on(call: ServiceCall) -> None:
        recorded["on"].append(call)

    async def turn_off(call: ServiceCall) -> None:
        recorded["off"].append(call)

    hass.services.async_register("light", "turn_on", turn_on)
    hass.services.async_register("light", "turn_off", turn_off)
    return recorded


@pytest.fixture
async def nightlight(hass: HomeAssistant, light_calls):
    """Pin the instance to Seattle, seed default room state, load the package
    (entities must exist before setup so numeric_state triggers arm), then
    enable the auto toggle like the operator does."""
    hass.config.latitude = 47.678796
    hass.config.longitude = -122.374477
    hass.config.elevation = 500
    hass.config.time_zone = "America/Los_Angeles"
    dt_util.set_default_time_zone(dt_util.get_time_zone("America/Los_Angeles"))

    seed_room(hass)  # entities present before automation setup
    # sun conditions validate against a live sun.sun — set the integration up
    # explicitly (automation setup only LOADS sun, it does not start it)
    assert await async_setup_component(hass, "sun", {"sun": {}})
    await hass.async_block_till_done()
    await setup_nightlight(hass)
    hass.states.async_set(AUTO_TOGGLE, "on")
    return light_calls


async def tick(hass: HomeAssistant, freezer, seconds: float) -> None:
    """Advance the frozen clock AND HA's timers by `seconds`.

    The freezer must move too: templates evaluate now() against freezegun's
    clock, while async_fire_time_changed only drains HA's timers. Moving one
    without the other makes last_changed deltas lie (harness lesson from the
    first run of this suite)."""
    freezer.tick(dt_util.dt.timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
