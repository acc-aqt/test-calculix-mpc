---
status: accepted
---

# Check the LE10 thick plate against a published reference value instead of a closed-form target

## Context

The first three benchmarks (ADR 0001, ADR 0002, ADR 0003) check CalculiX against closed-form beam theory on slender cantilevers. Their stress states are essentially uniaxial bending stress plus shear, which says little about how C3D20R bricks handle a genuinely three-dimensional stress state. Problems with such a state rarely have a closed-form answer. The NAFEMS LE10 thick plate (#30) has none: a quarter of an elliptic annulus, 600 mm thick, under 1 MPa on its top face, whose target is σ_yy at point D on the hole edge. The value comes from a converged reference FE solution, not from a formula. The plate's stress state is fully three-dimensional, but at D itself the exact state is biaxial: D lies on the traction-free hole surface (normal −x) and the loaded top face, so σ_xx and every shear component vanish there and σ_zz = −p.

## Decision

- **Target.** The LE10 benchmark checks σ_yy(D) against the published value −5.38 MPa. The reference module returns it as a constant; nothing in the repo derives it.
- **Provenance.** The value is taken from four vendor verification documents that agree on it:
  - the Abaqus Benchmarks Manual, [LE10 thick plate pressure](https://abaqus.uclouvain.be/English/SIMACAEBMKRefMap/simabmk-c-le10.htm);
  - Altair OptiStruct verification, [NAFEMS LE10](https://help.altair.com/hwsolvers/os/topics/solvers/os/nafems_test_problem_le10_r.htm);
  - Seamplex/Fino, [case 012 (NAFEMS LE10)](https://www.seamplex.com/fino/cases/012-nafems-le10);
  - the COMSOL [thick_plate model](https://doc.comsol.com/6.4/doc/com.comsol.help.models.sme.thick_plate/thick_plate.html).

  The primary source, NAFEMS *The Standard NAFEMS Benchmarks* (TNSB) Rev. 3, was not consulted. The report says so.
- **Sign convention.** The target is signed and compressive, −5.38 MPa. Some sources quote the magnitude 5.38 MPa for "the stress at D". The error is signed against the signed target, as in the other benchmarks, so a result with the wrong sign has an error near −200 % and cannot pass.
- **Measured quantity.** σ_yy(D) is ccx's nodal value from the `.frd`, extrapolated from the integration points and averaged, because that is what published FE results compare. The nearest integration-point value is reported for information.
- **Sanity guards replace the analytical cross-checks.** Without a formula to fall back on, a quietly wrong deck could still land near −5.38 MPa. Guards on the mesh volume and the reaction balance (#31) stop such a run before it writes a report.

## Considered options

- **A closed-form thick-plate or elasticity solution.** Rejected: none exists for this geometry and support, and the point of the benchmark is a state no formula captures.
- **Our own converged value from a very fine mesh as the target.** Rejected as the target: it would check ccx against itself. A Richardson estimate over the three mesh levels is reported beside the published value instead, so a disagreement shows.
- **Waiting for TNSB Rev. 3.** Not done: it is not openly available. Four independent vendor documents quoting the same value were judged enough, with the caveat stated.

## Consequences

- The target's strength is that of its sources. The published hex20 results scatter around it:
  - Abaqus, fine mesh: C3D20R +2.8 %, C3D20 +4.8 %;
  - Altair, fine mesh: −3.6 %;
  - Fino: −0.4 %, converging to −5.379 MPa;
  - on the coarse NAFEMS mesh: Abaqus +47 % (C3D20R) and +25 % (C3D20), Altair about +1 %.

  The ±3 % tolerance on the fine C3D20R level (#32) sits inside that scatter. Our mesh levels are not the NAFEMS meshes, whose element counts could not be recovered from open sources, so the published coarse-mesh scatter does not carry over to our coarse level.
- The u_z = 0 line support on EE′ is singular, as COMSOL notes, so stresses near it depend on the mesh. Point D is far from it; the singularity is expected and is not a defect.
- The GLOSSARY header no longer says the suite checks only closed-form beam theory, and the LE10 terms use "published reference value" for the target.
