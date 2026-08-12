#!/usr/bin/env python3
"""Tablet count estimation and tenant per-node ceiling verification.

The model and its basis are documented in references/tablet-capacity.md:

  Tablets per table = base table partitions x subpartitions
              + Sum(local indexes) base table partitions x subpartitions
              + Sum(global indexes) that index's own partitions x subpartitions

  The ceiling applies **per OBServer node**, taking the smaller of two formulas:
      A = (MEMORY_SIZE/1GB) * _max_tablet_cnt_per_gb
      B = (MEMORY_SIZE * _storage_meta_memory_limit_percentage)/200MB * 20000
      per_node_limit = min(A, B)

  MEMORY_SIZE is "the memory of the user tenant's unit on that node", not the
  tenant's total spec (the Meta tenant takes roughly 1 GB). Per-node tablets
  ~= ceil(total tablets / unit_num).

  When GV$OB_TENANT_RESOURCE_LIMIT is queryable, its LIMIT_VALUE should be
  treated as authoritative; this script is only for upfront estimation during
  the design phase.

Usage:
    python3 estimate_tablets.py schema.json [--json]
    python3 estimate_tablets.py --self-test
    python3 estimate_tablets.py --print-example > schema.json

schema.json fields (--print-example prints valid JSON, no comments):
    compat_mode      "mysql"|"oracle"  determines the single-table partition ceiling;
                                       if missing, that item is judged unverified
                                       (MySQL: max_partition_num defaults to 8192, range [8192,65536])
                                       (Oracle: fixed at 65536, max_partition_num is **not used**)
    unit_memory_gb   number > 0    user tenant unit memory (**homogeneity assumption**); if missing, result=unverified
    unit_num         int > 0       units per Zone (homogeneity assumption); if missing, result=unverified
    units[]          optional, **use this for a heterogeneous Zone/Unit topology**,
                       overrides the two fields above when given:
                       {zone, memory_gb, tablet_share}
                       tablet_share is optional, defaults to an even split of 1/len(units);
                       the verdict takes the **worst node** (largest headroom_ratio), not the average
    max_tablet_cnt_per_gb                int, [1000, 50000), default 20000
    storage_meta_memory_limit_percentage number, [0, 50), default 20 (0 = no ceiling)
    max_partition_num                    int, [8192, 65536], default 8192, only meaningful in MySQL mode
    tables[]         required, non-empty array
      name           str
      partitions     int >= 1
      subpartitions  int >= 1 (default 1)
      local_indexes  int >= 0 (default 0)
      global_indexes[] {name, partitions >= 1, subpartitions >= 1}
"""
import json
import math
import sys

DEFAULT_MAX_TABLET_PER_GB = 20000   # _max_tablet_cnt_per_gb, product range [1000, 50000)
DEFAULT_META_MEM_PCT = 20           # _storage_meta_memory_limit_percentage, range [0, 50)
DEFAULT_MAX_PARTITION_NUM = 8192    # max_partition_num, MySQL-mode only, range [8192, 65536]
MAX_PARTITION_NUM_FLOOR = 8192      # product floor for this parameter (not 1)
MAX_PARTITION_NUM_CEIL = 65536      # product ceiling for this parameter
ORACLE_PARTITION_LIMIT = 65536      # fixed ceiling for Oracle mode; max_partition_num is not used
SAFE_PARTITION_LIMIT = 8192         # the "safe under both modes" threshold when compat_mode is unknown
COMPAT_MODES = ("mysql", "oracle")
MB_PER_GB = 1024
HEADROOM_WARN = 0.5                 # L2 empirical threshold, not a hard product limit

EXAMPLE = {
    "compat_mode": "mysql",
    "_note_heterogeneous": ("For heterogeneous Zones/Units, use the units[] field instead, "
                            "e.g.: \"units\": [{\"zone\":\"z1\",\"memory_gb\":8},"
                            "{\"zone\":\"z2\",\"memory_gb\":2}]; the verdict takes the worst node"),
    "unit_memory_gb": 8,
    "unit_num": 2,
    "max_tablet_cnt_per_gb": 20000,
    "storage_meta_memory_limit_percentage": 20,
    "max_partition_num": 8192,
    "tables": [
        {"name": "orders", "partitions": 6, "subpartitions": 1,
         "local_indexes": 3,
         "global_indexes": [{"name": "gidx_merchant", "partitions": 4}]},
        {"name": "order_items", "partitions": 12},
        {"name": "dim_currency", "partitions": 1},
    ],
}


class SchemaError(ValueError):
    """Invalid input. Never silently correct it — bad input must raise an error, not compute a passing result."""


def _num(d, key, path, *, required=False, default=None,
         minimum=None, maximum=None, exclusive_min=None, integer=False):
    if key not in d or d[key] is None:
        if required:
            raise SchemaError(f"{path}.{key} is required")
        return default
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SchemaError(f"{path}.{key} must be a number, got {type(v).__name__}")
    if integer and not float(v).is_integer():
        raise SchemaError(f"{path}.{key} must be an integer, got {v}")
    if integer:
        v = int(v)
    if exclusive_min is not None and v <= exclusive_min:
        raise SchemaError(f"{path}.{key} must be > {exclusive_min}, got {v}")
    if minimum is not None and v < minimum:
        raise SchemaError(f"{path}.{key} must be >= {minimum}, got {v}")
    if maximum is not None and v >= maximum:
        raise SchemaError(f"{path}.{key} must be < {maximum}, got {v}")
    return v


def validate(schema):
    """Validate and normalize the input; raise SchemaError immediately if invalid."""
    if not isinstance(schema, dict):
        raise SchemaError("top level must be a JSON object")

    tables = schema.get("tables")
    if not isinstance(tables, list) or not tables:
        raise SchemaError("tables must be a non-empty array")

    out = {
        # May be missing: if missing it's unverified — must not be papered over with a default
        "unit_memory_gb": _num(schema, "unit_memory_gb", "$", exclusive_min=0),
        "unit_num": _num(schema, "unit_num", "$", exclusive_min=0, integer=True),
        # Parameters with a product-defined value range: out of range raises immediately
        "max_tablet_cnt_per_gb": _num(
            schema, "max_tablet_cnt_per_gb", "$",
            default=DEFAULT_MAX_TABLET_PER_GB, minimum=1000, maximum=50000, integer=True),
        "storage_meta_memory_limit_percentage": _num(
            schema, "storage_meta_memory_limit_percentage", "$",
            default=DEFAULT_META_MEM_PCT, minimum=0, maximum=50),
        "max_partition_num": _num(
            schema, "max_partition_num", "$",
            default=DEFAULT_MAX_PARTITION_NUM,
            minimum=MAX_PARTITION_NUM_FLOOR, maximum=MAX_PARTITION_NUM_CEIL + 1,
            integer=True),
        "tables": [],
    }

    units = schema.get("units")
    if units is not None:
        if not isinstance(units, list) or not units:
            raise SchemaError("$.units must be a non-empty array")
        parsed, shares = [], []
        for i, u in enumerate(units):
            up = f"$.units[{i}]"
            if not isinstance(u, dict):
                raise SchemaError(f"{up} must be an object")
            zone = u.get("zone", f"zone{i}")
            if not isinstance(zone, str) or not zone.strip():
                raise SchemaError(f"{up}.zone must be a non-empty string")
            mem = _num(u, "memory_gb", up, required=True, exclusive_min=0)
            share = _num(u, "tablet_share", up, minimum=0, maximum=1.0000001)
            parsed.append({"zone": zone, "memory_gb": mem, "tablet_share": share})
            shares.append(share)
        given = [x for x in shares if x is not None]
        if given and len(given) != len(shares):
            raise SchemaError("$.units' tablet_share must be either all given or all omitted")
        if given and abs(sum(given) - 1.0) > 1e-6:
            raise SchemaError(f"$.units' tablet_share must sum to 1, got {sum(given)}")
        if not given:
            for u in parsed:
                u["tablet_share"] = 1.0 / len(parsed)
        out["units"] = parsed
    else:
        out["units"] = None

    cm = schema.get("compat_mode")
    if cm is not None:
        if not isinstance(cm, str) or cm.lower() not in COMPAT_MODES:
            raise SchemaError(
                f"$.compat_mode must be one of {COMPAT_MODES}, got {cm!r}")
        cm = cm.lower()
    out["compat_mode"] = cm

    seen = set()
    for i, t in enumerate(tables):
        path = f"$.tables[{i}]"
        if not isinstance(t, dict):
            raise SchemaError(f"{path} must be an object")
        name = t.get("name", f"table_{i}")
        if not isinstance(name, str) or not name.strip():
            raise SchemaError(f"{path}.name must be a non-empty string")
        if name in seen:
            raise SchemaError(f"{path}.name duplicated: {name!r}")
        seen.add(name)

        gidx = t.get("global_indexes", [])
        if not isinstance(gidx, list):
            raise SchemaError(f"{path}.global_indexes must be an array")
        globals_ = []
        for j, g in enumerate(gidx):
            gp = f"{path}.global_indexes[{j}]"
            if not isinstance(g, dict):
                raise SchemaError(f"{gp} must be an object")
            globals_.append({
                "name": g.get("name", f"gidx_{j}"),
                "partitions": _num(g, "partitions", gp, default=1, minimum=1, integer=True),
                "subpartitions": _num(g, "subpartitions", gp, default=1, minimum=1, integer=True),
            })

        out["tables"].append({
            "name": name,
            "partitions": _num(t, "partitions", path, default=1, minimum=1, integer=True),
            "subpartitions": _num(t, "subpartitions", path, default=1, minimum=1, integer=True),
            "local_indexes": _num(t, "local_indexes", path, default=0, minimum=0, integer=True),
            "global_indexes": globals_,
        })
    return out


def table_tablets(t):
    """Return this table's tablet breakdown, plus the partition-count list for
    **every independently partitioned physical object**.

    The partition-count ceiling is a limit on **each partitioned object
    individually**, not on "the table as a whole":
      * base table              -> its own partitions x subpartitions
      * each global index       -> may have its **own independent partitioning
                                    rule**, must be checked individually
      * local indexes / PK index -> inherit the base table's partitioning; if the
                                    base table complies, they necessarily comply
                                    too, no need to check separately
      * LOB auxiliary objects   -> follow the base table's partitioning, same
                                    reasoning, not checked separately
    Checking only the base table would miss a real violation such as "base
    table has 1 partition + a global index has 9000 partitions".
    """
    base = t["partitions"] * t["subpartitions"]
    local = t["local_indexes"] * base
    glob = sum(g["partitions"] * g["subpartitions"] for g in t["global_indexes"])
    objects = [{"object": t["name"], "kind": "base_table", "partition_count": base}]
    for g in t["global_indexes"]:
        objects.append({
            "object": f"{t['name']}.{g['name']}",
            "kind": "global_index",
            "partition_count": g["partitions"] * g["subpartitions"]})
    return {"table": t["name"], "partition_count": base,
            "base": base, "local_index": local, "global_index": glob,
            "total": base + local + glob,
            "partitioned_objects": objects}


def per_node_limit(unit_memory_gb, max_per_gb, meta_pct):
    """Return (limit, A, B, binding). All are None when unit_memory_gb is None."""
    if not unit_memory_gb:
        return None, None, None, None
    a = int(unit_memory_gb * max_per_gb)
    if meta_pct == 0:                       # 0 means no ceiling -> formula B does not apply
        return a, a, None, "A"
    mem_mb = unit_memory_gb * MB_PER_GB
    b = int(mem_mb * (meta_pct / 100.0) / 200.0 * 20000)
    return (a, a, b, "A") if a <= b else (b, a, b, "B")


def estimate(schema):
    s = validate(schema)
    rows = [table_tablets(t) for t in s["tables"]]
    total = sum(r["total"] for r in rows)

    assumptions = []
    for key, default, label in (
        ("max_tablet_cnt_per_gb", DEFAULT_MAX_TABLET_PER_GB, "_max_tablet_cnt_per_gb"),
        ("storage_meta_memory_limit_percentage", DEFAULT_META_MEM_PCT,
         "_storage_meta_memory_limit_percentage"),
        ("max_partition_num", DEFAULT_MAX_PARTITION_NUM, "max_partition_num"),
    ):
        if key not in schema or schema[key] is None:
            if key == "max_partition_num" and s["compat_mode"] == "oracle":
                continue          # Oracle mode does not use this parameter, so it is not an assumption
            assumptions.append(f"{label} not provided, using default {default}")
    if s["compat_mode"] is None:
        assumptions.append(
            "compat_mode not provided; the single-table partition ceiling is judged "
            "against the safe floor of 8192 for both modes; "
            "8193-65536 outputs unverified")

    mem, units = s["unit_memory_gb"], s["unit_num"]
    unit_list = s["units"]
    node_detail = []

    if unit_list:
        # Heterogeneous Zone/Unit: compute the ceiling and usage per node
        # individually, the verdict takes the **worst node**.
        # Using the average would hide the real failure mode of "the
        # small-memory node blows up first".
        for u in unit_list:
            l, a, b, bd = per_node_limit(
                u["memory_gb"], s["max_tablet_cnt_per_gb"],
                s["storage_meta_memory_limit_percentage"])
            cnt = math.ceil(total * u["tablet_share"])
            node_detail.append({
                "zone": u["zone"], "memory_gb": u["memory_gb"],
                "tablet_share": u["tablet_share"], "estimated_tablets": cnt,
                "per_node_limit": l, "formula_a": a, "formula_b": b,
                "binding_formula": bd,
                "headroom_ratio": (cnt / l) if l else None})
        worst = max(node_detail, key=lambda d: d["headroom_ratio"])
        limit, fa, fb, binding = (worst["per_node_limit"], worst["formula_a"],
                                  worst["formula_b"], worst["binding_formula"])
        per_node, ratio = worst["estimated_tablets"], worst["headroom_ratio"]
        mem = worst["memory_gb"]
    else:
        limit, fa, fb, binding = per_node_limit(
            mem, s["max_tablet_cnt_per_gb"], s["storage_meta_memory_limit_percentage"])
        per_node = math.ceil(total / units) if units else None
        ratio = (per_node / limit) if (limit and per_node) else None

    # The single-table partition ceiling **depends on compat mode**:
    #   mysql  -> max_partition_num (default 8192, tunable up to 65536)
    #   oracle -> fixed at 65536, max_partition_num is not used
    #   unknown -> only judged pass when "both are <= 8192" (safe under both
    #             modes); falling in 8193..65536 cannot be determined, outputs
    #             unverified instead of a false fail
    cm = s["compat_mode"]
    if cm == "mysql":
        part_limit, part_limit_basis = s["max_partition_num"], "max_partition_num"
    elif cm == "oracle":
        part_limit, part_limit_basis = ORACLE_PARTITION_LIMIT, "oracle_fixed_65536"
    else:
        part_limit, part_limit_basis = SAFE_PARTITION_LIMIT, "compat_mode_unknown_safe_floor"

    # Judge each **partitioned object** individually (base table + each
    # independently partitioned global index), not just the base table
    all_objects = [o for r in rows for o in r["partitioned_objects"]]

    def label(o):
        return f"{o['object']}({o['kind']}, {o['partition_count']})"

    over_part = [label(o) for o in all_objects
                 if o["partition_count"] > part_limit]
    if cm is None and over_part:
        # unknown mode and above the safe floor -> cannot assert a violation
        ambiguous_part = [label(o) for o in all_objects
                          if SAFE_PARTITION_LIMIT < o["partition_count"]
                          <= ORACLE_PARTITION_LIMIT]
        hard_over = [label(o) for o in all_objects
                     if o["partition_count"] > ORACLE_PARTITION_LIMIT]
        over_part = hard_over          # exceeding 65536 is a violation under both modes
        part_result = "fail" if hard_over else "unverified"
    else:
        ambiguous_part = []
        part_result = "fail" if over_part else "pass"

    # Verdict priority: **any definite violation > unknown > pass**.
    # The reverse (unknown overriding a definite fail) would report a real
    # over-limit as "cannot be determined" — a dangerous false negative.
    definite_fail = (part_result == "fail") or (
        limit is not None and per_node is not None and per_node > limit)
    has_unknown = (limit is None or per_node is None
                   or part_result == "unverified")

    if definite_fail:
        result = "fail"
    elif has_unknown:
        result = "unverified"                 # missing input must not be forced into a pass via defaults
    elif ratio > HEADROOM_WARN:
        result = "pass_with_warning"
    else:
        result = "pass"

    if unit_list:
        missing = []          # units[] already provides the full topology
    else:
        missing = [k for k, v in (("unit_memory_gb", s["unit_memory_gb"]),
                                  ("unit_num", units)) if not v]

    return {"breakdown": rows, "estimated_total": total,
            "unit_memory_gb": mem, "unit_num": units,
            "max_tablet_cnt_per_gb": s["max_tablet_cnt_per_gb"],
            "storage_meta_memory_limit_percentage":
                s["storage_meta_memory_limit_percentage"],
            "formula_a": fa, "formula_b": fb, "binding_formula": binding,
            "per_node_limit": limit, "estimated_per_node": per_node,
            "headroom_ratio": ratio,
            "topology": "heterogeneous" if unit_list else "homogeneous",
            "worst_node": (max(node_detail, key=lambda d: d["headroom_ratio"])["zone"]
                           if node_detail else None),
            "node_detail": node_detail,
            "compat_mode": cm,
            "max_partition_num": s["max_partition_num"],
            "partition_limit": part_limit,
            "partition_limit_basis": part_limit_basis,
            "partition_limit_result": part_result,
            "partitioned_object_count": len(all_objects),
            "objects_over_partition_limit": over_part,
            "objects_ambiguous_partition_limit": ambiguous_part,
            "missing_inputs": missing,
            "assumptions": assumptions, "result": result}


def render(rep):
    w = max([len(r["table"]) for r in rep["breakdown"]] + [5])
    print(f"{'table'.ljust(w)}  {'base':>6} {'local':>6} {'global':>7} {'total':>7}")
    for r in rep["breakdown"]:
        print(f"{r['table'].ljust(w)}  {r['base']:>6} {r['local_index']:>6} "
              f"{r['global_index']:>7} {r['total']:>7}")
    print("-" * (w + 32))
    print(f"{'TOTAL'.ljust(w)}  {'':>6} {'':>6} {'':>7} {rep['estimated_total']:>7}")

    if rep["per_node_limit"] is None:
        print(f"\nMissing input {rep['missing_inputs']} -> cannot determine the per-node ceiling")
    else:
        fb = rep["formula_b"] if rep["formula_b"] is not None else "n/a (pct=0)"
        print(f"\nFormula A = {rep['unit_memory_gb']} GB x "
              f"{rep['max_tablet_cnt_per_gb']} = {rep['formula_a']}")
        print(f"Formula B = {rep['unit_memory_gb']}GB x "
              f"{rep['storage_meta_memory_limit_percentage']}% / 200MB x 20000 = {fb}")
        print(f"per_node_limit = min(A, B) = {rep['per_node_limit']}  "
              f"(binding formula {rep['binding_formula']})")
        if rep["topology"] == "homogeneous":
            print(f"Per-node estimate = ceil({rep['estimated_total']} / {rep['unit_num']}) "
                  f"= {rep['estimated_per_node']}")
        else:
            print(f"Worst-node estimate = {rep['estimated_per_node']}"
                  f" (see node detail table below)")
        print(f"headroom_ratio = {rep['headroom_ratio']:.4f}")
    if rep["node_detail"]:
        print(f"\nTopology: heterogeneous (verdict takes the worst node {rep['worst_node']})")
        w = max(len(d["zone"]) for d in rep["node_detail"])
        print(f"  {'zone'.ljust(w)}  {'memGB':>6} {'share':>6} "
              f"{'tablets':>8} {'limit':>8} {'ratio':>7}  bind")
        for d in rep["node_detail"]:
            mark = " <-- worst" if d["zone"] == rep["worst_node"] else ""
            print(f"  {d['zone'].ljust(w)}  {d['memory_gb']:>6} "
                  f"{d['tablet_share']:>6.3f} {d['estimated_tablets']:>8} "
                  f"{d['per_node_limit']:>8} {d['headroom_ratio']:>7.4f}  "
                  f"{d['binding_formula']}{mark}")

    print(f"\nPartition ceiling = {rep['partition_limit']} "
          f"(based on {rep['partition_limit_basis']}, compat_mode={rep['compat_mode']}) "
          f"-> {rep['partition_limit_result']}")
    print(f"          Checked partitioned objects: {rep['partitioned_object_count']}"
          f" (base table + independently partitioned global indexes)")
    if rep["objects_over_partition_limit"]:
        print(f"[L0] Objects over the partition ceiling: {rep['objects_over_partition_limit']}")
    if rep["objects_ambiguous_partition_limit"]:
        print(f"[unverified] Partition count falls in 8193-65536 with mode unknown, cannot determine: "
              f"{rep['objects_ambiguous_partition_limit']}")
    for a in rep["assumptions"]:
        print(f"[assumed] {a}")
    print(f"result: {rep['result']}")


def self_test():
    passed = 0

    def check(cond, msg):
        nonlocal passed
        assert cond, msg
        passed += 1

    base = {"unit_memory_gb": 8, "unit_num": 2, "tables": [
        {"name": "orders", "partitions": 6, "local_indexes": 3,
         "global_indexes": [{"name": "g1", "partitions": 4}]},
        {"name": "order_items", "partitions": 12},
        {"name": "dim_currency", "partitions": 1}]}

    # 1) Summation formula (cases.md B7): (6 + 3*6 + 4) + 12 + 1 = 41
    r = estimate(base)
    check(r["estimated_total"] == 41, r["estimated_total"])
    check(r["estimated_per_node"] == 21, r["estimated_per_node"])

    # 2) With default parameters, A=160000 < B=163840, A is binding
    check((r["formula_a"], r["formula_b"]) == (160000, 163840), r)
    check(r["binding_formula"] == "A" and r["per_node_limit"] == 160000
          and r["result"] == "pass", r)

    # 3) Raise _max_tablet_cnt_per_gb -> formula B becomes the bottleneck (min must take effect, cases.md B16)
    r = estimate(dict(base, max_tablet_cnt_per_gb=50000 - 1))
    check(r["binding_formula"] == "B" and r["per_node_limit"] == 163840, r)

    # 4) Lower the metadata memory percentage -> B gets smaller
    r = estimate(dict(base, storage_meta_memory_limit_percentage=5))
    check(r["binding_formula"] == "B" and r["per_node_limit"] == 40960, r["per_node_limit"])

    # 5) pct=0 means no ceiling -> only A is used
    r = estimate(dict(base, storage_meta_memory_limit_percentage=0))
    check(r["formula_b"] is None and r["per_node_limit"] == 160000, r)

    # 6) Missing unit memory / unit count -> unverified
    r = estimate({"tables": [{"name": "t", "partitions": 4,
                              "subpartitions": 8, "local_indexes": 2}]})
    check(r["estimated_total"] == 96, r["estimated_total"])
    check(r["result"] == "unverified"
          and r["missing_inputs"] == ["unit_memory_gb", "unit_num"], r)

    # 7) Small tenant over the limit
    r = estimate({"unit_memory_gb": 1, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 50000}]})
    check(r["per_node_limit"] == 20000 and r["result"] == "fail", r)

    # 8) MySQL mode: 9000 partitions exceeds the max_partition_num default of 8192 -> fail
    r = estimate({"compat_mode": "mysql", "unit_memory_gb": 8, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 9000}]})
    check(r["result"] == "fail"
          and r["objects_over_partition_limit"] == ["t(base_table, 9000)"], r)
    check(r["partition_limit"] == 8192
          and r["partition_limit_basis"] == "max_partition_num", r)

    # 9) Subpartitions count toward the single-table partition total: 100*100 = 10000 > 8192 (cases.md I10)
    r = estimate({"compat_mode": "mysql", "unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 100, "subpartitions": 100}]})
    check(r["result"] == "fail", r["result"])

    # 10) **Oracle mode must likewise allow 10000 partitions** (ceiling fixed at
    #     65536, max_partition_num not used). This is the bug fixed in this
    #     round: it used to wrongly reject a valid Oracle design using 8192
    r = estimate({"compat_mode": "oracle", "unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 10000}]})
    check(r["partition_limit"] == 65536
          and r["partition_limit_basis"] == "oracle_fixed_65536", r)
    check(r["result"] == "pass" and r["objects_over_partition_limit"] == [], r)

    # 11) Oracle mode should still fail above 65536
    r = estimate({"compat_mode": "oracle", "unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 70000}]})
    check(r["result"] == "fail", r["result"])

    # 12) compat_mode unknown + 10000 partitions -> unverified (neither a false fail nor a false pass)
    r = estimate({"unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 10000}]})
    check(r["partition_limit_result"] == "unverified", r)
    check(r["result"] == "unverified"
          and r["objects_ambiguous_partition_limit"] == ["t(base_table, 10000)"], r)

    # 13) compat_mode unknown but above 65536 -> a violation under both modes, can fail directly
    r = estimate({"unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 70000}]})
    check(r["result"] == "fail"
          and r["objects_over_partition_limit"] == ["t(base_table, 70000)"], r)

    # 14) compat_mode unknown but both <= 8192 -> safe under both modes, can judge pass
    r = estimate({"unit_memory_gb": 8, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 8000}]})
    check(r["partition_limit_result"] == "pass" and r["result"] == "pass", r)

    # 15a) **A global index's own partition count must be limited
    #      individually** (a missed check found in this round's review).
    #      The base table has only 1 partition, but the global index has
    #      9000 partitions -- must fail in MySQL mode
    r = estimate({"compat_mode": "mysql", "unit_memory_gb": 8, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 1,
                              "global_indexes": [{"name": "g", "partitions": 9000}]}]})
    check(r["estimated_total"] == 9001, r["estimated_total"])
    check(r["partition_limit_result"] == "fail",
          f"global index with 9000 partitions was missed: {r['partition_limit_result']}")
    check(r["result"] == "fail", r["result"])
    check(r["objects_over_partition_limit"] == ["t.g(global_index, 9000)"],
          r["objects_over_partition_limit"])
    check(r["partitioned_object_count"] == 2, r["partitioned_object_count"])

    # 15b) The same global index is legal under Oracle mode (ceiling 65536)
    r = estimate({"compat_mode": "oracle", "unit_memory_gb": 8, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 1,
                              "global_indexes": [{"name": "g", "partitions": 9000}]}]})
    check(r["partition_limit_result"] == "pass", r["partition_limit_result"])

    # 15c) A global index's subpartitions also count: 100 x 100 = 10000 > 8192
    r = estimate({"compat_mode": "mysql", "unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 1,
                              "global_indexes": [{"name": "g", "partitions": 100,
                                                  "subpartitions": 100}]}]})
    check(r["partition_limit_result"] == "fail", r)

    # 15d) Mode unknown + global index with 9000 partitions -> unverified (not a false fail)
    r = estimate({"unit_memory_gb": 8, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 1,
                              "global_indexes": [{"name": "g", "partitions": 9000}]}]})
    check(r["partition_limit_result"] == "unverified", r)
    check(r["objects_ambiguous_partition_limit"] == ["t.g(global_index, 9000)"], r)

    # 15e) Local indexes are not checked individually (they inherit the base
    #      table's partitioning; if the base table complies, they comply too)
    r = estimate({"compat_mode": "mysql", "unit_memory_gb": 64, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 8000, "local_indexes": 5}]})
    check(r["partition_limit_result"] == "pass", r["partition_limit_result"])
    check(r["partitioned_object_count"] == 1, r["partitioned_object_count"])

    # 16) Priority: tablet count is definitely over the limit + partition
    #     count is unknown -> must still be fail, must not be masked by unverified
    r = estimate({"unit_memory_gb": 1, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 50000}]})
    check(r["partition_limit_result"] == "unverified", r)
    check(r["result"] == "fail", f"a definite tablet over-limit was masked by unverified: {r['result']}")

    # 16b) Heterogeneous Zone/Unit: verdict takes the worst node, must not let
    #      the average mask a small node blowing up
    #      z1=64GB(limit 1.28M) / z2=1GB(limit 20000), total 30000 split evenly -> 15000 each
    #      looks fine on average; z2's 15000/20000 = 0.75 already crosses the warning line
    r = estimate({"compat_mode": "mysql",
                  "units": [{"zone": "z1", "memory_gb": 64},
                            {"zone": "z2", "memory_gb": 1}],
                  "tables": [{"name": "t", "partitions": 6000, "local_indexes": 4}]})
    check(r["topology"] == "heterogeneous", r["topology"])
    check(r["worst_node"] == "z2", r["worst_node"])
    check(r["per_node_limit"] == 20000, r["per_node_limit"])
    check(r["estimated_per_node"] == 15000, r["estimated_per_node"])
    check(r["result"] == "pass_with_warning", r["result"])
    check(len(r["node_detail"]) == 2, r["node_detail"])

    # 16c) The worst node genuinely blows up -> fail (instead of being averaged out by the large node)
    r = estimate({"compat_mode": "mysql",
                  "units": [{"zone": "z1", "memory_gb": 64},
                            {"zone": "z2", "memory_gb": 1}],
                  "tables": [{"name": "t", "partitions": 8000, "local_indexes": 9}]})
    check(r["worst_node"] == "z2" and r["result"] == "fail", r["result"])

    # 16d) Explicit tablet_share (skewed distribution)
    r = estimate({"compat_mode": "mysql",
                  "units": [{"zone": "z1", "memory_gb": 8, "tablet_share": 0.9},
                            {"zone": "z2", "memory_gb": 8, "tablet_share": 0.1}],
                  "tables": [{"name": "t", "partitions": 1000}]})
    check(r["worst_node"] == "z1" and r["estimated_per_node"] == 900, r)

    # 16e) tablet_share not summing to 1 -> error
    for bad in ([{"zone": "z1", "memory_gb": 8, "tablet_share": 0.5},
                 {"zone": "z2", "memory_gb": 8, "tablet_share": 0.2}],
                [{"zone": "z1", "memory_gb": 8, "tablet_share": 0.5},
                 {"zone": "z2", "memory_gb": 8}]):
        try:
            estimate({"units": bad, "tables": [{"name": "t", "partitions": 4}]})
        except SchemaError:
            passed += 1
        else:
            raise AssertionError(f"tablet_share validation missed: {bad}")

    # 16f) units missing memory_gb -> error
    try:
        estimate({"units": [{"zone": "z1"}], "tables": [{"name": "t", "partitions": 4}]})
    except SchemaError:
        passed += 1
    else:
        raise AssertionError("units.memory_gb required-check missing")

    # 17) Oracle mode does not list the missing max_partition_num as an assumption
    r = estimate({"compat_mode": "oracle", "unit_memory_gb": 8, "unit_num": 1,
                  "tables": [{"name": "t", "partitions": 10}]})
    check(not any("max_partition_num" in a for a in r["assumptions"]), r["assumptions"])

    # ---- Input validation: every one of the following must raise SchemaError, not compute a result ----
    bad_cases = [
        ({"unit_memory_gb": 8, "unit_num": -2, "tables": [{"name": "t", "partitions": 4}]},
         "unit_num negative"),
        ({"unit_memory_gb": 0, "unit_num": 1, "tables": [{"name": "t", "partitions": 4}]},
         "unit_memory_gb is 0"),
        ({"unit_memory_gb": -8, "unit_num": 1, "tables": [{"name": "t", "partitions": 4}]},
         "unit_memory_gb negative"),
        ({"unit_num": 1.5, "tables": [{"name": "t", "partitions": 4}]},
         "unit_num not an integer"),
        ({"tables": [{"name": "t", "partitions": 0}]}, "partitions is 0"),
        ({"tables": [{"name": "t", "partitions": -4}]}, "partitions negative"),
        ({"tables": [{"name": "t", "partitions": 4, "subpartitions": 0}]},
         "subpartitions is 0"),
        ({"tables": [{"name": "t", "partitions": 4, "local_indexes": -1}]},
         "local_indexes negative"),
        ({"tables": [{"name": "t", "partitions": 4, "local_indexes": 1.5}]},
         "local_indexes not an integer"),
        ({"tables": [{"name": "t", "partitions": 4,
                      "global_indexes": [{"partitions": 0}]}]}, "global index partitions is 0"),
        ({"tables": [{"name": "t", "partitions": 4, "global_indexes": {}}]},
         "global_indexes not an array"),
        ({"tables": []}, "tables is empty"),
        ({"tables": "x"}, "tables not an array"),
        ({}, "missing tables"),
        ("not a dict", "top level not an object"),
        ({"tables": [{"name": "", "partitions": 4}]}, "name is empty string"),
        ({"tables": [{"name": "t", "partitions": 4}, {"name": "t", "partitions": 5}]},
         "name duplicated"),
        ({"max_tablet_cnt_per_gb": 999, "tables": [{"name": "t", "partitions": 4}]},
         "_max_tablet_cnt_per_gb below the product floor of 1000"),
        ({"max_tablet_cnt_per_gb": 50000, "tables": [{"name": "t", "partitions": 4}]},
         "_max_tablet_cnt_per_gb reaches the product ceiling of 50000 (range is right-open)"),
        ({"storage_meta_memory_limit_percentage": 50,
          "tables": [{"name": "t", "partitions": 4}]},
         "metadata memory percentage reaches the ceiling of 50 (range is right-open)"),
        ({"storage_meta_memory_limit_percentage": -1,
          "tables": [{"name": "t", "partitions": 4}]}, "metadata memory percentage negative"),
        ({"max_partition_num": 0, "tables": [{"name": "t", "partitions": 4}]},
         "max_partition_num is 0"),
        ({"max_partition_num": 4096, "tables": [{"name": "t", "partitions": 4}]},
         "max_partition_num below the product floor of 8192"),
        ({"max_partition_num": 65537, "tables": [{"name": "t", "partitions": 4}]},
         "max_partition_num exceeds the product ceiling of 65536"),
        ({"compat_mode": "postgres", "tables": [{"name": "t", "partitions": 4}]},
         "compat_mode has an invalid value"),
        ({"compat_mode": 1, "tables": [{"name": "t", "partitions": 4}]},
         "compat_mode not a string"),
        ({"unit_memory_gb": True, "tables": [{"name": "t", "partitions": 4}]},
         "boolean treated as a number"),
        ({"tables": [{"name": "t", "partitions": "4"}]}, "partitions is a string"),
    ]
    for bad, label in bad_cases:
        try:
            estimate(bad)
        except SchemaError:
            passed += 1
        else:
            raise AssertionError(f"input validation missed: {label} -> {bad!r}")

    # --print-example's output must be valid JSON acceptable to json.load
    reparsed = json.loads(json.dumps(EXAMPLE))
    check(estimate(reparsed)["estimated_total"] == 41, "example schema is unusable")

    print(f"self-test: {passed}/{passed} passed "
          f"({len(bad_cases)} input validation cases)")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] == "--self-test":
        self_test()
        return 0
    if args[0] == "--print-example":
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    try:
        with open(args[0], encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}", file=sys.stderr)
        print("hint: use --print-example to generate a valid template (JSON does not support comments)",
              file=sys.stderr)
        return 2
    try:
        rep = estimate(schema)
    except SchemaError as e:
        print(f"invalid input: {e}", file=sys.stderr)
        return 2
    render(rep)
    if "--json" in args:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 1 if rep["result"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
