---
status: accepted
---

# Add a CHS 168.3 × 8 solid tube cantilever with exact-circle targets and Cowper κ

## Context

The IPE 200 benchmark (ADR 0001) passes, but its convergence study says almost nothing: every edge of the I-section is straight and the bending field is linear, so C3D20R bricks reproduce it almost exactly and the coarse, medium and fine mesh levels agree to within 0.01 %. Its shear target, κ = 1 with A_s = (h − t_f)·t_w, is an approximation, so the shear term is not tested sharply either. We want a second case where refining the mesh visibly matters and the shear target has a closed form.

## Decision

Add a **solid tube** benchmark of an EN 10210 CHS 168.3 × 8 cantilever, L = 1000 mm, in its own folder next to the IPE 200 one, keeping the solid C3D20R approach of ADR 0001. Where it differs from ADR 0001:

- **Exact-circle targets.** A and I are those of the exact annulus. The mesh approximates the circle with quadratic arcs, so the FE error includes the **section discretisation error**, which is what the convergence study measures.
- **Cowper κ.** The Timoshenko deflection uses the **Cowper shear coefficient** for a hollow circle with the full annulus area, a closed-form value instead of the IPE 200's κ = 1 web-area approximation. The Euler-Bernoulli deflection and the thin-wall κ = 0.5 deflection are reported for information, so the report shows that the FE result tells them apart.
- **Midspan stress fit.** The midspan stress is the least-squares fit σ_xx = a·y + b over every midspan outer-surface node instead of a mean over a few nodes, so it uses every node and does not depend on where a single node sits. The top fibre is a·r_o + b and the bottom fibre −a·r_o + b; the intercept b lets the two fibres come out different, so the check at each fibre is a real one rather than the same number twice. The single-node top and bottom fibre stresses are shown next to it.
- **L/D ≈ 6.** The tube is short enough that shear is about 5 % of the deflection, so the shear term is checked, while still being a slender beam.
- **Stricter verdict.** PASS needs the fine level within ±1 % of the Timoshenko deflection and of the fitted stress at both fibres, **and** the fitted stress error magnitude must strictly shrink coarse → medium → fine at both fibres. The deflection is not part of the shrink condition: it is within 0.1 % already at the coarse level and then sits on a modelling floor of about −0.007 % against Cowper's target, so it would fail on rounding noise.
- **C3D20R only**, as for the IPE 200.
- **Mapped mesh.** A mapped (x, r, θ) lattice whose θ index wraps so the seam shares nodes, with circumferential divisions a multiple of 4 and even length divisions so that the top and bottom fibres, the neutral axis and x = L/2 fall on nodes. Node coordinates are written with at most 14 significant digits and round-off below 1e-9 as 0, because `ccx` rejects full-precision values such as `4.66e-15` from cos(90°).

## Considered options

- **Refine or add levels to the IPE 200 benchmark.** Rejected: its straight-edged section converges at the coarse level whatever the refinement, so more levels would still show a flat line.
- **Thin-wall κ = 0.5 as the shear target.** Rejected: a prototype solve matched Cowper κ to 0.007 % but κ = 0.5 only to 0.30 %, so Cowper's value is the sharper target.
- **A longer tube.** Rejected: at L/D ≈ 18 shear is under 1 % of the deflection and the Timoshenko check would barely differ from Euler-Bernoulli.
- **Extracting a shared package for the geometry-independent modules.** Deferred: the `.frd` and `.dat` readers, palette and `ccx` functions are copied, and extracting them is a later, separate refactor.

## Consequences

- The tube's coarse level is visibly unconverged in stress (about +1.4 % fitted, +5 % single-node), so the convergence table and figure show a real curve.
- The tube has no material at its centroid, so the reference node is compared with the **tip-face mean deflection** instead of a centreline node.
- The two benchmarks share the shared glossary terms but each has its own mesh level directions, shear target and verdict rule.
