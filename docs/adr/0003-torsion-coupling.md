---
status: accepted
---

# Introduce the torsion benchmark's torque through `*COUPLING` + `*DISTRIBUTING`, and measure twist on the beam

## Context

The IPE 200 torsion benchmark (#23) applies a torque at the tip of the solid I-beam and compares the tip twist with Vlasov mixed torsion. The bending benchmarks introduce their tip load through `*DISTRIBUTING COUPLING` on a DCOUP3D reference node (ADR 0001). The first try at torsion reused that deck with the force replaced by a moment on DOF 4 of the reference node. In ccx 2.24 it solved with return code 0 and no warning, and every displacement in the `.frd` was exactly 0: the moment was dropped. The ccx 2.24 manual (§7.42) says `*DISTRIBUTING COUPLING` is for translational loading only.

## Decision

- **Load introduction.** The torque goes in through `*COUPLING, REF NODE=…, SURFACE=…` followed by `*DISTRIBUTING` with DOFs 1–6, and `*CLOAD` on DOF 4 of the reference node. The surface is a face-based `*SURFACE` of the tip element faces (S4, the +x face of each tip element), because ccx rejects a node surface for `*DISTRIBUTING` ("a nodal surface is not allowed").
- **No reference-node measurement.** Under this coupling, as under `*DISTRIBUTING COUPLING`, ccx prints the reference node's U as 0 in the `.dat` and leaves it out of the `.frd`. The twist is measured on the beam instead: φ = (u_z,top − u_z,bottom)/h_m from the flange mid-plane centre nodes.
- **Tip free to warp.** A distributing `*COUPLING` does not stiffen the tip face, so it warps freely, which is the Vlasov boundary condition at the tip. A rigid coupling or a mean-rotation MPC tying all six DOFs would restrain warping there and change the target.
- **Zero-twist guard.** A run whose |φ(L)| is below 1 % of the St-Venant tip twist stops with an error and writes no report. A test runs the `*DISTRIBUTING COUPLING` variant under real ccx and expects the guard to trip, so a regression to that card cannot pass quietly.

## Considered options

- **`*DISTRIBUTING COUPLING` with the moment on DOF 4.** Rejected: it drops the moment without a warning.
- **A force couple on the flanges.** Rejected: it puts point loads on the tip face and needs a choice of nodes and lever arm, where the coupling takes the moment as it is.
- **A mean-rotation MPC on the tip face** (manual §8.7.1) as the load path or as an independent φ(L) measurement. Not chosen for the load path because of the warping restraint above; a cross-check measurement may follow as a separate issue.
- **Reading φ(L) from the reference node's rotation.** Not possible: ccx reports no displacement for it.

## Consequences

- The benchmark depends on `*COUPLING`/`*DISTRIBUTING` behaving as the ccx 2.24 manual describes; the zero-twist guard catches a version where it does not.
- The FE beam twists more than the thin-walled target: on the coarse mesh φ is about 2.4 % above Vlasov at L/2, 4.2 % at 0.9L and 5 % at the tip, growing smoothly from root to tip. The cause is the torsion constant, not the coupling. Σbt³/3 without the end correction overestimates J, so the solid is softer in St-Venant torsion, and St-Venant torsion carries more of the torque towards the tip. With the end-corrected J the Vlasov tip twist is 0.27313 rad, and the coarse φ(L) is about 1 % above it. A least-squares rigid-rotation fit over all section nodes gives the same twist as the flange mid-plane centre nodes to within 0.3 %, so the section does not distort measurably. The tip-twist tolerance is therefore ±8 %, wider than the ±5 % for the warping stress.
- The coupling's force distribution differs from the St-Venant shear flow, and the load-introduction zone it causes is not short. The three-level run with figures (#26) measured it:
  - the flange-tip warping stress stays above Vlasov from about x ≈ 1200 mm to the tip, with the fine level more than 2 % above the end-corrected curve;
  - it levels off at about 12–17 MPa between x = 2000 and 2800 mm, where Vlasov falls to a few MPa, and drops to near zero only at the tip face;
  - all three mesh levels agree, so it is not a discretisation error;
  - x = L/4 is clear of it: there the fine level is −0.47 % from the end-corrected curve, so the stress verdict is not affected.

  The φ(x) gap also grows past the end-corrected line over the last third of the length, so the disturbance may add to the tip-twist gap there, on top of the J approximation above. The likely cause, not proven, is that the coupling brings most of the torque into the flanges as lateral shear, where Vlasov carries it almost entirely as St-Venant shear at a free tip; in an open section that difference settles over about 1/λ ≈ 810 mm rather than locally. Follow-up: #29.
- The reference node's `*NODE PRINT` is kept in the deck only to show, in a test, that it stays zero.
