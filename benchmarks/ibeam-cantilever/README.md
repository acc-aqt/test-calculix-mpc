# IPE 200 cantilever benchmark

An IPE 200 solid cantilever (C3D20R bricks) with a tip load, solved with CalculiX `ccx` 2.24 and
checked against Euler-Bernoulli and Timoshenko beam theory. See issue #1 for the full spec.

## Setup

Tested on macOS (Apple Silicon). The solver and Python tooling live in an isolated micromamba
environment named `calculix-bench`, defined in `environment.yml`.

1. Install micromamba with Homebrew:

   ```sh
   brew install micromamba
   ```

2. Create the environment from conda-forge (run from this folder):

   ```sh
   export MAMBA_ROOT_PREFIX="$HOME/micromamba"
   micromamba create -y -f environment.yml
   ```

   This installs `calculix` 2.24 (`ccx`), Python 3.12, numpy, pytest and ruff into
   `$HOME/micromamba/envs/calculix-bench`.

3. Check the solver:

   ```sh
   "$HOME/micromamba/envs/calculix-bench/bin/ccx" -v
   ```

   It prints `This is Version 2.24`.

You don't need `micromamba shell init` or `micromamba activate`. Run commands in the environment
with `micromamba run -p "$HOME/micromamba/envs/calculix-bench" <command>`.

## Lint and tests

From this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" pytest
micromamba run -p "$HOME/micromamba/envs/calculix-bench" ruff check
```

Configuration for both is in `pyproject.toml`. The end-to-end tests run the real `ccx` (coarse
and medium mesh levels, a few seconds) and are skipped with a message when `ccx` isn't found.

## Running the benchmark

From this folder:

```sh
micromamba run -p "$HOME/micromamba/envs/calculix-bench" python benchmark.py
```

This runs the coarse, medium and fine mesh levels (about 45 s in total, most of it the fine level)
and writes `REPORT.md`, which is committed. Options:

- `--levels coarse medium` runs only the levels you name. Without `fine` there's no verdict.
- `--report <path>` writes the report somewhere else.
- `--work-dir <dir>` changes where decks and solver output go. The default is `work/<mesh
  level>/ibeam.inp` (and `.frd`, `.dat`, ...) in this folder, which git ignores.
- `--ccx <path>` sets the solver. Without it, the command uses `$CCX`, then `ccx` on `PATH`, then
  the environment's `ccx`.

Exit codes: `0` PASS (or no verdict), `1` FAIL, `2` when `ccx` is missing, fails or doesn't
finish the job. On exit code 2 the command prints the `*ERROR` lines and writes no report.

### Reading the report

- **Section properties and targets** are the hand-checkable analytical values: A, I, the shear
  area A_s, the Euler-Bernoulli deflection (information only), and the Timoshenko deflection and
  midspan stress, which are the targets.
- **Convergence** has one row per mesh level. Error = (FE − analytical) / analytical × 100.
  Deflection errors use magnitudes. Stress errors are signed: the analytical midspan stress is +σ
  at the top flange and −σ at the bottom flange, so a flange with the wrong sign fails.
  Tip deflection is the reference node's u_y, which is read from the `.dat` because ccx doesn't write the reference node to the `.frd`. The web-centreline tip node is listed next
  to it as a check on the coupling. Midspan σ_xx is averaged across the full flange width on the
  outer flange surface at x = L/2. Stresses keep their sign: the top flange is in tension and the
  bottom flange in compression. Spec #1 has these signs the wrong way round. The root peak von
  Mises stress is for information only and grows as the mesh level gets finer (a
  singularity where the root face meets the free surfaces).
- **Verdict** is PASS when the fine mesh is within ±2 % of the Timoshenko deflection and of the
  midspan stress at both flanges.

Spec #1's "I ≈ 1.943×10⁷ mm⁴, δ_EB ≈ 22.06 mm, shear adds ~5 %" are figures for the rolled section
with fillets. The no-fillet section modelled here has I ≈ 1.846×10⁷ mm⁴, δ_EB ≈ 23.22 mm and
δ_T ≈ 23.57 mm, so shear adds about 1.5 %.

## Running `ccx`

```sh
"$HOME/micromamba/envs/calculix-bench/bin/ccx" -i <jobname>
```

`<jobname>` is the deck name without `.inp`. Output files are written to the current directory.

## CalculiX MCP server

The [calculix-mcp-rs](https://github.com/carlomontec/calculix-mcp-rs) server gives Claude Code
tools to inspect decks, run `ccx` and query `.frd` results. Build it outside this repository and
register it at local scope, so no machine-specific paths are committed.

1. Install a Rust toolchain:

   ```sh
   brew install rustup
   export PATH="$(brew --prefix rustup)/bin:$PATH"
   rustup default stable
   ```

   Homebrew's `rustup` is keg-only, so add its `bin` folder to `PATH` yourself.

2. Clone and build the server in a folder outside this repository:

   ```sh
   git clone https://github.com/carlomontec/calculix-mcp-rs.git <clone dir>
   cd <clone dir>
   cargo build --release -p calculix-mcp
   <clone dir>/target/release/calculix-mcp --help
   ```

   `--help` lists `--root`, `--allow`, `--ccx`, `--env-passthrough`, `--max-run-gb` and `--cgx`.

3. Register it from the repository root (local scope is the default and is private to you):

   ```sh
   claude mcp add --scope local calculix -- <clone dir>/target/release/calculix-mcp \
     --root <repo dir>/benchmarks/ibeam-cantilever \
     --ccx ccx="$HOME/micromamba/envs/calculix-bench/bin/ccx"
   claude mcp list
   ```

   All paths must be absolute. `claude mcp list` shows `calculix` as connected. `--root` pins the
   server's models folder to this benchmark folder. `--env-passthrough` isn't needed: the server
   clears the solver's environment, and `ccx` runs without one (see Caveats).

4. Restart Claude Code. A running session doesn't pick up a newly registered server, so the
   tools are only available in a new session.

The server runs each solve on a copy of the deck in `.calculix-mcp/runs/<job id>/` inside this
folder, which is ignored by git. It never deletes those folders.

## Caveats

- **Root prefix.** Set `MAMBA_ROOT_PREFIX` (or use `-p <env path>`) for every micromamba call. If
  you don't, Homebrew's micromamba uses its own Cellar folder as the root prefix, so `-n
  calculix-bench` won't find the environment and new environments would be created inside the
  Homebrew install.
- **Dylibs.** `ccx` links its libraries (arpack, openblas, libgfortran, libomp) through
  `@rpath`, which resolves to `@loader_path/../lib`, the environment's own `lib` folder. It runs
  with an empty environment (`env -i`), so you don't need `DYLD_LIBRARY_PATH`, activation or
  `--env-passthrough` when you register it with an MCP server. Call it by its absolute path.
- **Exit codes.** `ccx` exits with 0 when the job finishes and 201 on input errors (for
  example, a missing deck or an element without a material). `ccx -v` also exits with 201, so
  don't treat a non-zero exit from `-v` as a failure.
- **Threads.** By default `ccx` uses 1 CPU. Set `OMP_NUM_THREADS` to use more.
- **Extra output.** Besides `.frd`, `.dat`, `.sta` and `.cvg`, each run writes a `.12d` file and
  `spooles.out`. All of them are ignored by git.

## Repository layout

Generated decks and solver output (`*.inp`, `*.frd`, `*.dat`, `*.sta`, `*.cvg`, `*.12d`,
`spooles.out`), the `work/` folder for solver runs and the MCP server's `.calculix-mcp/` folder
are ignored by git (see `.gitignore`).
