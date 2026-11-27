# CHS 168.3 × 8 tube cantilever benchmark

An EN 10210 CHS 168.3 × 8 solid tube cantilever (C3D20R bricks) with a tip load, solved with
CalculiX `ccx` 2.24 and checked against Timoshenko beam theory with Cowper's shear coefficient.
It is the sibling of the [IPE 200 benchmark](../ibeam-cantilever/README.md): the curved section
makes the convergence study meaningful, because the mesh approximates the circle while the
targets use the exact annulus. See issue #17 for the full spec and
[ADR 0002](../../docs/adr/0002-tube-cantilever-benchmark.md) for the decisions.

## Setup

The tube benchmark uses the same micromamba environment, `calculix-bench`, as the IPE 200
benchmark; its `environment.yml` is identical. If you already set it up for the IPE 200
benchmark, there is nothing to install. Otherwise follow the IPE 200 README's
[Setup](../ibeam-cantilever/README.md#setup) (install micromamba with Homebrew), then create the
environment from this folder:

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

Configuration for both is in `pyproject.toml`, the same as for the IPE 200 benchmark. The
end-to-end tests run the real `ccx` (coarse and medium mesh levels, about a second) and are
skipped with a message when `ccx` isn't found. The figures tests are also skipped without
matplotlib or PyVista.

## Running the benchmark

From this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
```

This runs the coarse, medium and fine mesh levels (about 10 s in total, most of it the fine level)
and writes `REPORT.md`, which is committed. Options:

- `--levels coarse medium` runs only the levels you name. A verdict needs all three levels, so a
  partial run gives none.
- `--report <path>` writes the report somewhere else.
- `--work-dir <dir>` changes where decks and solver output go. The default is `work/<mesh
  level>/tube.inp` (and `.frd`, `.dat`, ...) in this folder, which git ignores.
- `--ccx <path or name>` sets the solver; a bare name is looked up on `PATH`. Without it, the
  command uses `$CCX`, then `ccx` on `PATH`, then the environment's `ccx`.

Exit codes: `0` PASS (or no verdict), `1` FAIL, `2` when `ccx` is missing, fails or doesn't
finish the job. On exit code 2 the command prints the `*ERROR` lines and writes no report.

### Reading the report

- **Section properties and targets** are the hand-checkable analytical values for the exact
  annulus: A, I, the Cowper shear coefficient κ, G, the Euler-Bernoulli deflection and the
  thin-wall κ = 0.5 deflection (both information only), and the Timoshenko deflection with
  Cowper κ and the midspan stress, which are the targets.
- **Convergence** has one row per mesh level, labelled by circumferential divisions / elements
  through the wall / elements along the length (coarse 8/1/10, medium 16/2/20, fine 32/4/40).
  Error = (FE − analytical) / analytical × 100. Deflection errors use magnitudes. Stress errors
  are signed: the analytical midspan stress is +σ at the top fibre and −σ at the bottom fibre, so
  a fibre with the wrong sign fails.
  Tip deflection is the reference node's u_y, read from the `.dat` because ccx doesn't write the
  reference node to the `.frd`. The tip-face mean deflection is listed next to it as a check on
  the coupling (the tube has no material at its centroid, so there is no centreline node).
  The midspan stress is the midspan stress fit σ_xx = a·y + b over every midspan outer-surface
  node, reported as a·r_o + b and −a·r_o + b, so each fibre is checked on its own; the single-node
  σ_xx at the top-fibre and bottom-fibre nodes is
  shown next to it. The root peak von Mises stress is for information only and grows as the mesh
  level gets finer.
- **Observed order** is reported for information for the deflection, the fit and the single-node
  stresses. The deflection's is n/a: it is within 0.1 % at the coarse level and then sits on a
  modelling floor of about −0.007 % against δ_T, which is not mesh error.
- **Verdict** is PASS when the fine mesh level is within ±1 % of the Timoshenko deflection and of
  the midspan stress fit at both fibres, **and** the fit error magnitude strictly shrinks coarse →
  medium → fine at both fibres.

## Figures

The figures and their captions are on [FIGURES.md](FIGURES.md); the PNGs are in `figures/`. Both
are generated and committed. To regenerate them, run the benchmark first (it leaves the solver
output in `work/`) and then the figures command, from this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python plots.py
```

`plots.py` reads the `.frd` and `.dat` of every mesh level and doesn't run `ccx`. Figures 1-4
are 3D views that `renders.py` draws off-screen with PyVista; figures 5-8 are matplotlib charts.
Figure 8 is the convergence plot: |error| against element size (circumferential arc length per
element) on log-log axes, with the observed order marked. Options:

- `--work-dir <dir>` reads the solver output from another folder, as for `benchmark.py`.
- `--output-dir <dir>` writes `figures/` and `FIGURES.md` somewhere else.

Exit codes: `0` figures written, `1` when a mesh level's `.frd` or `.dat` is missing. Then the
command lists the missing files, tells you to run `benchmark.py` first and writes nothing.

## Running `ccx`

```sh
"$HOME/micromamba/envs/calculix-bench/bin/ccx" -i <jobname>
```

`<jobname>` is the deck name without `.inp` (`tube` in each `work/<mesh level>/` folder). Output
files are written to the current directory.

## CalculiX MCP server

Building and registering the [calculix-mcp-rs](https://github.com/carlomontec/calculix-mcp-rs)
server is described in the IPE 200 README's
[CalculiX MCP server](../ibeam-cantilever/README.md#calculix-mcp-server) section. To use it on
this benchmark, register it with `--root <repo dir>/benchmarks/tube-cantilever`. With `--root`
the models folder is fixed, so a server registered for the IPE 200 folder can't switch to this
one; either register a second server or copy the deck into a folder below its root.

## Cross-check via MCP

The MCP's own deck and `.frd` readers act as an independent check on the Python tool, here on
curved quadratic elements. In a Claude Code session with the `calculix` tools loaded:

1. Generate the medium deck: `python benchmark.py --levels medium --report <scratch path>` (the
   scratch path keeps the committed `REPORT.md` as it is).
2. `mesh_check` on `work/medium/tube.inp`.
3. `ccx_solve` on the same deck, then `ccx_job_status` (`wait_s=30`) and `ccx_diagnose` on the
   job.
4. `frd_query_set` on the job's `.frd` with `inp_path=work/medium/tube.inp`, for `REFNODE` and
   `TIPFACE` (displacement), `MIDTOP` and `MIDBOT` (stress) and `MIDOUTER` (stress, `top_by=s1`,
   `top_n=32`).

Outcome on the medium mesh level (ccx 2.24, 2026-11-27). The server's root was the IPE 200
folder, so the generated deck was copied into a folder below it for the session:

| Check | MCP | Python tool |
|---|---|---|
| Free nodes / inverted elements / set problems | 0 / 0 / 0 | |
| Elements / nodes | 640 C3D20R + 1 DCOUP3D / 3649 | 640 / 3649 |
| Volume (corner nodes) | 3 926 026 mm³ | A·L = 4 028 778 mm³ |
| Solve | SUCCEEDED, `ccx_diagnose` LINEAR, 1 increment | |
| δ reference node (`REFNODE`) | not in `.frd`; job `.dat` gives 1.281135 mm | 1.28113 mm |
| Tip face (`TIPFACE`), 128 nodes | \|u\| from 1.27697 to 1.29439 mm | mean u_y 1.28113 mm |
| Midspan top fibre (`MIDTOP`) | s1 32.8230 MPa | σ_xx +32.8224 MPa |
| Midspan bottom fibre (`MIDBOT`) | s3 −32.8230 MPa | σ_xx −32.8224 MPa |
| Midspan outer surface (`MIDOUTER`), 32 nodes | s1 max 32.8230, s3 min −32.8230 MPa | fit ±32.5133 MPa |

The MCP solve used 4 threads and the Python run 1. The nodal values in the two `.frd` files
differ by at most one unit in the last printed digit (10⁻⁶ mm, 10⁻⁵ MPa), and the reference
node's u_y in the two `.dat` files is the same.

Differences, and why they are not bugs in the benchmark:

- **`mesh_check` verdict is REVIEW**, for the same reason as on the IPE 200 deck: it finds 2
  parts (the C3D20R mesh and the `DCOUP3D` element) and doesn't count `*DISTRIBUTING COUPLING`
  as a connecting card (see
  [`docs/upstream/calculix-mcp-rs.md`](../../docs/upstream/calculix-mcp-rs.md)). Everything else
  is clean. The worst aspect ratio is 12.5 (50 mm long elements, 4 mm across half the wall).
- **`mesh_check`'s volume is the polygonal mesh, not the annulus.** It uses corner nodes only,
  so each quadratic arc counts as its chord and the section is a 16-sided polygonal annulus:
  (16/2)·sin(2π/16)·(r_o² − r_i²)·L = 3 926 026 mm³, exactly the MCP value and 2.55 % below the
  exact A·L. The MCP's own note says so. The FE geometry, whose midside nodes lie on the true
  arcs, has a parabolic edge on each segment and a volume of about 4 028 580 mm³, 0.005 % below
  A·L. So the 2.55 % is a limit of the check, not of the mesh; the server's own README documents it.
- **`REFNODE` has no displacement** in `frd_query_set`, because ccx doesn't write the reference
  node to the `.frd`. The MCP can't read `.dat` files, so the value above comes from the job's
  `.dat` file.
- **Tip-face values are magnitudes |u|, not u_y, and there is no mean.** The tip face rotates, so
  the top and bottom fibre nodes also move axially (u_x = ±0.1558 mm): their |u| is 1.29439 mm
  while their u_y is 1.28498 mm. At the neutral axis u_x = 0, so the MCP minimum 1.27697 mm is
  u_y there. The Python tool's tip-face mean u_y lies between them, and `frd_query_set` has no
  mean to compare with it (see the upstream findings).
- **Midspan stresses are principal stresses, not σ_xx.** `frd_query_set` reports invariants,
  not components. At the top fibre node σ_xx = 32.8224 MPa and there is a small τ_xy =
  0.1430 MPa, so s1 ≈ σ_xx + τ²/σ_xx = 32.8230 MPa, the MCP value; the bottom fibre mirrors it.
  The MCP can't reproduce the fit, which needs σ_xx and y at every `MIDOUTER` node: s1 at the
  neutral axis nodes (y = 0, z = ±r_o) is 4.888 MPa, which is the transverse shear stress τ_xy
  there, not bending. The fit (32.5133 MPa) is below the single-node top value because the
  single-node value carries the section discretisation error most strongly (+1.2 % against
  +0.25 % for the fit at this mesh level).

## Caveats

The IPE 200 README's [Caveats](../ibeam-cantilever/README.md#caveats) on the root prefix, dylibs,
`ccx` exit codes, threads and extra output apply here unchanged. In addition:

- **Coordinate formatting.** The deck writes node coordinates with at most 14 significant digits
  and round-off below 1e-9 as 0. `ccx` 2.24 rejects full-precision values such as
  `4.6628426877535476e-15` (what cos 90° gives in floating point) with `*ERROR reading *NODE`
  and exit code 201, so a deck written with Python's `repr` would not run. Keep this if you change `deck.py`.
- **Mesh level divisions.** The circumferential divisions must be a multiple of 4 and the length
  divisions even, so that the top and bottom fibres, the neutral axis and x = L/2 fall on nodes.
  The deck generator rejects other values.
- **Deflection floor.** The deflection error doesn't converge to zero: from the medium level on
  it sits at about −0.007 % against δ_T. That is the modelling difference between the clamped
  solid with a distributing coupling and Timoshenko beam theory, at the resolution of the `.dat`
  print. That is why only the stress has to shrink for a PASS.

## Repository layout

Generated decks and solver output (`*.inp`, `*.frd`, `*.dat`, `*.sta`, `*.cvg`, `*.12d`,
`spooles.out`), the `work/` folder for solver runs and the MCP server's `.calculix-mcp/` folder
are ignored by git (see `.gitignore`). The generated `REPORT.md`, `FIGURES.md` and `figures/` are
committed so that they render on GitHub. The modules mirror the IPE 200 benchmark's: the
geometry-independent `.frd` and `.dat` readers, `ccx` helpers and palette are copies of the IPE
200 ones, not a shared package.
