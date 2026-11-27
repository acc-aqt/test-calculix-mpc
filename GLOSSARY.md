# CalculiX Cantilever Benchmarks

Reproducible checks of CalculiX, set up and inspected through the `calculix-mcp-rs` MCP server, against closed-form beam theory for solid cantilevers: an IPE 200 I-beam and a CHS 168.3 × 8 tube with a tip load, and the IPE 200 I-beam with a tip torque. Terms used by both benchmarks come first, then the terms of each benchmark.

## Shared

### Model

**Root face**:
The cross-section face at x = 0, where every degree of freedom is fixed to form the cantilever support.
_Avoid_: Clamped end, fixed face, support face

**Tip face**:
The cross-section face at x = L, through which the tip load is introduced into the solid.
_Avoid_: Free end, load face

**Reference node**:
A single node at the tip-face centroid that carries the tip load and whose vertical displacement is the measured tip deflection.
_Avoid_: Master node, pilot node, control node

**Distributing coupling**:
The CalculiX `*DISTRIBUTING COUPLING` constraint that spreads the reference node's load over the tip face without stiffening it, so there is no load singularity and no twisting.
_Avoid_: Kinematic coupling, rigid link, MPC

**Mesh level**:
One of three named meshes of a benchmark (coarse, medium, fine), each defined by element counts in three directions; each benchmark names its own directions.
_Avoid_: Mesh density, refinement, resolution

### Analytical solution

**Euler-Bernoulli deflection**:
The bending-only tip deflection δ_EB = PL³/(3EI), reported for information as the baseline.
_Avoid_: Classical deflection, beam-theory deflection

**Timoshenko deflection**:
The tip deflection including shear, δ = PL³/(3EI) + PL/(κ·G·A_s), which is the deflection target for pass/fail. Each benchmark sets its own shear coefficient κ and shear area A_s.
_Avoid_: Shear-corrected deflection

**Midspan stress**:
The bending stress σ_xx at the outer fibres at x = L/2, with analytical target σ = P·(L/2)·c/I, where c is the outer fibre distance (h/2 for the I-beam, r_o for the tube).
_Avoid_: Max stress, peak stress

**Root stress**:
The peak stress at the root face, reported for information only because the fixed end disturbs it.
_Avoid_: Support stress

### Results

**Target**:
The analytical value an FE result is checked against: the Timoshenko deflection for deflection and the midspan stress for stress.
_Avoid_: Reference value, expected value

**Error**:
The signed percentage difference (FE − analytical) / analytical × 100. Stress errors compare signed values: the analytical midspan stress is +σ at the top fibre (tension) and −σ at the bottom fibre (compression), so a fibre with the wrong sign has a large error. Deflection errors compare magnitudes.
_Avoid_: Deviation, discrepancy

**Verdict**:
PASS or FAIL for a full run, decided on the fine mesh level by the rule of each benchmark below.
_Avoid_: Status, outcome

## IPE 200 cantilever

**Solid I-beam**:
The IPE 200 section (without fillet radii) modelled as 20-node C3D20R brick elements covering both flanges and the web, extruded along the beam length.
_Avoid_: Beam model, 3D beam

**Web-centreline tip node**:
The tip-face node on the web centreline at the section centroid (which is also the shear centre), whose deflection is compared with the reference node's to show the coupling is not distorting the result.
_Avoid_: Centre node, check node

**Midspan flange nodes**:
The nodes on the outer surfaces of the top and bottom flanges at x = L/2, where the bending stress is measured away from the St-Venant zones at either end.
_Avoid_: Stress nodes, midspan nodes

**IPE 200 mesh level**:
Element counts through the flange thickness, along the web height and along the length.

**Shear area**:
The effective area resisting transverse shear in the IPE 200 Timoshenko deflection, taken as the web area between flange mid-planes, A_s = (h − t_f)·t_w, with shear coefficient κ = 1.
_Avoid_: Effective area, web area

**IPE 200 verdict**:
PASS when the fine mesh level's deflection error and both midspan stress errors are within ±2 %, otherwise FAIL.

## Tube cantilever

**Solid tube**:
The CHS 168.3 × 8 section modelled as a mapped mesh of 20-node C3D20R brick elements around the circumference, through the wall and along the length, closed on itself with shared nodes and midside nodes on the true arcs.
_Avoid_: Pipe model, shell model

**Circumferential divisions**:
The number of elements around the circumference of the solid tube. It must be a multiple of 4 so that the top fibre, bottom fibre and neutral axis (0°, 90°, 180°, 270°) fall on nodes.
_Avoid_: Segments, sectors

**Tube mesh level**:
Circumferential divisions, element counts through the wall and along the length, e.g. coarse 8/1/10.

**Section discretisation error**:
The part of the FE error that comes from approximating the circular section with quadratic arcs over a finite number of circumferential divisions, measured because the targets use the exact annulus.
_Avoid_: Polygon error, geometry error

**Cowper shear coefficient**:
Cowper's (1966) shear coefficient for a hollow circle, κ = 6(1+ν)(1+m²)² / ((7+6ν)(1+m²)² + (20+12ν)m²) with m = r_i/r_o, used with the full annulus area as A_s in the tube's Timoshenko deflection. The thin-wall value κ = 0.5 is reported for information only.
_Avoid_: Shear factor, shear correction

**Tip-face mean deflection**:
The mean u_y of all tip-face nodes, compared with the reference node's deflection to show the coupling is not distorting the result (the tube has no material at its centroid, so there is no centreline node to compare with).
_Avoid_: Average tip deflection, centre deflection

**Midspan outer-surface nodes**:
Every node on the outer surface of the solid tube at x = L/2, corner and midside, used for the midspan stress fit.
_Avoid_: Stress nodes, midspan ring

**Top-fibre and bottom-fibre nodes**:
The midspan outer-surface nodes at y = r_o and y = −r_o, whose single-node σ_xx is shown next to the midspan stress fit.
_Avoid_: Top node, bottom node

**Midspan stress fit**:
The least-squares fit σ_xx = a·y + b over every midspan outer-surface node, giving the measured midspan stress a·r_o + b at the top fibre and −a·r_o + b at the bottom fibre. The intercept b lets the two fibres differ, so each is checked on its own.
_Avoid_: Mean stress, regression stress

**Observed order**:
The convergence order p = ln((e_c − e_m)/(e_m − e_f)) / ln 2 from the signed errors of the coarse, medium and fine mesh levels, reported for information and shown as not available when the ratio is not positive or a level is missing.
_Avoid_: Convergence rate

**Tube verdict**:
PASS when the fine mesh level's deflection error and the midspan stress fit errors at both fibres are within ±1 %, and the midspan stress fit error magnitude strictly decreases coarse → medium → fine at both fibres; otherwise FAIL. There is no verdict unless all three mesh levels were run.

## IPE 200 torsion

The solid I-beam, root face, tip face, mesh level, IPE 200 mesh level, error and target carry over from above. The reference node carries the torque instead of a tip load, and it is not measured (see **Distributing *COUPLING**).

**Torque**:
The tip load of the torsion benchmark, T = 5·10⁵ N·mm about +x by the right-hand rule, applied as `*CLOAD` on DOF 4 of the reference node. It turns the top flange towards +z.
_Avoid_: Moment, twisting moment, torsional load

**Tip twist**:
The twist φ(L) at the tip face, the measured value checked against the Vlasov twist.
_Avoid_: Tip rotation, end rotation, rotation angle

**Twist**:
How far a cross-section turns about the x axis, φ(x) in rad, measured as φ = (u_z,top − u_z,bottom)/h_m from the flange mid-plane centre nodes at each x station; positive for the torque about +x.
_Avoid_: Rotation, angle of twist

**St-Venant torsion**:
Torsion carried by shear stresses circulating in the section alone, with the section free to warp everywhere; it gives the twist φ_SV = T·x/(GJ), reported for information.
_Avoid_: Uniform torsion, pure torsion, free torsion

**Warping**:
The axial displacement u_x of a twisted open section, varying linearly across each flange width and changing sign at the web. The fixed root face restrains it; the tip face is free to warp.
_Avoid_: Out-of-plane displacement, axial distortion

**Vlasov twist**:
The twist of mixed torsion with warping restrained at the root and free at the tip, φ(x) = T/(GJ)·[x − (sinh λL − sinh λ(L−x))/(λ·cosh λL)]. Its tip value is the twist target.
_Avoid_: Warping-torsion twist, non-uniform twist, Timoshenko torsion

**Torsion constant**:
The St-Venant torsion constant of the thin-walled section, J = (2·b·t_f³ + (h − 2t_f)·t_w³)/3.
_Avoid_: Polar moment, J_t, torsional inertia

**Warping constant**:
I_w = I_f·h_m²/2, with I_f = t_f·b³/12 the second moment of one flange about its own vertical axis and h_m = h − t_f the distance between the flange mid-planes.
_Avoid_: Sectorial moment of inertia, C_w, Γ

**Torsion parameter**:
λ = √(GJ/(E·I_w)). λL ≈ 3.7 for this beam says how far warping restraint reaches: it cuts the tip twist to about 73 % of St-Venant.
_Avoid_: Torsion coefficient, decay constant

**Sectorial coordinate**:
The thin-walled coordinate ω that gives the shape of the warping over the section, ω = y·z on the flange mid-planes, with magnitude h_m·b/4 at the four flange tips.
_Avoid_: Warping function, unit warping

**Warping stress**:
The normal stress σ_w = −E·y·z·φ''(x) from restrained warping, linear across each flange width and opposite in sign on the two edges of a flange and on the two flanges. Its flange-tip magnitude E·ω·φ'' at x = L/4 is the warping stress target.
_Avoid_: Bimoment stress, warping normal stress, σ_xx

**Flange-tip edges**:
The four edges along x at the outer ends of the flange widths (y = ±h/2 … ±(h/2 − t_f), z = ±b/2), where warping stress is largest.
_Avoid_: Flange corners, flange edges

**Flange mid-plane centre nodes**:
The nodes on each flange mid-plane (y = ±h_m/2) over the web footprint (|z| ≤ t_w/2), whose mean u_z at each x station gives the twist. Over the web footprint rather than only at z = 0, because a mesh level with an odd number of elements through the flange thickness has no node at the centre.
_Avoid_: Centre-line nodes, twist nodes

**Distributing *COUPLING**:
The CalculiX `*COUPLING` + `*DISTRIBUTING` (DOFs 1–6) constraint that spreads the reference node's torque over a face-based tip surface without stiffening it, so the tip face can warp. Unlike `*DISTRIBUTING COUPLING`, which silently drops a moment, it carries the torque. ccx reports the reference node's displacement as zero under it. See ADR 0003.
_Avoid_: Coupling, MPC, distributing coupling (that is the `*DISTRIBUTING COUPLING` card above)

**Zero-twist guard**:
The check that stops a run whose |φ(L)| is below 1 % of the St-Venant tip twist with an error and no report, so a load introduction that drops the torque cannot pass quietly.
_Avoid_: Sanity check, zero check
