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

## `frd_query_set` gives no components and no set mean

**Status:** not reported. Found during #21, server commit `e12b02e` (2026-11-27).

**What happens.** `frd_query_set` returns, per set and step, only the extrema of the
displacement magnitude |u| and of stress invariants (von Mises, s1, s3, Tresca, hydrostatic),
plus the `top_n` nodes ranked by one of them. It can't return a single component (u_y, σ_xx)
or the mean of a component over the set, although the `.frd` holds the components (`D1`-`D3`,
`SXX`-`SZX`).

**Expected.** An option to query one component per node (for example `component: "D2"` or
`"SXX"`), with min, max and mean over the set, and the component in the `top_n` rows.

**Repro.** The medium mesh level of the tube benchmark (`benchmarks/tube-cantilever`,
`python benchmark.py --levels medium`), solved with `ccx_solve`, then `frd_query_set` on the
job's `.frd` with `inp_path=work/medium/tube.inp`:

- `set=TIPFACE`, `quantity=displacement`: u_max 1.29439 mm at the top-fibre node. That node's
  u_y is 1.28498 mm; the rest is the axial u_x = 0.1558 mm from the rotation of the tip face.
  The benchmark's check value, the mean u_y over the tip face (1.28113 mm), can't be queried.
- `set=MIDTOP`, `quantity=stress`: s1 32.8230 MPa, while σ_xx at that node is 32.8224 MPa (the
  difference is τ_xy = 0.143 MPa). A least-squares fit of σ_xx over `MIDOUTER` can't be built
  from invariants: at the neutral axis s1 is the shear stress, 4.888 MPa.

**Impact here.** None on the results, but the MCP cross-checks in both benchmark READMEs can
only compare invariants and magnitudes with the Python tool's components, and each difference
has to be explained by hand.
