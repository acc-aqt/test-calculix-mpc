# IPE 200 cantilever in torsion benchmark

An IPE 200 solid cantilever (C3D20R bricks, no fillet radii) with a torque at the tip, solved
with CalculiX `ccx` 2.24 and checked against Vlasov mixed torsion. It is the sibling of the
[IPE 200 bending benchmark](../ibeam-cantilever/README.md) on the same section. The fixed root
restrains warping, so the beam carries the torque partly by St-Venant shear and partly by
warping, with warping normal stresses that vary across each flange width and decay along the
length. The FE result converges towards the solid section's answer, which sits a few percent
from the thin-walled targets for reasons the report explains. See issue #23 for the full spec and
[ADR 0003](../../docs/adr/0003-torsion-coupling.md) for why the torque goes in through
`*COUPLING` + `*DISTRIBUTING`.

## The model

- **Section and length.** IPE 200 without fillet radii (h = 200, b = 100, t_w = 5.6,
  t_f = 8.5 mm), L = 3000 mm, linear-elastic steel (E = 210 000 MPa, ν = 0.3). Units N, mm, MPa.
- **Supports.** Every degree of freedom on the root face (x = 0) is fixed, so warping is
  restrained there.
- **Load.** A torque T = 5·10⁵ N·mm about +x (right-hand rule) on DOF 4 of a reference node at the
  tip-face centroid. The reference node is joined to a face-based `*SURFACE` of the tip element
  faces by `*COUPLING` + `*DISTRIBUTING` (DOFs 1–6), so the tip face is free to warp.
- **Targets.** The Vlasov tip twist φ(L) = 0.26275 rad, and the warping stress
  σ_w = E·ω·φ''(L/4) = 58.68 MPa at each of the four flange tips at x = L/4, with the signs
  + − − +. The pure St-Venant twist, the St-Venant shear at midspan, the end-corrected values and
  the root peak stress are for information only.
- **Mesh levels**, as elements through the flange thickness / along the web height / along the
  length: coarse 1/4/30, medium 2/8/60, fine 3/12/120, the same as the bending benchmark.

All parameters are in `benchmark_parameters.py`; the analytical values are in `analytical.py`.

## Setup

The torsion benchmark uses the same micromamba environment, `calculix-bench`, as the other
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
end-to-end tests run the real `ccx` on the coarse and medium mesh levels (about 30 s in total)
and are skipped with a message when `ccx` isn't found. One of them solves a
`*DISTRIBUTING COUPLING` variant of the deck (`tests/dcoup_variant.py`), which drops the torque,
and expects the zero-twist guard to stop the run.

## Running the benchmark

From this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
```

This runs the coarse, medium and fine mesh levels (about 30 s in total, most of it the fine level)
and writes `REPORT.md`, which is committed. Options:

- `--levels coarse medium` runs only the levels you name. The verdict is decided by the fine level,
  so a run without it gives "verdict not evaluated".
- `--report <path>` writes the report somewhere else.
- `--work-dir <dir>` changes where decks and solver output go. The default is `work/<mesh
  level>/ibeam.inp` (and `.frd`, `.dat`, ...) in this folder, which git ignores.
- `--ccx <path or name>` sets the solver; a bare name is looked up on `PATH`. Without it, the
  command uses `$CCX`, then `ccx` on `PATH`, then the environment's `ccx`.

Exit codes: `0` PASS (or no verdict), `1` FAIL, `2` when `ccx` is missing, fails or doesn't
finish the job, or when the zero-twist guard trips. On exit code 2 the command prints the reason
and writes no report.

### Reading the report

- **Section properties and targets** are the hand-checkable thin-walled values: G, J = Σbt³/3,
  I_f, h_m, I_w, λ and λL, the flange-tip sectorial coordinate ω, the two targets, and for
  information φ_SV(L), the end-corrected J with its Vlasov twist and L/4 stress, σ_w at the root
  and τ_SV at midspan.
- **Convergence** has one row per mesh level. Error = (FE − analytical) / analytical × 100,
  signed. The tip twist φ(L) = (u_z,top − u_z,bottom)/h_m comes from the mean u_z of the flange
  mid-plane centre nodes at x = L, read from the `.frd`; the reference node isn't read, because
  ccx reports it as zero. σ_w at each flange tip is the mean nodal σ_xx over the five nodes of the
  flange-tip edge through the flange thickness at x = L/4. The errors are signed against signed
  targets, so a flipped stress sign gives about −200 %. The error against St-Venant, τ_SV and the
  root peak von Mises stress are for information only.
- **Verdict** is PASS when the fine mesh level is within ±8 % of the Vlasov φ(L) and within ±5 %
  of σ_w at each of the four flange tips, with the + − − + signs.
- **Expected gap to thin-walled theory.** The FE beam twists about 5–6 % more than the Vlasov
  target and the warping stress is about 4 % higher, and both errors grow slightly with
  refinement. The report's last section explains why: mainly the missing end correction in
  Σbt³/3, which the end-corrected values shown for information account for.

## Figures

The figures and their captions are on [FIGURES.md](FIGURES.md), generated by the figures
command and committed, as for the other benchmarks. To regenerate them, run the benchmark first
(it leaves the solver output in `work/`) and then the figures command, from this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python plots.py
```

`plots.py` reads the solver output of every mesh level and doesn't run `ccx`.

## Running `ccx`

```sh
"$HOME/micromamba/envs/calculix-bench/bin/ccx" -i <jobname>
```

`<jobname>` is the deck name without `.inp` (`ibeam` in each `work/<mesh level>/` folder). Output
files are written to the current directory.

## CalculiX MCP server

Building and registering the [calculix-mcp-rs](https://github.com/carlomontec/calculix-mcp-rs)
server is described in the IPE 200 README's
[CalculiX MCP server](../ibeam-cantilever/README.md#calculix-mcp-server) section. To use it on
this benchmark, register it with `--root <repo dir>/benchmarks/ibeam-torsion`. With `--root` the
models folder is fixed, so a server registered for another benchmark folder can't switch to this
one; either register a second server or write the deck into a folder below its root with
`--work-dir`.

## Cross-check via MCP

The MCP's own deck and `.frd` readers act as an independent check on the Python tool, here on a
`*COUPLING` + `*DISTRIBUTING` deck. In a Claude Code session with the `calculix` tools loaded:

1. Generate the medium deck: `python benchmark.py --levels medium --report <scratch path>` (the
   scratch path keeps the committed `REPORT.md` as it is).
2. `inp_inspect` and `mesh_check` on `work/medium/ibeam.inp`.
3. `ccx_solve` on the same deck, then `ccx_job_status` (`wait_s=30`) and `ccx_diagnose` on the
   job.
4. `frd_summary` and `frd_sets` on the job's `.frd`, with `inp_path=work/medium/ibeam.inp`.
5. `frd_query_set` on the job's `.frd`:
   - for the tip twist nodes, with `inp_path` set to a `tiptwist.nam` file next to the deck that
     holds the five tip nodes of each flange mid-plane centre line (`TOPLINE` and `BOTLINE` run
     along the whole length):

     ```
     *NSET, NSET=TIPTOPC
     19145, 19146, 19147, 19148, 19149
     *NSET, NSET=TIPBOTC
     19001, 19002, 19003, 19004, 19005
     ```

     `TIPTOPC` and `TIPBOTC`, `quantity=displacement`, `top_n=5`;
   - with `inp_path=work/medium/ibeam.inp`: `REFNODE` (displacement), the four flange-tip edges
     `TIPTOPNZ`, `TIPTOPPZ`, `TIPBOTNZ`, `TIPBOTPZ` (stress, `top_n=5`, `top_by=s1` for the
     tension tips and `s3_min` for the compression tips) and `ROOT` (stress, `top_n=1`).

Outcome on the medium mesh level (ccx 2.24, server commit `e12b02e`, 2026-11-27). The server's
root was the IPE 200 folder, so the deck was written with `--work-dir` into an ignored `work/`
folder below it:

| Check | MCP | Python tool |
|---|---|---|
| `inp_inspect` | 1 step (STATIC), `COUPLING`, `DISTRIBUTING` and `SURFACE` in the census, no flags | |
| Free nodes / inverted elements / set problems | 0 / 0 / 0 | |
| Parts | 1, joined by `COUPLING`; 1 reference node (19190, from `*COUPLING`); verdict OK | |
| Elements / nodes | 3360 C3D20R / 19190 | 3360 / 19190 |
| Volume (corner nodes) | 8 174 400 mm³ | A·L = 8 174 400 mm³ |
| Solve | SUCCEEDED, `ccx_diagnose` LINEAR, 1 increment, no solver messages | |
| Reference node (`REFNODE`) | not in `.frd`; job `.dat` gives 0, 0, 0 | not read |
| Top tip centre nodes (`TIPTOPC`) | \|u\| 26.5463 mm at the centre node 19147 (z = 0), up to 26.5564 mm at z = ±2.8 | mean u_z +26.54618 mm |
| Bottom tip centre nodes (`TIPBOTC`) | \|u\| 26.5463 mm at the centre node 19003, up to 26.5564 mm | mean u_z −26.54618 mm |
| Tip twist φ(L) | 2 · 26.5463 / 191.5 = 0.277246 rad (centre nodes) | 0.277245 rad (+5.52 %) |
| Top flange tip, z = −b/2 (`TIPTOPNZ`) | s1 64.103 to 72.876 MPa, s3 min −11.928 MPa | σ_xx mean +60.9285 MPa |
| Top flange tip, z = +b/2 (`TIPTOPPZ`) | s3 −64.103 to −72.876 MPa, s1 max 11.928 MPa | σ_xx mean −60.9285 MPa |
| Bottom flange tip, z = −b/2 (`TIPBOTNZ`) | s3 −64.103 to −72.876 MPa, s1 max 11.928 MPa | σ_xx mean −60.9285 MPa |
| Bottom flange tip, z = +b/2 (`TIPBOTPZ`) | s1 64.103 to 72.876 MPa, s3 min −11.928 MPa | σ_xx mean +60.9285 MPa |
| Root face (`ROOT`) | von Mises max 170.4465 MPa at node 65 (0, −91.5, −50) | 170.45 MPa |

The MCP solve used 4 threads and the Python run 1. Read through the Python tool's own `.frd`
reader, the MCP job's `.frd` gives the same tip twist, flange-tip stresses, τ_SV and root peak to
every printed digit; nodal values in the two files differ by at most one unit in the last printed
digit (10⁻⁴ mm, 10⁻⁴ MPa).

Differences, and why they are not bugs in the benchmark:

- **`mesh_check` verdict is OK here**, unlike on the bending decks: `*COUPLING` is one of the
  connecting cards it knows, and it reads the `REF NODE` parameter, so it finds one part and one
  reference node (see [`docs/upstream/calculix-mcp-rs.md`](../../docs/upstream/calculix-mcp-rs.md)).
  The volume is exact because every edge is straight. The worst aspect ratio is 17.9 (50 mm long
  elements, 2.8 mm across half the web).
- **`REFNODE` has no displacement** in `frd_query_set` (the note says the step has "no DISP
  dataset"), because ccx doesn't write the reference node to the `.frd`. Its `.dat` value is zero,
  as ADR 0003 records, which is why the twist is measured on the beam.
- **Tip-twist values are magnitudes |u|, not u_z, and there is no mean.** The tip section rotates
  about x, so the centre-line nodes off the web mid-plane (z = ±1.4, ±2.8 mm) also move in y
  (u_y = ∓0.74 mm at z = ±2.8), which raises their |u|. At the centre node z = 0, u_x and u_y are
  below 10⁻⁷ mm, so |u| = |u_z| = 26.5463 mm there. φ from those two nodes is 0.0005 % above the
  Python tool's φ, which uses the mean u_z over the five nodes (the off-centre nodes have u_z =
  26.5461 and 26.5462 mm). `frd_query_set` has no component or mean to compare with directly
  (see the upstream findings).
- **Flange-tip stresses are principal stresses, not σ_xx.** On the free flange-tip edge the
  St-Venant shear flow turns round the plate end, so there is a vertical τ_xy, largest at
  mid-thickness: at node 4917 (y = 95.75) σ_xx = 60.9495 MPa and τ_xy = 29.48 MPa, which gives
  s1 = σ/2 + √((σ/2)² + τ²) = 72.876 MPa, the MCP maximum. At the flange surfaces τ_xy is
  6.5 MPa and s1 is 64.1 to 68.6 MPa, against σ_xx of 58.38 to 63.45 MPa. The benchmark's value,
  the mean σ_xx over the five edge nodes, can't be queried. The four edges give the same
  magnitudes with the + − − + pattern: s1 is the large value on the two tension tips and s3 on
  the two compression tips.
- **The whole-model von Mises peak is not at the root.** `frd_summary` gives 210.16 MPa at node
  19046 (3000, −80.06, −2.8), on the tip face where the bottom flange meets the web, with
  σ_yy = 223.2 MPa. That is the load-introduction zone of the coupling, which the report
  mentions as local to the tip. The benchmark's root peak is taken on the root face only, and the
  MCP's `ROOT` query agrees with it.

## Caveats

The IPE 200 README's [Caveats](../ibeam-cantilever/README.md#caveats) on the root prefix, dylibs,
`ccx` exit codes, threads and extra output apply here unchanged. In addition:

- **Don't simplify the coupling.** `*DISTRIBUTING COUPLING` with the moment on DOF 4, as in the
  bending decks, solves with return code 0 and no warning but drops the torque: every
  displacement is zero. Neither ccx nor the MCP's `inp_inspect` warns about it. The zero-twist
  guard and its test catch it. See ADR 0003.
- **Face-based tip surface.** `*DISTRIBUTING` needs a `*SURFACE, TYPE=ELEMENT`; a node surface
  gives `*ERROR reading *DISTRIBUTING: a nodal surface is not allowed`.
- **Mesh level divisions.** The length divisions must be even, so that x = L/2 and L/4 fall on
  nodes. The deck generator rejects other values.
- **Errors grow with refinement.** That is expected here, not a convergence failure: the coarse
  mesh is slightly stiffer in torsion, and the FE converges towards the solid section's answer,
  not the thin-walled target. That is why the verdict has no shrinking-error rule.

## Repository layout

Generated decks and solver output (`*.inp`, `*.frd`, `*.dat`, `*.sta`, `*.cvg`, `*.12d`,
`spooles.out`), the `work/` folder for solver runs and the MCP server's `.calculix-mcp/` folder
are ignored by git (see `.gitignore`). The generated `REPORT.md` and the figures page are
committed so that they render on GitHub. The modules mirror the IPE 200 benchmark's: the
geometry-independent `.frd` and `.dat` readers, `ccx` helpers and palette are copies of the IPE
200 ones, not a shared package.
