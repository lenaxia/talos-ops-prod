# =============================================================================
# Signal-matrix behavioral tests for the master_bed_nightlight package.
#
# Every scenario mirrors a row of the matrix reviewed in PRs #2646/#2649.
# The three regression cases (inert debounce, dead asleep-gate, watchdog)
# encode the exact bugs found and fixed there.
#
# Seattle, October 2026: sunset ~18:30 PDT, sunrise ~07:10 PDT.
# Local clock helpers come from conftest; the freezer pins HA's clock.
# =============================================================================
import pytest
from homeassistant.core import HomeAssistant

from .conftest import (
    ALL_SEGMENTS,
    MAIN_LIGHTS,
    MIKE_MAT,
    PIR,
    SEG_MIKE_HB,
    SEG_SERENA_GROUND,
    SEG_SERENA_HB,
    SERENA_MAT,
    BLINDS,
    fire_motion,
    local,
    seed_room,
    setup_nightlight,
    tick,
)


def _targets(call) -> set[str]:
    eid = call.data["entity_id"]
    if isinstance(eid, str):
        eid = [eid]
    return set(eid)


# ---------------------------------------------------------------------------
# ON automation — gating
# ---------------------------------------------------------------------------

async def test_ships_disabled_by_default(hass: HomeAssistant, light_calls):
    """Without the operator toggle, motion does nothing."""
    from .conftest import seed_room as seed

    seed(hass)
    await setup_nightlight(hass)
    # toggle left at its initial "off" state
    fire_motion(hass)
    await hass.async_block_till_done()
    assert light_calls["on"] == []


async def test_main_lights_on_blocks_nightlight(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off", main_lights="on")
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"] == []


async def test_bright_open_room_blocks_nightlight(hass, nightlight, freezer):
    freezer.move_to(local(12))  # midday: sun up, blinds open
    seed_room(hass, serena_mat="off", mike_mat="off", blinds_position=80)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"] == []


# ---------------------------------------------------------------------------
# ON automation — occupancy selection
# ---------------------------------------------------------------------------

async def test_unknown_mover_both_in_bed_lights_nothing(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="on", mike_mat="on")
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"] == []


async def test_serena_out_mike_asleep_lights_serena_side_only(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="on")
    await tick(hass, freezer, 30)  # mat off long enough to clear the 15 s debounce
    fire_motion(hass)
    await hass.async_block_till_done()
    assert len(nightlight["on"]) == 1
    assert _targets(nightlight["on"][0]) == {SEG_SERENA_HB, SEG_SERENA_GROUND}


async def test_mike_out_serena_asleep_lights_mike_side_only(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="on", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert len(nightlight["on"]) == 1
    assert _targets(nightlight["on"][0]) == {SEG_MIKE_HB}


async def test_everyone_out_lights_all_segments(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert _targets(nightlight["on"][0]) == set(ALL_SEGMENTS)


async def test_regression_debounce_bounce_does_not_light_sleeper(hass, nightlight, freezer):
    """REGRESSION (PR #2649 bug 1): a mat bounced 'off' for 2 s (roll-over)
    must NOT count as out — the sleeper's side stays dark."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="on", mike_mat="on")
    # Serena rolls over: mat drops to off 2 s ago and holds (bounce window)
    hass.states.async_set(SERENA_MAT, "off")
    await tick(hass, freezer, 2)
    fire_motion(hass)
    await hass.async_block_till_done()
    # serena counts as IN (bounce) and mike is IN -> unknown mover -> nothing
    assert nightlight["on"] == []


async def test_dead_mat_counts_as_out(hass, nightlight, freezer):
    """Unavailable mat (week-long outage precedent) lights that side rather
    than leaving the walker dark."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="unavailable", mike_mat="on")
    fire_motion(hass)
    await hass.async_block_till_done()
    assert _targets(nightlight["on"][0]) == {SEG_SERENA_HB, SEG_SERENA_GROUND}


# ---------------------------------------------------------------------------
# ON automation — scene buckets
# ---------------------------------------------------------------------------

async def test_deep_night_bucket_is_dim_red(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    data = nightlight["on"][0].data
    assert data["brightness_pct"] == 10
    assert list(data["rgb_color"]) == [255, 40, 0]


async def test_evening_bucket_is_warm_amber(hass, nightlight, freezer):
    freezer.move_to(local(20))  # after sunset (~18:30), before 23:00
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    data = nightlight["on"][0].data
    assert data["brightness_pct"] == 30
    assert list(data["rgb_color"]) == [255, 160, 0]


async def test_dawn_bucket_is_warm_white(hass, nightlight, freezer):
    freezer.move_to(local(5, 30, day=6))  # after 05:00, before sunrise (~07:10)
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    data = nightlight["on"][0].data
    assert data["brightness_pct"] == 20
    assert list(data["rgb_color"]) == [255, 190, 140]


async def test_daytime_blinds_nap_falls_to_default_bucket(hass, nightlight, freezer):
    """Day + blinds drawn (<=20) passes the dark gate via the blinds branch;
    no time bucket matches -> choose default (evening values)."""
    freezer.move_to(local(12))
    seed_room(hass, serena_mat="off", mike_mat="off", blinds_position=10)
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    data = nightlight["on"][0].data
    assert data["brightness_pct"] == 30


# ---------------------------------------------------------------------------
# OFF automation
# ---------------------------------------------------------------------------

async def test_motion_clear_three_minutes_fades_off(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"]

    hass.states.async_set(PIR, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 181)
    assert len(nightlight["off"]) == 1
    assert nightlight["off"][0].data.get("transition") == 3


async def test_main_lights_on_turns_nightlight_off(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()

    hass.states.async_set(MAIN_LIGHTS, "on")
    await hass.async_block_till_done()
    assert len(nightlight["off"]) == 1


async def test_regression_asleep_gate_partner_up_keeps_lights_on(hass, nightlight, freezer):
    """REGRESSION (PR #2649 bug 2): mike back in bed 5 min while Serena is
    still UP must NOT kill the nightlight."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="on")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"]

    hass.states.async_set(MIKE_MAT, "on")
    await tick(hass, freezer, 301)
    assert nightlight["off"] == []


async def test_everyone_back_in_bed_turns_lights_off(hass, nightlight, freezer):
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()

    hass.states.async_set(MIKE_MAT, "on")
    hass.states.async_set(SERENA_MAT, "on")
    await hass.async_block_till_done()
    await tick(hass, freezer, 301)
    # both asleep triggers fire (one per mat) -> two idempotent turn_off calls
    assert nightlight["off"]


async def test_blinds_opening_turns_lights_off(hass, nightlight, freezer):
    freezer.move_to(local(9))  # morning, sun up: dark gate rests on blinds
    seed_room(hass, serena_mat="off", mike_mat="off", blinds_position=10)
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"]

    hass.states.async_set(BLINDS, "open", {"current_position": 80})
    await hass.async_block_till_done()
    assert len(nightlight["off"]) == 1


# ---------------------------------------------------------------------------
# Watchdog (regression, PR #2649 bug 3)
# ---------------------------------------------------------------------------

async def test_regression_watchdog_stuck_pir_kills_lights(hass, nightlight, freezer):
    """PIR stuck ON for 30 min (no clear edge) -> nightlight off."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"]

    await tick(hass, freezer, 29 * 60)
    assert nightlight["off"] == []  # not yet

    await tick(hass, freezer, 2 * 60)  # past 30 min of continuous on
    assert len(nightlight["off"]) == 1
