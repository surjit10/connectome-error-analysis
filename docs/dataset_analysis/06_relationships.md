# 06 — Relationships

> Defines all primary keys, foreign keys, one-to-many relationships, and join paths across every file in every dataset.

---

## 6.1 Relationship Diagram (All Datasets)

```
neurons.csv.gz
    │
    │  PK: root_id / Root ID
    │
    ├────────────────────────────────────────────────────────┐
    │                                                        │
    ▼ (FK: pre_root_id)                    ▼ (FK: post_root_id)
connections_princeton.csv.gz
    PK: (pre_root_id, post_root_id, neuropil)
```

For FAFB, additional joins exist:

```
neurons.csv.gz          classification.csv.gz       consolidated_cell_types.csv.gz
    │                        │                              │
    │  PK: root_id           │  PK: root_id                │  PK: root_id
    │                        │                              │
    └────────────────────────┴──────────────────────────────┘
              JOIN ON root_id → FAFB Combined Neuron Table
                              │
              ▼ (FK: pre_root_id / post_root_id)
    connections_princeton.csv.gz
```

---

## 6.2 Primary Keys

### neurons.csv.gz

| Dataset | PK Column | Raw Name | Uniqueness Confirmed |
|---------|----------|---------|---------------------|
| BANC | `root_id` | `Root ID` | ✓ (0 duplicates) |
| FAFB | `root_id` | `root_id` | ✓ (0 duplicates) |
| MANC | `root_id` | `Root ID` | ✓ (0 duplicates) |
| MAOL | `root_id` | `Root ID` | ✓ (0 duplicates) |
| MCNS | `root_id` | `Root ID` | ✓ (0 duplicates) |

**All neuron tables have unique root_id.** No deduplication is needed.

### connections_princeton.csv.gz

| Dataset | Natural PK | Uniqueness |
|---------|-----------|-----------|
| BANC | `(pre_root_id, post_root_id, neuropil)` | ✓ (0 duplicates) |
| FAFB | `(pre_root_id, post_root_id, neuropil)` | ✓ (0 duplicates) |
| MANC | `(pre_root_id, post_root_id, neuropil)` | ✓ (0 duplicates) |
| MAOL | `(pre_root_id, post_root_id, neuropil)` | ✓ (0 duplicates) |
| MCNS | `(pre_root_id, post_root_id, neuropil)` | ✓ (0 duplicates) |

> Note: The `(pre_root_id, post_root_id)` pair alone is **NOT** unique — the same neuron pair can have synapses in multiple neuropil regions. The composite triplet is the natural key.

### FAFB classification.csv.gz

| PK Column | Uniqueness |
|----------|-----------|
| `root_id` | ✓ (0 duplicates; row count matches neurons.csv exactly) |

### FAFB consolidated_cell_types.csv.gz

| PK Column | Uniqueness |
|----------|-----------|
| `root_id` | ✓ (0 duplicates; 928 fewer rows than neurons.csv — those neurons are unclassified) |

---

## 6.3 Foreign Keys

### connections → neurons (pre_root_id)

```
connections_princeton.csv.gz.pre_root_id
    →  neurons.csv.gz.root_id
```

**Relationship**: Many-to-one (many connections per neuron)  
**Referential integrity**: Not formally enforced in CSV format.  
**Uncertainty**: Whether every `pre_root_id` in connections has a matching row in neurons.csv has **not been verified** (full join would require loading both files simultaneously — a heavy operation). The loader should optionally validate this and report missing references.

### connections → neurons (post_root_id)

```
connections_princeton.csv.gz.post_root_id
    →  neurons.csv.gz.root_id
```

**Relationship**: Many-to-one  
**Same referential integrity caveat as above.**

### FAFB classification → neurons

```
classification.csv.gz.root_id
    →  neurons.csv.gz.root_id
```

**Relationship**: One-to-one (same neuron set)  
**Row count match**: 139,255 = 139,255 ✓ Complete join, no orphan rows expected.

### FAFB consolidated_cell_types → neurons

```
consolidated_cell_types.csv.gz.root_id
    →  neurons.csv.gz.root_id
```

**Relationship**: One-to-one (but 928 neurons unclassified)  
**Left join behavior**: 928 neurons from neurons.csv will have NaN after the join.

---

## 6.4 One-to-Many Relationships

### Neuron → Connections (outgoing)

One neuron (as presynaptic) connects to many postsynaptic neurons.

```
neurons.root_id  ←  1:N  →  connections.pre_root_id
```

### Neuron → Connections (incoming)

One neuron (as postsynaptic) receives from many presynaptic neurons.

```
neurons.root_id  ←  1:N  →  connections.post_root_id
```

### Connection Pair → Neuropil Regions

One `(pre, post)` neuron pair can have synapses in multiple neuropil regions.

```
(pre_root_id, post_root_id)  ←  1:N  →  neuropil (within connections table)
```

This means the connections table is at neuropil-level granularity, not neuron-pair granularity. For graph construction, the loader must decide whether to:
- **Keep neuropil-level edges** (multi-edge graph): one edge per `(pre, post, neuropil)` row
- **Aggregate to neuron-pair edges** (simple graph): `sum(syn_count)` grouped by `(pre, post)`

---

## 6.5 Lookup Relationships

The following columns in the neuron table act as categorical lookups but no separate lookup table file is provided. The valid values must be inferred from the data:

| Column | Acts As | Notes |
|--------|---------|-------|
| `flow` | Categorical enum | Values: `afferent`, `intrinsic`, `efferent` |
| `super_class` | Categorical lookup | Dataset-specific values |
| `class_` | Categorical lookup | Dataset-specific values |
| `sub_class` | Categorical lookup | Dataset-specific values |
| `soma_side` | Categorical enum | Values: `left`, `right`, and bilateral variants |
| `predicted_nt_type` | Categorical enum | Values: `ACH`, `GABA`, `GLUT`, `DA`, `SER`, `OCT` |
| `neuropil` | Categorical lookup | Dataset-specific region codes |

No separate taxonomy or ontology files were found in the dataset directories. The framework must derive valid categorical values from the data at load time.

---

## 6.6 FAFB Complete Join Path

For FAFB to produce a full neuron table equivalent to the Princeton schema, the following join is required:

```
Step 1:  neurons.csv.gz  (root_id, group, nt_type, nt_type_score, da_avg, ...)
Step 2:  LEFT JOIN classification.csv.gz ON root_id
         → adds: flow, super_class, class, sub_class, hemilineage, side, nerve
Step 3:  LEFT JOIN consolidated_cell_types.csv.gz ON root_id
         → adds: primary_type, additional_type(s)
Step 4:  Rename columns to canonical names

Result:  FAFB Combined Neuron Table (same structure as Princeton neurons output)
```

After this join, `connections_princeton.csv.gz.pre_root_id` and `.post_root_id` reference `root_id` in the combined neuron table.

---

## 6.7 Cross-Dataset Relationships

There are **no cross-dataset relationships**. Neuron IDs are dataset-scoped and do not reference each other. The framework treats each dataset as a fully independent graph.

The scientific cross-dataset comparison (Phase 005+) operates on derived graph metrics (degree distributions, centrality scores, etc.), not on raw neuron IDs.
