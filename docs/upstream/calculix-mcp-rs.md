# Upstream findings: calculix-mcp-rs

Problems found in [calculix-mcp-rs](https://github.com/carlomontec/calculix-mcp-rs) while
using it for these benchmarks, and one behaviour checked as a counterpart to a problem. None has
been reported upstream yet; each problem section is written so it can be pasted into an upstream
issue.

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
explains the REVIEW verdict. The `*COUPLING` counterpart is handled correctly; see
"`mesh_check` counts `*COUPLING` + `*DISTRIBUTING` as connecting" below.

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

## Deck inspection doesn't warn about a moment on a `*DISTRIBUTING COUPLING` reference node

**Status:** not reported; a suggestion. Found during #27, server commit `e12b02e` (2026-11-27).

**What happens.** ccx 2.24 drops a moment `*CLOAD` (DOF 4–6) on the reference node of a
`*DISTRIBUTING COUPLING`: the job finishes with return code 0 and no warning, and every
displacement is zero. The ccx 2.24 manual (§7.42) says the card is for translational loading only.
None of the MCP's tools points at it. On the torsion benchmark's medium deck with the tip changed
to `*DISTRIBUTING COUPLING` and the torque left on DOF 4:

- `inp_inspect`: `flags: []`; the census lists `DISTRIBUTING COUPLING: 1` and the step plan
  `CLOAD: 1`, with nothing connecting the two. `inp_cards` shows `*CLOAD` with
  `REFNODE, 4, 500000.0` and `*DISTRIBUTING COUPLING, ELSET=ECOUP` with `TIPFACE, 1.0`.
- `mesh_check`: verdict REVIEW, but only for the unrelated reason in the first entry above
  (2 parts, `joined_by: []`, `reference_nodes.count: 0`).
- `ccx_solve` / `ccx_job_status`: SUCCEEDED, exit code 0, verdict LINEAR; `ccx_diagnose`: LINEAR,
  `solver_messages: []`.
- `frd_summary`: `u_max` 0 and `vm_max` 0 over all 19 189 nodes.

**Expected.** `inp_inspect` raises a flag (for example `MOMENT_ON_DISTRIBUTING_COUPLING`) when a
`*CLOAD` on DOF 4, 5 or 6 names a node, or a node set holding a node, that is the reference node
of a `*DISTRIBUTING COUPLING`, i.e. the node of a `DCOUP3D` element in the coupling's `ELSET`. The
flag's note can point to `*COUPLING` + `*DISTRIBUTING` (manual §7.27, §7.41) or a mean-rotation
MPC (§8.7.1), which do carry a moment. The `*CLOAD` in the repro names the node through a set,
so the check has to resolve node sets.

**Repro.** The medium mesh level of the torsion benchmark (`benchmarks/ibeam-torsion`,
`python benchmark.py --levels medium`), passed through `distributing_coupling_variant` in
`tests/dcoup_variant.py`. The variant replaces the `*SURFACE`/`*COUPLING`/`*DISTRIBUTING` tip with:

```
*ELEMENT, TYPE=DCOUP3D, ELSET=ECOUP
3361, 19190
*DISTRIBUTING COUPLING, ELSET=ECOUP
TIPFACE, 1.0
*STEP
*STATIC
*CLOAD
REFNODE, 4, 500000.0
```

**Cause (from the source).** `InpCards::flags` in `crates/cgx-core/src/parser/inp_cards.rs`
only raises structural flags (cyclic symmetry, contact, NLGEOM, perturbation, missing includes,
no steps, no mesh); no check looks at loads against the cards they act through.

**Impact here.** None on the results: the benchmark uses `*COUPLING` + `*DISTRIBUTING`
(ADR 0003), and its zero-twist guard, with a test that solves this variant, catches the drop.

## `mesh_check` counts `*COUPLING` + `*DISTRIBUTING` as connecting

**Status:** works as expected; no report needed. Checked during #27, server commit `e12b02e`
(2026-11-27). Recorded as the counterpart to the `*DISTRIBUTING COUPLING` entry above.

**What happens.** On the torsion benchmark's medium deck, where the tip reference node is joined
to a face-based tip surface by `*COUPLING, REF NODE=19190, SURFACE=TIPSURF` and `*DISTRIBUTING`,
`mesh_check` returns `verdict: "OK"`, `parts.count: 1`, `parts.joined_by: ["COUPLING"]` and
`reference_nodes.count: 1` (node 19190, card `COUPLING`), with no problems, 0 free nodes and 0
inverted elements. `inp_inspect` lists `COUPLING`, `DISTRIBUTING` and `SURFACE` in its census,
with `flags: []`.

**Expected.** As above. The reference node is in no element, so it is a reference node and not a
part, and the deck is one part.

**Repro.** `python benchmark.py --levels medium` in `benchmarks/ibeam-torsion`, then
`mesh_check` on `work/medium/ibeam.inp`.

**Evidence (from the source).** In `crates/cgx-core/src/mesh_check.rs`, `card_node_ids` reads
the `REF NODE` parameter of `*COUPLING`, so the node counts as a reference node rather than a free
node, and `joining_cards` lists `COUPLING` whenever the keyword is present in the deck. That
second check is by presence only: it doesn't test whether the coupling's surface actually reaches
the parts it is said to join.

**Impact here.** None; the torsion README's "Cross-check via MCP" section records the OK
verdict.
