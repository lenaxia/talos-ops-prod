#!/usr/bin/env python3
# =============================================================================
# Deploy-tree cron validity guard (LLMSafeSpaces issue #1905).
#
# Walks every YAML under kubernetes/ and validates each literal cron
# expression found in cron:/schedule:-shaped string fields:
#
#   * five-field expressions (minute hour dom month dow) are validated
#     against the standard ranges — minute 0-59, hour 0-23, dom 1-31,
#     month 1-12, dow 0-7 (0 and 7 both Sunday) — the same class of
#     validation as the platform trigger validator
#     (LLMSafeSpaces pkg/workflows robfig 5-field parser). #1905's bug
#     was a RecurringJob cron "0 1 * * 8": day-of-week 8 is outside
#     0-7, Longhorn's parser rejects the job, snapshots never run.
#   * six-field expressions (CloudNative-PG backup schedule dialect,
#     seconds-prefixed) validate the seconds field 0-59 plus the five
#     standard fields.
#   * @-shorthands accepted by the batch/v1 CronJob controller and the
#     robfig dialect (@hourly, @midnight, ... @every <duration>) pass a
#     known-form check; anything else @-prefixed fails.
#   * values containing "${" are shell/kustomize templates, not literal
#     crons — skipped (counted, but not validated).
#
# The guard asserts a non-trivial harvest so a walker regression (e.g.
# silently matching zero files) cannot pass vacuously, and pins that the
# longhorn storage app's expressions are in the harvest (the #1905 site).
#
# Encrypted sops files (*.sops.yaml or a top-level sops: block) are
# skipped: their contents are ciphertext by construction.
#
# Run: python3 -m pytest tests/test_cron_validity.py -q
# =============================================================================
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_TREE = REPO_ROOT / "kubernetes"
CRON_KEYS = {"cron", "schedule"}

# (minute, hour, day-of-month, month, day-of-week) standard ranges.
FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
SECONDS_RANGE = (0, 59)

AT_TOKENS = {
    "@yearly", "@annually", "@monthly", "@weekly", "@daily", "@hourly", "@midnight",
}

# Walker-regression floor: the tree harvests well above this today; if a
# "valid" run finds fewer, the walker is silently skipping files.
MIN_HARVEST = 20

# Files that do not parse even under the lenient loader, frozen here so
# the audit surface cannot silently shrink: a NEW unparseable file fails
# the guard and must be either fixed or consciously added to this list.
#   - kvm-device.yaml: committed with a one-space global indent (upstream
#     NodeFeatureRule example shape); no cron content.
KNOWN_UNPARSEABLE = {
    "kubernetes/apps/kube-system/node-feature-discovery/rules/kvm-device.yaml",
}


def _validate_component(comp: str, lo: int, hi: int) -> str | None:
    """Validate one field component (*, n, a-b, */s, a-b/s). None = ok."""
    if comp == "":
        return "empty component"
    base, slash, step_s = comp.partition("/")
    if slash and (not step_s.isdigit() or int(step_s) < 1):
        return f"invalid step {comp!r}"
    if base == "*":
        return None
    start_s, dash, end_s = base.partition("-")
    if dash:
        if not (start_s.isdigit() and end_s.isdigit()):
            return f"malformed value {comp!r}"
        start, end = int(start_s), int(end_s)
        if not (lo <= start <= hi and lo <= end <= hi):
            return f"value {comp!r} out of range [{lo}, {hi}]"
        if start > end:
            return f"descending range {comp!r}"
        return None
    if not base.isdigit():
        return f"non-numeric value {comp!r}"
    if not lo <= int(base) <= hi:
        return f"value {comp!r} out of range [{lo}, {hi}]"
    return None


def validate_field(field: str, lo: int, hi: int) -> str | None:
    """Validate one cron field: comma-separated components, each standard."""
    if field == "":
        return "empty field"
    for comp in field.split(","):
        err = _validate_component(comp, lo, hi)
        if err:
            return err
    return None


def validate_cron(expr: str) -> str | None:
    """Validate a cron expression; return a human-readable error or None."""
    expr = expr.strip()
    if expr.startswith("@"):
        if expr in AT_TOKENS:
            return None
        if expr.startswith("@every "):
            return None  # duration accepted verbatim (robfig/forgejo dialect)
        return f"unknown @-shorthand {expr!r}"
    tokens = expr.split()
    if len(tokens) == 5:
        fields, ranges = tokens, FIELD_RANGES
    elif len(tokens) == 6:
        # seconds-prefixed dialect (CloudNative-PG backup.schedule)
        err = validate_field(tokens[0], *SECONDS_RANGE)
        if err:
            return f"seconds field: {err}"
        fields, ranges = tokens[1:], FIELD_RANGES
    else:
        return f"expected 5 fields (or 6 with seconds), got {len(tokens)}"
    for token, (lo, hi) in zip(fields, ranges):
        err = validate_field(token, lo, hi)
        if err:
            return err
    return None


class AuditLoader(yaml.SafeLoader):
    """SafeLoader plus audit-friendly leniency.

    - Unknown tags (ESPHome !secret etc.) stringify: those configs share
      the deploy tree and carry no cron semantics, but skipping files
      would be a blind spot a future invalid cron could hide behind.
    - Duplicate anchors are tolerated, last definition wins (same
      behavior as the Flux/kustomize YAML 1.2 tooling that consumes
      these files; pyyaml's Composer is stricter than the cluster and
      rejects e.g. gamevault's helm-release on a repeated &ns).
    """


def _stringify_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


AuditLoader.add_multi_constructor("!", _stringify_tag)


def _compose_node_tolerant(self, parent, index):
    # pyyaml Composer.compose_node verbatim minus the duplicate-anchor
    # raise (see class docstring).
    if self.check_event(yaml.AliasEvent):
        event = self.get_event()
        anchor = event.anchor
        if anchor not in self.anchors:
            raise yaml.YAMLError(f"found undefined alias {anchor!r}")
        return self.anchors[anchor]
    event = self.peek_event()
    anchor = event.anchor
    self.descend_resolver(parent, index)
    if self.check_event(yaml.ScalarEvent):
        node = self.compose_scalar_node(anchor)
    elif self.check_event(yaml.SequenceStartEvent):
        node = self.compose_sequence_node(anchor)
    elif self.check_event(yaml.MappingStartEvent):
        node = self.compose_mapping_node(anchor)
    self.ascend_resolver()
    return node


AuditLoader.compose_node = _compose_node_tolerant


def _is_sops(docs: list) -> bool:
    return any(isinstance(d, dict) and "sops" in d for d in docs)


def _harvest(node, loc: str, key_chain: tuple, out: list) -> None:
    """Collect string values under cron:/schedule: keys, recursively."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CRON_KEYS and isinstance(value, str) and value.strip():
                out.append((loc, ".".join([*key_chain, str(key)]), value.strip()))
            else:
                _harvest(value, loc, (*key_chain, str(key)), out)
    elif isinstance(node, list):
        for item in node:
            _harvest(item, loc, key_chain, out)


def collect_cron_expressions(deploy_tree: Path) -> list[tuple[str, str, str]]:
    cases: list[tuple[str, str, str]] = []
    unparseable: list[str] = []
    for path in sorted(deploy_tree.rglob("*.y*ml")):
        if path.name.endswith(".sops.yaml"):
            continue
        try:
            docs = list(yaml.load_all(path.read_text(), Loader=AuditLoader))
        except yaml.YAMLError:
            unparseable.append(str(path.relative_to(REPO_ROOT)))
            continue
        if _is_sops(docs):
            continue
        rel = str(path.relative_to(REPO_ROOT))
        for doc in docs:
            _harvest(doc, rel, (), cases)
    unexpected = [p for p in unparseable if p not in KNOWN_UNPARSEABLE]
    assert not unexpected, (
        f"unparseable YAML in deploy tree (cannot audit crons): {unexpected} "
        f"— fix the file or extend KNOWN_UNPARSEABLE consciously"
    )
    return cases


def _audit_cases() -> list[tuple[str, str, str]]:
    """Full harvest; templated (${...}) values are skipped as non-literal."""
    return [c for c in collect_cron_expressions(DEPLOY_TREE) if "${" not in c[2]]


def test_walker_harvest_is_nontrivial():
    cases = _audit_cases()
    assert len(cases) >= MIN_HARVEST, (
        f"cron harvest fell to {len(cases)} expressions "
        f"(floor {MIN_HARVEST}) — the walker is likely skipping files"
    )


def test_walker_covers_longhorn_storage_app():
    # The #1905 site: if this pin breaks, the longhorn RecurringJobs are
    # no longer being audited (file moved/renamed/walker regression).
    cases = _audit_cases()
    assert any("apps/storage/longhorn" in loc for loc, _, _ in cases), (
        "no cron expressions harvested from kubernetes/apps/storage/longhorn"
    )


VALIDATOR_CASES = [
    # (expr, expected_error_substring or None)
    ("0 1 * * *", None),              # daily 01:00 — the #1905 corrected value
    ("0 0 * * 1", None),              # weekly Monday
    ("*/5 * * * *", None),
    ("0 */8 * * *", None),
    ("55 5 * * *", None),
    ("45 13 * * 1-5", None),          # dow range
    ("0 1 * * 0,2,4", None),          # dow list
    ("0 0 1 * *", None),
    ("30 4 1-15/3 * *", None),        # dom range with step
    ("0 0 12 * * *", None),           # CloudNative-PG seconds dialect
    ("59 0 12 * * *", None),
    ("@hourly", None),
    ("@every 168h", None),
    ("@midnight", None),
    ("0 1 * * 8", "out of range"),     # #1905's bug: dow 8 invalid (0-7)
    ("0 1 * * 07", None),             # zero-padded is numeric and in range
    ("61 * * * *", "out of range"),    # minute 61
    ("* 24 * * *", "out of range"),    # hour 24
    ("* * 0 * *", "out of range"),     # dom 0
    ("* * * 13 *", "out of range"),    # month 13
    ("* * * * 5-1", "descending"),     # inverted dow range
    ("* * * * * * *", "expected 5"),   # 7 fields
    ("not a cron", "expected 5"),
    ("*/0 * * * *", "invalid step"),
    ("@fortnightly", "unknown @-shorthand"),
    ("0 0 * * SUN", "non-numeric"),    # numeric-only by design (standard ranges)
]


@pytest.mark.parametrize(
    "expr,expected",
    VALIDATOR_CASES,
    ids=[expr.replace(" ", "_") + ("_ok" if expected is None else f"_{expected.replace(' ', '_')}") for expr, expected in VALIDATOR_CASES],
)
def test_validator(expr, expected):
    err = validate_cron(expr)
    if expected is None:
        assert err is None, f"{expr!r} should be valid, got: {err}"
    else:
        assert err is not None and expected in err, (
            f"{expr!r} should fail with {expected!r}, got: {err}"
        )


@pytest.mark.parametrize(
    "loc,key,expr",
    _audit_cases(),
    ids=[f"{Path(loc).name}:{expr}" for loc, _, expr in _audit_cases()],
)
def test_cron_expression_is_valid(loc, key, expr):
    err = validate_cron(expr)
    assert err is None, f"{loc} [{key}]: invalid cron {expr!r}: {err}"
