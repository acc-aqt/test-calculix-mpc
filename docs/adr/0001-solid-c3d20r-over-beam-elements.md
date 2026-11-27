---
status: accepted
---

# Model the I-beam with solid C3D20R elements, not B32 beam elements

## Context

The benchmark checks a CalculiX cantilever, set up and inspected through the `calculix-mcp-rs` MCP server, against Euler-Bernoulli and Timoshenko beam theory. A cantilever of an IPE 200 section is the textbook case for beam elements, so a reader will expect B32 elements with a `*BEAM SECTION`. We need the model to be one the MCP can actually check, mesh and query.

## Decision

Model the IPE 200 as a **solid I-beam** of 20-node C3D20R bricks covering both flanges and the web, without fillet radii. The reasons:

- The `calculix-mcp-rs` tools target solid meshes and ignore beam and shell elements in face selection.
- The MCP has no documented support for beam sections.
- CalculiX expands beam elements into solids internally anyway, so a beam model would not avoid a solid mesh, only hide it.
- Comparing a 3D solid against 1D beam theory is a stronger check than comparing a 1D beam element against the same 1D theory it is built on.

## Considered options

- **B32 beam elements with `*BEAM SECTION`.** Rejected: the MCP cannot select their faces or confirm their section, and agreement with beam theory would say little about the toolchain.
- **Both a solid and a beam model, compared with each other.** Rejected for now: it doubles the deck generator and the result extraction for a model the MCP cannot inspect. It is out of scope for the benchmark and can be added later as a separate decision.

## Consequences

- The load cannot be applied to a single beam node, so it goes in through a **distributing coupling** from the **tip face** to a **reference node** at the centroid, and the support is the fully fixed **root face**.
- The fixed root face causes a St-Venant disturbance, so stress is checked at midspan and the root stress is reported for information only.
- Results depend on the **mesh level**, so the benchmark runs three levels and bases the **verdict** on the fine one.
- Without fillet radii the FE section matches the hand-calculated I and A_s exactly, but not the rolled IPE 200 tables.
