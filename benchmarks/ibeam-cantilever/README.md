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

Configuration for both is in `pyproject.toml`. While there are no tests, `pytest` exits with
code 5 ("no tests collected").

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
