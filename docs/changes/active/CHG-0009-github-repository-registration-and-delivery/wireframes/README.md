# Review wireframes

These are review-only Pencil artifacts governed by [CHG-0009](../../CHG-0009-github-repository-registration-and-delivery.md). They depict proposed CLI/dashboard behavior but are not CAP-linked current-product wireframes and do not authorize implementation. They are the pending-CHG stage of the [capability-wireframes lifecycle](../../../../../skills/software-development/capability-wireframes/SKILL.md): product `docs/product/wireframes/` artifacts begin only with the CAP, runtime surface, and executable evidence in an approved implementation slice. Their complete Hermes shell and Daidala Config navigation are copied from the historical [Config GitHub Projects concept](../../../../plans/hermes-dashboard-ux-live.pen), while the use-case workspace is new review content.

- [`repository-registration-and-delivery.pen`](repository-registration-and-delivery.pen) is the canonical editable source.
- [`exports/repository-registration.png`](exports/repository-registration.png) depicts the pre-rename Config → Repositories review design: explicit controller profile, safe secret readiness, URL inspection, a preview-only CLI, required GitHub least-rights guidance, and selected-profile secret-storage guidance.
- [`exports/delivery-authority.png`](exports/delivery-authority.png) depicts future branch delivery: independent evidence gates, the selected-profile credential setup gate, and a disabled confirmation action while credential/policy authority is unavailable.
- The live visual reference was inspected at [http://127.0.0.1:9119/daidala?view=config](http://127.0.0.1:9119/daidala?view=config); it is a local review reference, not implementation evidence or an authority surface.
- Reviewed source SHA-256: `eb9a50aebfc6dec3eb13ac59c234093b5a0eccc488f124acc79e04b953251d42`.
- No secret value, source command, vault item, raw environment-variable name, checkout path, or GitHub identifier beyond synthetic sample data may appear here.
