# Upstream findings: calculix-mcp-rs

Problems found in [calculix-mcp-rs](https://github.com/carlomontec/calculix-mcp-rs) while
using it for this benchmark. None has been reported upstream yet; each section is written so it
can be pasted into an upstream issue.

## `mesh_check` doesn't count `*DISTRIBUTING COUPLING` as a connecting card

**Status:** not reported. Found during #9, server commit `e12b02e` (2026-11-23).

**What happens.** On a deck where a solid mesh is joined to a reference node with
`*DISTRIBUTING COUPLING`, `mesh_check` returns `verdict: "REVIEW"`, with `parts.count: 2`,
`parts.joined_by: []`, `reference_nodes.count: 0`, and the note "2 parts and no connecting card
(TIE, CONTACT PAIR, RIGID BODY, EQUATION, MPC, COUPLING)". The deck is correct: the coupling
joins the parts and ccx solves it.

**Expected.** `*DISTRIBUTING COUPLING` is listed in `joined_by`, the two parts aren't reported as
unconnected, and the verdict is not REVIEW for this reason.

**Repro.** The medium mesh level deck of this benchmark
(`python benchmark.py --levels medium`, then `mesh_check` on `work/medium/ibeam.inp`). The
relevant cards:

```
*ELEMENT, TYPE=DCOUP3D, ELSET=ECOUP
<coupling element>, <reference node>
...
*DISTRIBUTING COUPLING, ELSET=ECOUP
TIPFACE, 1.0
```

In this form the reference node is given as the only node of a `DCOUP3D` element, not as a
`REF NODE` parameter, so the mesh has two parts: the C3D20R mesh and the one-node `DCOUP3D`
element.

**Cause (from the source).** In `crates/cgx-core/src/mesh_check.rs`, `joining_cards` matches
the exact keywords `RIGID BODY`, `TIE`, `CONTACT PAIR`, `EQUATION`, `MPC` and `COUPLING`. The
keyword `DISTRIBUTING COUPLING` isn't in that list. `card_node_ids` also only reads a
`REF NODE` parameter on `*COUPLING`, so the `DCOUP3D` reference node isn't counted as a
reference node.

**Impact here.** None on the results. The benchmark README's "Cross-check via MCP" section
explains the REVIEW verdict.
