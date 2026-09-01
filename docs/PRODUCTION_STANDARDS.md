# IQR — Enterprise Productionization Standards

What "production-grade" means for an agentic AI validation platform, per the
current authoritative guidance (Microsoft Well-Architected Framework for AI,
the Foundry baseline reference architecture, the Cloud Adoption Framework's
AI security guidance, NIST AI RMF, ISO/IEC 42001) — mapped line-by-line to
IQR's current state with the concrete action that closes each gap.

Legend: ✅ in place · 🟡 partial (POC-grade) · ⬜ to do at the marked stage.

---

## 1. The standards landscape (what auditors and buyers ask for in 2026)

| Framework | What it is | Why it matters to IQR |
|---|---|---|
| **Azure Well-Architected — AI workloads** | Microsoft's five pillars (reliability, security, cost, operational excellence, performance) plus AI-specific principles: experimental mindset, explainable/ethical AI, guarding against model decay | The engineering bar for the workload itself |
| **Foundry baseline reference architecture (landing zone)** | Microsoft's reference for production Foundry workloads: private networking, identity-first access, IaC, recovery runbooks | The infrastructure bar for our Azure footprint |
| **CAF — Secure AI (PaaS)** | Concrete controls: Entra ID over keys, managed identities, Defender for Cloud AI threat protection, Prompt Shields, Purview, execution isolation | The security-control checklist |
| **NIST AI RMF** | Govern / Map / Measure / Manage; voluntary but a de-facto US procurement expectation | The governance vocabulary risk teams speak |
| **ISO/IEC 42001** | Certifiable AI management system standard; increasingly a buyer precondition | The certifiable wrapper if/when certification is pursued |

IQR's architecture already *is* an AI-governance system (frozen plans, citation
gate, replayable ledger, eval gates, HITL, governed learning), so most
framework asks map to existing mechanisms — the gaps are mostly
infrastructure hardening, not redesign.

---

## 2. Well-Architected pillars → IQR

| Pillar | Standard's ask | IQR now | Production action |
|---|---|---|---|
| Reliability | Graceful degradation, no single model dependency | ✅ Multi-backend fallback chain with visible attribution; offline stub keeps the close calendar unblocked; crashed checks abstain as gaps | ⬜ Add a second-region Foundry deployment to the chain |
| Security | Zero-trust, least privilege | 🟡 Easy Auth on the console; keys in gitignored env/app settings | See §4 ladder |
| Cost | Right-size models per task | ✅ Per-seat routing (economical checks / reasoning verifier / router for compile); pay-per-token; pausable analytics | ⬜ Budget alerts + APIM token quotas |
| Operational excellence | IaC, safe deployment, observability | 🟡 Provisioning scripts + replayable ledgers; manual zip deploy | ⬜ Bicep/Terraform + CI/CD (GitHub Actions: pytest + eval gates as the release gate); diagnostic logs to Log Analytics |
| Performance | Scale to workload | 🟡 Parallel check fan-out; single App Service worker | ⬜ Parsed-artifact cache (hash-keyed) before shadow-cycle scale; B-series plan when concurrency grows |
| **Model decay** (AI principle) | Detect drift over time | ✅ This is the eval harness's job: five gates on every change, batch mode with per-check stability; Golden Library turns every override into a permanent regression case | ⬜ Schedule a weekly batch eval as a canary |

---

## 3. Foundry baseline architecture → IQR footprint

| Baseline requirement | IQR now | Production action |
|---|---|---|
| Private endpoints for AI services, storage, search; BYO VNet | ⬜ Public endpoints (POC) | Private endpoints on Foundry, Search, Storage; console integrated into the VNet |
| Only one internet-exposed component (gateway) | 🟡 Console is the only exposed piece, gated by Easy Auth | Front with Application Gateway/WAF; egress via Azure Firewall |
| Lock the Foundry portal in production; manage by IaC | ⬜ Portal access open | Revoke portal access for non-admins; deployments only via pipeline |
| Resource locks + recovery runbook for stateful services | ⬜ | Delete-locks on Storage/Search; runbook for evidence-store and ledger recovery (content-addressing makes re-ingest deterministic — document it) |
| Customer-managed keys where mandated | ⬜ Platform-managed | CMK on Storage/Search if policy requires |

---

## 4. CAF Secure-AI controls → IQR

| Control family | Standard's ask | IQR action ladder |
|---|---|---|
| Identity | **Entra ID everywhere, no API keys**; managed identities for service-to-service; MFA + PIM for admins; Conditional Access | Pilot: managed identity for console→Storage/Search/Foundry, delete keys from app settings; Key Vault for anything that must stay secret. Roles: Reviewer / SME-Approver / Admin (the software enforces the SoD it audits) |
| AI gateway | Centralize model traffic via APIM: authn, quotas, monitoring | Production: route Foundry calls through APIM; per-seat quotas map cleanly to our seat abstraction |
| Model threat protection | Defender for Cloud AI threat protection; Prompt Shields; verify model provenance | Enable Defender AI plan on the Foundry resource. Note: IQR's strict tool-protocol + citation gate already neutralizes the *impact* of prompt injection (an injected model still cannot mint an uncited fact), but detection telemetry belongs on |
| Data governance | Data boundaries per audience; dataset isolation; Purview lineage | Evidence store is already content-addressed and single-purpose; add Purview registration of the storage account for classification/lineage when the org mandates it |
| Execution isolation | Isolate agent code execution, resource limits, full activity logging | ✅ by design: agents execute nothing — only whitelisted deterministic tools run, in-process, with every call ledgered; AGENT_MAX_STEPS caps loops. Document this as the compensating control |
| Agent inventory | Track all AI agents (Entra Agent ID) | Our agents are code-defined and version-controlled — the roster in the design doc + ledger attribution *is* the inventory; register in Entra Agent ID if Foundry-hosted agents are added |

---

## 5. NIST AI RMF functions → IQR mechanisms (the governance story)

| Function | Requirement | IQR mechanism |
|---|---|---|
| **Govern** | Policies, roles, accountability | Frozen SME-approved plans (what may run); role ladder; Golden Library release gate (eval + sign-off); three laws as codified policy enforced by tests |
| **Map** | Know the system's context and risks | Design doc v4; per-control risk framing via check modalities; sentinel's adversarial threat model |
| **Measure** | Quantify trustworthiness | Five-gate eval (recall, false exceptions, citation validity, abstention, reproducibility) + batch scoring with per-check confidence; the replayable ledger as evidence |
| **Manage** | Respond, improve, document | HITL exception queue; bandit-RL earned confidence steering review priority; Shadow→Assist→Primary per-control graduation; every override becomes a regression case |

For **ISO 42001**: the artifacts above (plans, ledgers, eval reports,
adjudication records, release sign-offs) are precisely the AIMS evidence a
certification audit samples — retain them under the records policy below.

---

## 6. Production readiness checklist (staged)

**Now (POC exit criteria — all done):** offline test suite green from a
fresh clone · five eval gates pass on live models · console gated by tenant
sign-in · secrets out of git · org-neutral public repo.

**Pilot:**
1. Managed identities replace every key; Key Vault; RBAC roles wired to console actions
2. CI/CD: pytest + `iqr.cli eval --batch 3` as the merge gate; zip deploy from pipeline only
3. Diagnostic settings → Log Analytics; budget alerts; Defender for Cloud AI plan
4. Weekly scheduled batch eval (canary for drift/decay)
5. Records retention: ledgers + packs immutable (WORM) with a defined period

**Production:**
6. Landing-zone alignment: VNet + private endpoints + App Gateway/WAF + Firewall egress
7. APIM AI gateway with per-seat quotas; portal lockdown; IaC only
8. Resource locks + recovery runbook; CMK if mandated
9. DR: second-region model deployment in the fallback chain; storage GRS
10. Governance pack for audit: this document + design doc v4 + eval history + adjudication log — the NIST/ISO evidence set

---

## Sources

- [Azure Well-Architected Framework — AI workloads](https://learn.microsoft.com/en-us/azure/well-architected/ai/)
- [Baseline Azure AI Foundry chat reference architecture in a landing zone](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-azure-ai-foundry-landing-zone)
- [Cloud Adoption Framework — Secure Azure PaaS for AI](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai/platform/security)
- [NIST AI Risk Management Framework guides](https://www.aigovernancecore.com/blog/nist-ai-rmf-complete-guide) · [ISO 42001 vs NIST AI RMF](https://www.modelop.com/ai-governance/ai-regulations-standards/nist-vs-iso)
