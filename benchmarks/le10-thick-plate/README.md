# NAFEMS LE10 thick plate benchmark

The NAFEMS LE10 thick plate (C3D20R bricks) under pressure on its top face, solved with
CalculiX `ccx` 2.24 and checked against the published reference value of σ_yy at point D.
Unlike the cantilever benchmarks, the plate's stress state is fully three-dimensional and has no
closed-form answer, so the target is a published value and sanity guards take the place of the
analytical cross-checks. See issue #30 for the full spec and
[ADR 0004](../../docs/adr/0004-published-reference-value.md) for the target and its provenance.

## The model

- **Thick plate.** A quarter of an elliptic annulus between the inner ellipse
  x²/2000² + y²/1000² = 1 (the hole edge) and the outer ellipse x²/3250² + y²/2750² = 1, 600 mm
  thick with the mid-plane at z = 0, linear-elastic steel (E = 210 000 MPa, ν = 0.3). Units N,
  mm, MPa.
- **Supports.** u_y = 0 on the y = 0 face and u_x = 0 on the x = 0 face (symmetry),
  u_x = u_y = 0 on the outer face, and u_z = 0 on line EE′, the outer face at z = 0, on every
  corner and midside node. The hole face and the bottom face are free.
- **Load.** A uniform pressure p = 1 MPa on the top face (z = +300 mm), applied as `*DLOAD` on a
  face-based `*SURFACE`.
- **Target.** The published reference value σ_yy(D) = −5.38 MPa, compressive, at point D =
  (2000, 0, +300) mm: on the hole edge, on the x axis, on the loaded face. It comes from four
  vendor verification documents that agree on it (Abaqus, Altair OptiStruct, Seamplex/Fino and
  COMSOL); the primary NAFEMS document, TNSB Rev. 3, was not consulted. Some sources quote the
  magnitude 5.38 MPa. See ADR 0004.
- **Mesh levels**, as elements around the annulus × across it × through the thickness: coarse
  6×4×2, medium 12×8×4, fine 24×16×8. Each level halves the element size of the one before. The
  mesh is mapped: each line across the annulus joins the two ellipses at one parametric angle θ,
  (a cos θ, b sin θ), with uniform spacing, and the midside nodes sit on the ellipses. The
  thickness count must be even so that line EE′ has nodes; the deck generator rejects other
  values.
- **C3D20 (information).** Every level is solved again with full integration. These values never
  count towards the verdict.

All parameters are in `benchmark_parameters.py`; the target and the exact geometry the guards
use are in `reference.py`.

## Sanity guards

Without a formula to fall back on, a quietly wrong deck could still land near −5.38 MPa. Two
sanity guards check the solved model and stop the run with exit code 2 and no report:

- **Mesh volume.** The volume of the elements, integrated from their node positions with the
  20-node shape functions so that curved edges count, must be within 0.1 % of the exact quarter
  annulus, (π/4)(a_o·b_o − a_i·b_i)·t = 3.26922·10⁹ mm³.
- **Reaction balance.** The total RF_z on line EE′, printed to the `.dat`, must be within 0.1 %
  of the applied load p·(π/4)(a_o·b_o − a_i·b_i) = 5 448 699.8 N.

The tests solve two broken variants of the coarse deck (`tests/broken_variants.py`): one with
straight-chord midside nodes, which trips the volume guard, and one with only half the top face
loaded, which trips the reaction guard.

## Setup

The LE10 benchmark uses the same micromamba environment, `calculix-bench`, as the other
benchmarks; its `environment.yml` is identical. If you already set it up, there is nothing to
install. Otherwise follow the IPE 200 README's [Setup](../ibeam-cantilever/README.md#setup)
(install micromamba with Homebrew), then create the environment from this folder:

```sh
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
micromamba create -y -f environment.yml
"$HOME/micromamba/envs/calculix-bench/bin/ccx" -v
```

The last command prints `This is Version 2.24`. Run commands in the environment with
`micromamba run -p "$HOME/micromamba/envs/calculix-bench" <command>`; you don't need
`micromamba activate`.

## Lint and tests

From this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" pytest
micromamba run -p "$HOME/micromamba/envs/calculix-bench" ruff check
```

Configuration for both is in `pyproject.toml`, the same as for the other benchmarks. The
end-to-end tests run the real `ccx`, mostly on the coarse level and once on all three levels
(about 10 s in total), and are skipped with a message when `ccx` isn't found.

## Running the benchmark

From this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
```

This runs the coarse, medium and fine mesh levels, each with C3D20R and C3D20 (about 15 s in
total, most of it the fine level), and writes `REPORT.md`, which is committed. Options:

- `--levels coarse medium` runs only the levels you name. The verdict needs all three levels, so
  a run without one of them gives "verdict not evaluated".
- `--report <path>` writes the report somewhere else.
- `--work-dir <dir>` changes where decks and solver output go. The default is
  `work/<mesh level>/<element type>/le10.inp` (and `.frd`, `.dat`, ...) in this folder, which
  git ignores.
- `--ccx <path or name>` sets the solver; a bare name is looked up on `PATH`. Without it, the
  command uses `$CCX`, then `ccx` on `PATH`, then the environment's `ccx`.

Exit codes: `0` PASS (or no verdict), `1` FAIL, `2` when `ccx` is missing, fails or doesn't
finish the job, or when a sanity guard trips. On exit code 2 the command prints the reason and
writes no report.

### Reading the report

- **Benchmark parameters and target** list the geometry, material, load, supports, the top-face
  area, the exact volume and the published value with its provenance.
- **Convergence** has one row per mesh level. Error = (FE − target) / target × 100, signed
  against the signed target, so a flipped sign gives about −200 %. σ_yy(D) is ccx's nodal value
  from the `.frd`, extrapolated from the integration points of the one element at D. The
  integration point nearest D, printed to the `.dat` with `*EL PRINT`, shows how much of the
  nodal value comes from extrapolation. The observed order and the Richardson estimate, flagged
  when more than 2 % from the target, are for information only.
- **Verdict** is PASS when the fine C3D20R level's σ_yy(D) is within ±3 % of −5.38 MPa, with the
  same sign, and σ_yy(D) is converging, |fine − medium| < |medium − coarse|. There is no verdict
  unless all three levels were run.
- **Stress at D** gives the full nodal stress tensor. D's exact state is biaxial, σ_xx = 0, every
  shear component 0 and σ_zz = −p, so the distance from that is a check on the surface
  tractions.

## Figures

The figures and their captions are on [FIGURES.md](FIGURES.md), generated by the figures
command and committed, as for the other benchmarks. To regenerate them, run the benchmark first
(it leaves the solver output in `work/`) and then the figures command, from this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python plots.py
```

`plots.py` reads the C3D20R and C3D20 solver output of every mesh level and doesn't run `ccx`;
it exits with code 1 and writes nothing when any of it is missing. `--output-dir <dir>` writes
`figures/` and `FIGURES.md` somewhere else.

## Running `ccx`

```sh
"$HOME/micromamba/envs/calculix-bench/bin/ccx" -i <jobname>
```

`<jobname>` is the deck name without `.inp` (`le10` in each `work/<mesh level>/<element type>/`
folder). Output files are written to the current directory.

## CalculiX MCP server

Building and registering the [calculix-mcp-rs](https://github.com/carlomontec/calculix-mcp-rs)
server is described in the IPE 200 README's
[CalculiX MCP server](../ibeam-cantilever/README.md#calculix-mcp-server) section. To use it on
this benchmark, register it with `--root <repo dir>/benchmarks/le10-thick-plate`. With `--root`
the models folder is fixed, so a server registered for another benchmark folder can't switch to
this one; either register a second server or copy the deck and `.frd` into a folder below its
root.

## Cross-check via MCP

The MCP's own deck and `.frd` readers act as an independent check on the Python tool. In a
Claude Code session with the `calculix` tools loaded:

1. Generate and solve the fine level:
   `python benchmark.py --levels fine --report <scratch path>` (the scratch path keeps the
   committed `REPORT.md` as it is).
2. `inp_inspect` and `mesh_check` on `work/fine/C3D20R/le10.inp`.
3. `frd_summary` on `work/fine/C3D20R/le10.frd`.
4. `frd_query_set` on the same `.frd` with `inp_path=work/fine/C3D20R/le10.inp`,
   `set=POINTD`, `quantity=stress`, `top_n=1`.

Outcome on the fine C3D20R level (ccx 2.24, 2026-11-27). The server's root was the IPE 200
folder, so the fine deck and `.frd` from the Python run were copied into an ignored `work/`
folder below it; the MCP didn't solve the deck itself.

| Check | MCP | Python tool |
|---|---|---|
| `inp_inspect` | 1 step (STATIC), `SURFACE` in the census, 7 node sets and `ELEMD`, `POINTD` holds 1 node, no flags | |
| Free nodes / inverted elements / set problems | 0 / 0 / 0 | |
| Parts | 1, no reference nodes; verdict OK | |
| Elements / nodes | 3072 C3D20R / 14497 | 3072 / 14497 |
| Worst aspect ratio | 2.84 | |
| Volume | 3 266 886 305 mm³ (corner nodes, −0.071 %) | 3 269 219 730 mm³ (shape functions, −4·10⁻⁶ %), exact 3 269 219 855 mm³ |
| σ_yy at D (`POINTD`, node 17) | s3 −5.3620 MPa | σ_yy −5.36202 MPa (−0.33 %) |
| σ_xx at D | s1 −0.0589 MPa | σ_xx −0.0591 MPa |
| Von Mises at D | 4.9005 MPa | 4.9005 MPa |
| Hydrostatic at D | −2.1406 MPa | (σ_xx + σ_yy + σ_zz)/3 = −2.1406 MPa |
| Whole-model peaks (`frd_summary`) | \|u\| 0.2068 mm at node 641 (point A); von Mises 31.88 MPa at node 14489 (0, 2750, 0) | |

Differences, and why they are not bugs in the benchmark:

- **σ_yy(D) is read as the principal stress s3.** `frd_query_set` gives only invariants (see
  [`docs/upstream/calculix-mcp-rs.md`](../../docs/upstream/calculix-mcp-rs.md)), but at D the shear stresses are below 0.012 MPa, so the principal stresses
  are the normal ones to the printed digits: s3 = σ_yy, s1 ≈ σ_xx (−0.0589 against −0.0591 MPa),
  and the middle one is σ_zz = −1.001 MPa. That is the biaxial state D should have, so the
  comparison holds here; it wouldn't on a point with real shear.
- **The MCP volume is 0.071 % short.** `mesh_check` uses corner nodes only, so each curved edge
  counts as a straight chord; its note says so. The benchmark's volume guard integrates the
  midside nodes too and is exact to 4·10⁻⁶ %. The MCP volume is within the guard's 0.1 %
  tolerance, but it can't tell a deck with midside nodes on the ellipses from one with
  straight-chord midside nodes: on the fine level the two give the same corner-node volume to the
  last digit (see the upstream findings).
- **The whole-model von Mises peak is on line EE′.** Node 14489 is the end of line EE′ on the
  x = 0 face, where τ_yz = 18.4 MPa. The u_z = 0 line support is singular, so stresses next to it
  depend on the mesh, as ADR 0004 records. Point D is far from it.
- **The largest |u| is at point A**, node 641 at (0, 1000, 300): u_z = −0.2026 mm, the value
  figure 8 gives for the fine level, and u_y = −0.0418 mm.

## Caveats

The IPE 200 README's [Caveats](../ibeam-cantilever/README.md#caveats) on the root prefix, dylibs,
`ccx` exit codes, threads and extra output apply here unchanged. In addition:

- **The volume guard is weakest on the fine level.** Straight-chord midside nodes cut the
  volume by 1.14 % on the coarse level, 0.29 % on the medium level and 0.071 % on the fine level,
  so on the fine level alone they would pass the 0.1 % tolerance. The test uses the coarse
  level, and a full run solves the coarse and medium levels as well.
- **The low observed order.** The observed order p = 0.60 says the sequence is not yet in its
  asymptotic range, so the Richardson estimate is not a reliable limit. It is information only
  and doesn't affect the verdict.
- **The published hex20 results scatter** by a few percent around −5.38 MPa (ADR 0004 lists
  them). The ±3 % tolerance sits inside that scatter. Our mesh levels are not the NAFEMS meshes,
  so published coarse-mesh errors don't carry over to our coarse level.

## Repository layout

Generated decks and solver output (`*.inp`, `*.frd`, `*.dat`, `*.sta`, `*.cvg`, `*.12d`,
`spooles.out`), the `work/` folder for solver runs and the MCP server's `.calculix-mcp/` folder
are ignored by git (see `.gitignore`). The generated `REPORT.md` and the figures page are
committed so that they render on GitHub. The geometry-independent `.frd` and `.dat` readers,
`ccx` helpers and palette follow the other benchmarks' and are copies, not a shared package;
`reference.py` holds the published target and the exact geometry, and
`tests/broken_variants.py` the quietly wrong decks the guards are tested on.
