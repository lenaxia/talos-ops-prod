# Harness semantic-parity audit

The harness pins HA **2026.2.3** (newest published to PyPI) while the cluster
runs **2026.9.4** (`ghcr.io/lenaxia/home-assistant`, helm-release.yaml). This
audit verifies the HA behaviors the test suite depends on are identical
between the two, so version skew cannot silently invalidate test results.

Audit date: 2026-10-05, performed against tag **2026.9.4** (all five audited
files are also byte-identical between 2026.9.3 and 2026.9.4, so conclusions
carry across patch releases in that series). **Re-run this audit whenever
either version changes.** Method: fetch the deployed tag's source from
`home-assistant/core` and diff against the installed harness copy.

| # | Semantic | File(s) | 2026.2.3 | 2026.9.3 | Verdict |
|---|---|---|---|---|---|
| 1 | `condition: sun` with `after: sunset` + `before: sunrise` in ONE condition OR-s the midnight wrap | `components/sun/condition.py` | OR-case at L85 | OR-case at L127 | identical |
| 2 | `numeric_state` evaluates an `attribute` (covers expose position only as attribute) | `helpers/condition.py` | attribute supported | attribute supported | identical |
| 3 | State-identical write (same state+attributes, no `force_update`) emits no `state_changed` and preserves `last_changed` — debounce and watchdog tests hinge on this | `core.py` StateMachine | `same_state`/`same_attr`/`last_changed` logic | same, verbatim | identical |
| 4 | State-trigger `for:` timer resets on re-edge | `components/homeassistant/triggers/state.py` | for-timer attach/cancel logic | diff clean | identical |
| 5 | A condition inside `if/then` halts only that branch (`_ConditionFail`), not the parent sequence | `helpers/script.py` | `_ConditionFail` subclass of `_HaltScript`, caught per-branch | same mechanism (L419/L511) | identical |

Known gap NOT testable at state-machine level: a bed mat stuck **on** while
its owner is actually up is indistinguishable from "in bed" — the nightlight
correctly lights nothing for that person. Fix is physical (bedside sensors),
not logical; see the package header's notes on `side_debounce`.
