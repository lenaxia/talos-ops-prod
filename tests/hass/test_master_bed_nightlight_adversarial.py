# =============================================================================
# Adversarial scenarios for master_bed_nightlight — sequences the real
# devices produce that single-event tests miss: sensor flapping, recovery
# from unavailability, rapid retriggers under mode: restart, and trigger
# interleavings (asleep timer arriving while the partner is legitimately
# up and lit).
# =============================================================================
from .conftest import (
    MAIN_LIGHTS,
    MIKE_MAT,
    PIR,
    SEG_MIKE_HB,
    SEG_SERENA_GROUND,
    SEG_SERENA_HB,
    SERENA_MAT,
    fire_motion,
    local,
    seed_room,
    tick,
    targets,
)


async def test_mat_flap_rapid_cycles_never_light_sleeper(hass, nightlight, freezer):
    """Serena in bed, mat flapping off/on/off with 8 s gaps (roll-over
    pattern). Every flap is inside the 15 s debounce window, so her side
    must never light while Mike walks."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="on", mike_mat="off")
    await tick(hass, freezer, 30)  # mike out, stable

    for state in ("off", "on", "off"):
        hass.states.async_set(SERENA_MAT, state)
        await tick(hass, freezer, 8)

    fire_motion(hass)
    await hass.async_block_till_done()
    # serena's last flip was 'off' 8 s ago -> still IN; mike OUT -> his side
    assert len(nightlight["on"]) == 1
    assert targets(nightlight["on"][0]) == {SEG_MIKE_HB}


async def test_mat_unknown_state_counts_as_out(hass, nightlight, freezer):
    """'unknown' (distinct from 'unavailable') must also count as out."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="unknown", mike_mat="on")
    fire_motion(hass)
    await hass.async_block_till_done()
    assert targets(nightlight["on"][0]) == {SEG_SERENA_HB, SEG_SERENA_GROUND}


async def test_pir_unavailable_then_recovered(hass, nightlight, freezer):
    """A PIR outage window must not wedge anything: after the sensor
    returns, a normal motion edge lights the correct segments."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="on")
    await tick(hass, freezer, 30)

    # sensor drops out and returns (no on-edge while gone)
    hass.states.async_set(PIR, "unavailable")
    await tick(hass, freezer, 60)
    hass.states.async_set(PIR, "off")
    await tick(hass, freezer, 5)

    fire_motion(hass)
    await hass.async_block_till_done()
    assert targets(nightlight["on"][0]) == {SEG_SERENA_HB, SEG_SERENA_GROUND}


async def test_rapid_retrigger_restart_stays_consistent(hass, nightlight, freezer):
    """Motion burst (on/off/on within seconds) under mode: restart must end
    in a consistent lit state, and the later motion-clear still produces a
    single clean fade."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)

    fire_motion(hass)
    await hass.async_block_till_done()
    hass.states.async_set(PIR, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 1)
    fire_motion(hass)
    await hass.async_block_till_done()

    # last run wins: everything lit for both-out
    assert targets(nightlight["on"][-1]) == {SEG_SERENA_HB, SEG_SERENA_GROUND, SEG_MIKE_HB}

    hass.states.async_set(PIR, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 181)
    assert len(nightlight["off"]) == 1


async def test_asleep_timer_arrives_while_partner_active(hass, nightlight, freezer):
    """Mike returns to bed (arming his 5-min asleep timer) while Serena is
    still up with her side lit. When his timer fires, the gate must stop —
    her lights must NOT be killed by his asleep trigger."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"]

    # mike back in bed (real off->on edge arms the 5-min timer)
    hass.states.async_set(MIKE_MAT, "on")
    await hass.async_block_till_done()

    # serena still up: 4 min in, more motion (real off->on edge — PIRs
    # clear between detections; a state-identical write is a no-op) ->
    # her side lights
    await tick(hass, freezer, 240)
    hass.states.async_set(PIR, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 5)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert targets(nightlight["on"][-1]) == {SEG_SERENA_HB, SEG_SERENA_GROUND}

    # mike's asleep trigger fires at 5 min; gate sees serena still out -> stop
    await tick(hass, freezer, 70)
    assert nightlight["off"] == []


async def test_nightlight_relights_after_main_lights_cycle(hass, nightlight, freezer):
    """Main lights on kills the nightlight (instant off); lights back off +
    new motion must relight cleanly."""
    freezer.move_to(local(23, 30))
    seed_room(hass, serena_mat="off", mike_mat="off")
    await tick(hass, freezer, 30)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert nightlight["on"]

    hass.states.async_set(MAIN_LIGHTS, "on")
    await hass.async_block_till_done()
    assert nightlight["off"]

    hass.states.async_set(PIR, "off")
    await hass.async_block_till_done()
    hass.states.async_set(MAIN_LIGHTS, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 5)
    fire_motion(hass)
    await hass.async_block_till_done()
    assert targets(nightlight["on"][-1]) == {SEG_SERENA_HB, SEG_SERENA_GROUND, SEG_MIKE_HB}
