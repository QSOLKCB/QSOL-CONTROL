# QSOL-CONTROL Lattice Memory

## Name

**3×3×3 Sierpinski-derived lattice memory**

The word `derived` is important. CONTROL uses recursive 3-way partitioning and Sierpinski-inspired addressing as an information architecture. It does not claim the datastore is literally a Sierpinski triangle or that AI cognition occupies these coordinates.

## Why use geometry at all?

The geometry gives future humans and AIs a compact deterministic way to answer:

- what kind of record is this?
- what epistemic role does it have?
- what temporal role does it have?
- how do I traverse a bounded subset without loading everything?
- how can the same addressing convention survive different storage engines?

## Top-level lattice

There are 27 logical cells:

```text
3 information roles
× 3 epistemic roles
× 3 temporal roles
= 27 cells
```

### X — information role

```text
0 question
1 response
2 evidence
```

### Y — epistemic role

```text
0 observed
1 derived
2 unresolved
```

### Z — temporal role

```text
0 current
1 historical
2 recovery
```

## Address form

```text
L[x,y,z]
```

Examples:

```text
L[0,1,0]  current derived question/request representation
L[1,1,0]  current derived response such as Council synthesis
L[2,0,0]  current observed evidence reference
L[2,2,0]  current unresolved evidence gap
L[1,1,1]  historical derived response
L[2,0,2]  recovery-oriented observed evidence package
```

## Recursive addressing

A future profile may subdivide a cell:

```text
L[2,1,0]/L[0,2,1]
```

Recursion is allowed only when:

- the storage profile is versioned;
- the child assignment is deterministic from recorded metadata;
- maximum depth is bounded;
- the same record does not receive conflicting canonical addresses under the same profile;
- traversal cannot become an unbounded resource attack.

## Record identity

A lattice address is an index, not an identity.

Every persistent record should have a content-bound ID independently of its address, for example:

```text
sha256:<canonical-record-hash>
```

The following must remain independent:

```text
content identity
lattice address
source/provenance
lineage
canonical/evidence status
```

## Interaction storage

One CONTROL run may produce multiple records distributed across cells:

```text
question record             -> question cell
ORACLE observation refs     -> evidence/observed cell
unknown evidence gaps       -> evidence/unresolved cell
Council outputs             -> response/derived cell
model-state records         -> linked metadata records
historical comparison       -> historical cells
ARK-oriented export         -> recovery cells
```

A run manifest ties those records together.

## Model-state placement

Model-state records are metadata linked to interaction records. They should not be forced into an epistemically misleading coordinate merely because the three primary X categories are question/response/evidence.

The runtime should therefore treat model states as **attached typed records** with a host interaction/lattice reference, not pretend the model itself is evidence.

## Lineage

Derived records must identify their inputs by content/reference identity.

Example:

```text
Council response
  derived_from:
    - question:<hash>
    - oracle-evidence:<hash>
    - nexus-run:<receipt>
```

The lattice coordinate alone is insufficient lineage.

## Mutability

Preferred long-horizon model:

```text
records are immutable
new interpretations create new records
corrections reference old records
run manifests preserve historical membership
```

Storage engines may use indexes/caches internally, but exported canonical records should remain inspectable.

## ARK integration

A recovery bundle should contain enough material to reconstruct:

- lattice profile/version;
- coordinate meanings;
- record schemas;
- content IDs;
- lineage;
- interaction manifests;
- model-state records;
- validation/fingerprint rules.

A future AI should not need the original WebUI to understand the archive.

## Hard boundaries

```text
GEOMETRY != TRUTH
POSITION != IMPORTANCE
STORED != CANONICAL
MEMORY != EVIDENCE_AUTHORITY
MODEL_STATE != EVIDENCE
RECURSION != INFINITE_RUNTIME_PERMISSION
```
