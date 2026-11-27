# IPE 200 Cantilever Benchmark

A reproducible check of CalculiX, set up and inspected through the `calculix-mcp-rs` MCP server, against closed-form beam theory for a solid IPE 200 cantilever with a tip load.

## Model

**Solid I-beam**:
The IPE 200 section (without fillet radii) modelled as 20-node C3D20R brick elements covering both flanges and the web, extruded along the beam length.
_Avoid_: Beam model, 3D beam

**Root face**:
The cross-section face at x = 0, where every degree of freedom is fixed to form the cantilever support.
_Avoid_: Clamped end, fixed face, support face

**Tip face**:
The cross-section face at x = L, through which the tip load is introduced into the solid.
_Avoid_: Free end, load face

**Reference node**:
A single node at the tip-face centroid (which is also the shear centre) that carries the tip load and whose vertical displacement is the measured tip deflection.
_Avoid_: Master node, pilot node, control node

**Distributing coupling**:
The CalculiX `*DISTRIBUTING COUPLING` constraint that spreads the reference node's load over the tip face without stiffening it, so there is no load singularity and no twisting.
_Avoid_: Kinematic coupling, rigid link, MPC

**Web-centreline tip node**:
The tip-face node on the web centreline at the section centroid, whose deflection is compared with the reference node's to show the coupling is not distorting the result.
_Avoid_: Centre node, check node

**Midspan flange nodes**:
The nodes on the outer surfaces of the top and bottom flanges at x = L/2, where the bending stress is measured away from the St-Venant zones at either end.
_Avoid_: Stress nodes, midspan nodes

**Mesh level**:
One of three named mesh refinements (coarse, medium, fine), each defined by the element counts through the flange thickness, along the web height and along the length.
_Avoid_: Mesh density, refinement, resolution

## Analytical solution

**Shear area**:
The effective area resisting transverse shear in the Timoshenko deflection, taken as the web area between flange mid-planes, A_s = (h − t_f)·t_w, with shear coefficient κ = 1.
_Avoid_: Effective area, web area

**Euler-Bernoulli deflection**:
The bending-only tip deflection δ_EB = PL³/(3EI), reported for information as the baseline.
_Avoid_: Classical deflection, beam-theory deflection

**Timoshenko deflection**:
The tip deflection including shear, δ = PL³/(3EI) + PL/(κ·G·A_s), which is the deflection target for pass/fail.
_Avoid_: Shear-corrected deflection

**Midspan stress**:
The bending stress σ_xx at the outer flange fibres at x = L/2, with analytical target σ = P·(L/2)·c/I and c = h/2.
_Avoid_: Max stress, peak stress

**Root stress**:
The peak stress at the root face, reported for information only because the fixed end disturbs it.
_Avoid_: Support stress

## Results

**Target**:
The analytical value an FE result is checked against: the Timoshenko deflection for deflection and the midspan stress for stress.
_Avoid_: Reference value, expected value

**Error**:
The signed percentage difference (FE − analytical) / analytical × 100.
_Avoid_: Deviation, discrepancy

**Verdict**:
PASS when the fine mesh level's deflection error and both midspan stress errors are within ±2 %, otherwise FAIL.
_Avoid_: Status, outcome
