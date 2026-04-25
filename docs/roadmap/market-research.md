# The Architecture Of Trust

> Status: strategic market research for Aptitude product direction.
> This is not live registry API, schema, runtime, or implementation-sequence truth.
> Use [`aptitude-registry-prd.md`](aptitude-registry-prd.md) for registry requirements and [`../reference/api-contract.md`](../reference/api-contract.md) for the live HTTP contract.

Market research report on enterprise agentic registries and the definition of the Aptitude framework.

The rapid progression of large language models from passive knowledge engines to active agentic systems has fundamentally altered the requirements for enterprise software infrastructure.1 As organizations transition from experimentation to production-scale deployment, the management of the instructions, tools, and resources—collectively referred to as agentic artifacts—has emerged as a critical point of failure.3 The current market landscape for skills marketplaces and registries, exemplified by developer-centric platforms such as Vercel’s skills.sh and emerging enterprise solutions from Google and JFrog, reveals a significant gap in centralized governance and unified control.3 This report defines Aptitude as a walled-garden skills registry and gateway specifically engineered for the enterprise, focusing on the rigorous governance, granular visibility, and deterministic control required to operate autonomous agentic workforces at scale.

## **The Evolution of the Agentic Artifact Ecosystem**

The concept of "agent skills" represents a paradigm shift in how AI behavior is authored and distributed. Rather than relying on monolithic system prompts that consume excessive context and suffer from instructions drift, modern agentic architectures utilize modular, versioned packages of procedural knowledge.7 These packages, often defined by the open "Agent Skills" standard originally pioneered by Anthropic, package instructions, reference materials, and executable scripts into a single unit.8

The primary problem addressed by these artifacts is the "blank slate" problem.7 Without specific context regarding organizational standards, design systems, and deployment rules, an AI agent remains generic and inefficient.7 By providing a library of reusable context—the "npm moment" for agentic behavior—registries allow agents to load specific expertise only when a task requires it, a process known as progressive disclosure.7

### **The Open Marketplace Landscape: Vercel and GitHub**

Vercel’s skills.sh represents the leading open ecosystem for these capabilities.5 It provides a directory of community-contributed and official skills that enhance AI coding assistants with specialized expertise in frameworks like React and Next.js.5 The distribution model is decentralized and CLI-first, allowing developers to install skills via commands such as npx skills add \<owner/repo\>.5 This model prioritizes developer velocity and ease of discovery, supporting over 18 agents including Claude Code, GitHub Copilot, and Cursor.5

GitHub’s approach, through tools like skr (Skill Registry), integrates skills management directly into the Git workflow.13 The skr tool treats skills as Open Container Initiative (OCI) artifacts, enabling distribution via standard registries like GitHub Packages or Docker Hub.13 This architectural choice positions agentic artifacts as first-class citizens of the software supply chain, aligning their management with existing DevOps practices.13

| Platform | Distribution Model | Target Audience | Primary Focus |
| :---- | :---- | :---- | :---- |
| **skills.sh (Vercel)** | CLI-based Git ingestion | Web Developers | Reusable coding context and patterns 5 |
| **GitHub Skills Registry** | OCI Artifacts / Git | Enterprise Developers | Supply chain integration and CI/CD 13 |
| **Anthropic / Claude** | ZIP upload / API / Local | AI Practitioners | High-fidelity tool and document manipulation 8 |
| **OpenClaw / ClawHub** | Community Registry | Open Source Users | Cross-platform personal AI assistance 15 |

### **Structural Anatomy of an Agentic Artifact**

An agentic artifact is more than a simple text file; it is a complex directory structure that defines both the "what" and the "how" of agentic performance. The standard structure of a skill package, as analyzed in the research material, typically includes the following components:

The core of the artifact is the SKILL.md file, which contains YAML frontmatter for metadata and Markdown for procedural instructions.7 The frontmatter must include a unique name and a concise description, which the agent uses during the discovery phase to determine if the skill is relevant to the user’s request.7

In addition to text instructions, complex skills include a scripts/ directory containing executable code (e.g., Python or bash) that the agent can run to perform deterministic operations.7 This is critical for tasks that require exactness, such as form validation or database migrations, where the probabilistic nature of an LLM might lead to errors.8 Furthermore, a references/ directory houses static materials like API schemas, templates, and style guides that the agent can read on-demand without consuming tokens until the moment of access.7

## **The Governance Imperative in Enterprise Agentic AI**

The transition from individual developer tools to enterprise-wide agentic workforces introduces systemic risks that public marketplaces are not equipped to handle.2 The OWASP Top 10 for Agentic Applications (2026) highlights risks such as goal hijacking, tool misuse, and cascading failures.2 When an agent is granted the autonomy to execute trades, manage infrastructure, or access sensitive customer data, the registry governing its capabilities must be a fortified "walled garden".3

### **Strategic Challenges in Unmanaged Environments**

Without a centralized registry like the proposed Aptitude framework, organizations face several critical challenges. The "version control gap" occurs when different teams use different versions of the same prompt or script, leading to inconsistent outputs and unidentifiable regressions.1 The "security surface" expands as agents are allowed to pull unvetted skills from public repositories, potentially introducing malicious instructions that could lead to data exfiltration.4 Finally, the "auditability" requirement of modern regulations, such as the EU AI Act, necessitates a clear lineage for every action taken by an agent, mapping back to the specific artifact that authorized the behavior.2

| Risk Category | Impact in Agentic Systems | Mitigation Requirement |
| :---- | :---- | :---- |
| **Malicious Instruction Injection** | Agents perform unauthorized actions contrary to organizational policy. | Static and dynamic analysis of all registry artifacts.4 |
| **Identity Abuse** | Agents use static credentials to access resources without a human-in-the-loop. | Cryptographic agent identities with scoped permissions.6 |
| **Token Consumption Runaway** | Inefficient autonomous loops lead to massive, unexpected costs. | Real-time token consumption monitoring and budget capping.18 |
| **Data Leakage** | Context from one session is improperly shared with another. | Sandboxed execution environments and clear context boundaries.15 |

## **Defining Aptitude: The Walled Garden Skills Registry**

Aptitude is defined as a sovereign enterprise gateway and registry designed to function as the single source of truth for all agentic artifacts within an organization.3 It moves beyond the concept of a "marketplace" for discovery and establishes itself as a "control plane" for governance.19 The framework is built upon three pillars: rigorous ingestion governance, centralized resource visibility, and deterministic runtime control.

### **The Ingestion and Trust Workflow**

The primary function of the Aptitude registry is to serve as a "security airlock" for agentic resources.3 Unlike open platforms, Aptitude requires every artifact—whether a community skill, an internal script, or an MCP server configuration—to undergo a formal vetting process before it is promoted to the global enterprise scope.3 This process involves both automated scanning for malicious code and human-in-the-loop review by team or platform admins.4

The trust model in Aptitude is based on the concept of "verifiable provenance".3 Every artifact is cryptographically signed and versioned, ensuring that an agent is always executing a known-good, immutable set of instructions.16 This prevents "prompt drift," where small changes to an LLM's backend or an unversioned skill can lead to silent failures in production workflows.1

### **Architectural Components: Registry, Gateway, and Identity**

Aptitude operates at the network and application layers to provide a comprehensive security umbrella. The **Registry** acts as the library of approved assets, indexing every internal tool and skill.6 The **Gateway** sits between the agents and the resources they access, acting as the "air traffic control".19 It intercepts every request, evaluating it against organization-wide policies before allowing execution.19

The core of this architecture is **Agent Identity**.19 Aptitude assigns a unique, verifiable cryptographic identity to every agent, which is used as the principal for all authorization decisions.6 This enables high-fidelity attribution: an auditor can trace a specific database update back to the agent ID, the specific version of the skill artifact used, and the policy evaluation that permitted the action.6

## **Market Research: Competition and Alternatives**

The market for agentic resource management is consolidating around established infrastructure providers who are extending their platforms to support AI-native workflows.3

### **Microsoft / GitHub: The Integrated Development Moat**

Microsoft’s competitive advantage lies in its deep integration across the entire developer stack, from VS Code to GitHub to Azure.23 The **Agent Governance Toolkit** released by Microsoft provides a runtime security layer that addresses the OWASP Agentic Top 10 through deterministic policy enforcement.2 By using Open Policy Agent (OPA) and the Rego language, Microsoft allows organizations to define "Policy as Code" for their agents, ensuring that security is enforced at the kernel level rather than through fragile system prompts.2

### **Google Cloud: The Security-by-Design Ecosystem**

Google’s **Gemini Enterprise Agent Platform** offers a highly integrated suite of governance tools.6 The **Agent Gateway** and **Agent Registry** within Google Cloud provide a centralized entry and exit point for all agentic interactions, ensuring that traffic between agents and tools is encrypted via mTLS and subject to strict context-aware access policies.6 Google’s focus is on creating "hardened sandboxed environments" (Agent Sandbox) for code execution, protecting the host system from potentially rogue agent behavior.6

### **JFrog: The Software Supply Chain Standard**

JFrog has positioned its platform as the "System of Record" for the AI era.3 Leveraging its dominance in binary and artifact management, JFrog treats agent skills, models, and MCP servers as standard software artifacts that must be stored, scanned, and versioned in Artifactory.3 The **JFrog Agent Skills Registry**, validated through integration with NVIDIA’s Agent Toolkit, provides a "verifiable trust layer" that prevents the ingestion of malicious skills and ensures compliance with organizational policies.3

### **Comparison of Enterprise Solutions**

| Feature | Aptitude (Proposed) | Microsoft / GitHub | Google Cloud | JFrog |
| :---- | :---- | :---- | :---- | :---- |
| **Governance Hub** | Centralized Walled Garden | GitHub Packages / OPA | Agent Registry / Gateway | Artifactory / Xray |
| **Policy Enforcement** | Real-time Gateway Interception | Agent Governance Toolkit | Agent Gateway / IAM | Policy-based Xray Gating |
| **Primary Moat** | Sovereign Gateway Control | Integrated Dev Experience | End-to-End Cloud Security | Supply Chain Provenance |
| **Interoperability** | Framework Agnostic | Azure / GitHub Focused | GCP Ecosystem Focused | Universal Artifact Support |
| **Risk Management** | Agentic Token Control | OWASP Top 10 Mapping | Agent Sandbox Isolation | Malware / Vulnerability Scan |

## **The Competitive Moat for Aptitude**

To survive in a market dominated by incumbents, Aptitude must build a moat based on **Sovereign Interoperability** and **Deterministic Resource Governance**. While cloud providers offer "security-by-design" within their own ecosystems, large enterprises operate in hybrid and multi-cloud environments.20

### **Pillar 1: Multi-Cloud Gateway Sovereignty**

Aptitude’s primary moat is its ability to serve as a cross-platform gateway that governs agentic traffic regardless of where the agent is hosted (e.g., AWS Bedrock, Google Vertex, or an on-premise Ollama instance).21 By normalizing the interface between disparate agent frameworks (LangChain, CrewAI, AutoGen) and enterprise resources, Aptitude prevents vendor lock-in and provides a unified audit trail.2

### **Pillar 2: Agentic Token Control and Financial Visibility**

As autonomous agents begin to operate 24/7, unmanaged token consumption becomes a significant financial risk.18 Aptitude integrates an **Agentic Token Control** module, which provides real-time spend visibility and allows for the definition of "budgets" per agent or per business unit.18 This level of granular financial control is currently missing from most general-purpose AI platforms and is a key requirement for CFOs overseeing AI adoption.18

### **Pillar 3: Automated Artifact Evolution and Optimization**

The most advanced moat for Aptitude involves integrating research from the "Darwin Gödel Machine" (DGM) and "RoboPhD" into the registry.27 Aptitude can function not just as a static store, but as an active optimization environment where agents can iteratively improve their own artifacts—prompts, scripts, and configurations—based on performance diagnostics.27

The optimization of an artifact ![][image1] can be modeled as:

![][image2]  
where ![][image1] is the artifact, ![][image3] is the set of evaluation examples, and ![][image4] is the scoring function provided by the Aptitude evaluator.27 By hosting this evolutionary loop within the registry, Aptitude ensures that agentic performance improves over time without manual developer intervention.27

## **Technical Implementation and Standardization**

Aptitude defines a strict standard for what constitutes an "enterprise-ready" agentic artifact, extending the base SKILL.md format with mandatory metadata and security requirements.7

### **Extended Metadata for Governance**

Every artifact in the Aptitude registry must include an extended YAML header that defines its security posture and operational constraints.

* criticality: A rating (Low, Medium, High) that determines the level of human review required for deployment.
* access\_policy: A reference to a Rego policy that defines which agent identities are allowed to load the skill.25
* egress\_rules: A list of authorized URLs or IP ranges the skill’s scripts are permitted to access.8
* resource\_limits: Maximum CPU/Memory/Token usage allowed for a single execution of the skill.18

### **Policy-as-Code with Open Policy Agent (OPA)**

Aptitude utilizes OPA as its centralized policy decision point.25 When an agent attempts to invoke an artifact, the Aptitude Gateway sends a query to OPA containing the agent’s identity, the artifact ID, and the current context (e.g., time of day, user location).25 OPA evaluates this against the organization’s Rego-based policies and returns a deterministic "Allow" or "Deny".23

This architecture ensures that the agent—and the underlying LLM—has no say in the security decision.25 The reasoning engine may decide it needs to access a specific tool, but whether that access is granted is a purely administrative decision governed by the registry’s policies.25

## **Case Study: Agentic Resource Planning (ARP) in Finance**

The effectiveness of the Aptitude framework is best demonstrated in complex domains like financial operations, where the "Perceive, Reason, Act, and Learn" lifecycle of agentic AI must be tightly governed.30 In a scenario where an autonomous agent is tasked with accounts receivable optimization, the Aptitude registry provides the necessary guardrails.26

The agent uses a "Tax Accuracy" skill from the registry to validate invoice entries against regulatory requirements.26 The Aptitude Gateway monitors the agent’s calls to the ERP system, ensuring it only accesses records for authorized business units.19 If the agent encounters an edge case not covered by its current artifact, it can query the registry for a specialized "Exception Handling" skill, which is loaded on-demand via progressive disclosure.7 The result is a reduction in loan approval times from 12 hours to under one hour, while maintaining a 100% audit trail of every decision.26

## **Conclusion: The Sovereign Path to Agentic Maturity**

Market research into the current state of skills marketplaces reveals a critical fork in the road for the enterprise. While open marketplaces like Vercel’s skills.sh are excellent for accelerating developer experimentation, they lack the foundational security and governance required for autonomous operations.4 The proposed Aptitude framework addresses this by redefining the registry not as a library, but as a walled-garden gateway.3

By focusing on cryptographic identity, Policy-as-Code, and comprehensive artifact versioning, Aptitude provides the "verifiable trust layer" necessary to move from productivity tools to true agentic workforces.3 The competitive moat for such a platform lies in its sovereign, multi-cloud approach, ensuring that as agentic deployments grow from small tests to production-scale impact, the organization maintains absolute visibility and control over its digital labor.6

### **Final Product Definition and Roadmap**

Aptitude is defined as an Enterprise Agentic Artifact Platform consisting of:

1. **A Sovereign Registry**: A versioned, immutable store for skills, scripts, and MCP servers with built-in security scanning.3
2. **A Governance Gateway**: A runtime interceptor that enforces deterministic policies and monitors resource consumption.19
3. **An Identity Directory**: A system of record for cryptographic agent personas and their authorized scopes.6

The implementation roadmap for Aptitude should prioritize the establishment of the "Security Airlock" for artifact ingestion, followed by the deployment of the Gateway for runtime traffic inspection.2 By treating agentic artifacts as the real unit of release, promotion, and audit, organizations can securely embrace the AI era with the same rigor and scale that defined the success of the DevOps revolution.14

#### **Works cited**

1. How visual workflow automation can integrate with enterprise-scale agentic AI \- Medium, accessed on April 25, 2026, [https://medium.com/quantumblack/how-visual-workflow-automation-can-integrate-with-enterprise-scale-agentic-ai-6785ac7e7103](https://medium.com/quantumblack/how-visual-workflow-automation-can-integrate-with-enterprise-scale-agentic-ai-6785ac7e7103)
2. Introducing the Agent Governance Toolkit: Open-source runtime security for AI agents, accessed on April 25, 2026, [https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/)
3. JFrog Delivers Trust Layer for AI-Driven Software with NVIDIA, accessed on April 25, 2026, [https://investors.jfrog.com/news/news-details/2026/JFrog-Delivers-Trust-Layer-for-AI-Driven-Software-with-NVIDIA/default.aspx](https://investors.jfrog.com/news/news-details/2026/JFrog-Delivers-Trust-Layer-for-AI-Driven-Software-with-NVIDIA/default.aspx)
4. JFrog AI Catalog | Enterprise AI Governance & Security, accessed on April 25, 2026, [https://jfrog.com/ai-catalog/](https://jfrog.com/ai-catalog/)
5. Agent Resources \- Vercel, accessed on April 25, 2026, [https://vercel.com/docs/agent-resources](https://vercel.com/docs/agent-resources)
6. Introducing Gemini Enterprise Agent Platform | Google Cloud Blog, accessed on April 25, 2026, [https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform)
7. Agent Skills: Creating, Installing, and Sharing Reusable Agent Context \- Vercel, accessed on April 25, 2026, [https://vercel.com/kb/guide/agent-skills-creating-installing-and-sharing-reusable-agent-context](https://vercel.com/kb/guide/agent-skills-creating-installing-and-sharing-reusable-agent-context)
8. Agent Skills \- Claude API Docs \- Claude Console, accessed on April 25, 2026, [https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
9. Agent Skills Overview \- Agent Skills, accessed on April 25, 2026, [https://agentskills.io/home](https://agentskills.io/home)
10. Agent Skills – Codex | OpenAI Developers, accessed on April 25, 2026, [https://developers.openai.com/codex/skills](https://developers.openai.com/codex/skills)
11. Agent Skills \- Vercel, accessed on April 25, 2026, [https://vercel.com/docs/agent-resources/skills](https://vercel.com/docs/agent-resources/skills)
12. vercel-labs/skills: The open agent skills tool \- npx skills \- GitHub, accessed on April 25, 2026, [https://github.com/vercel-labs/skills](https://github.com/vercel-labs/skills)
13. Actions · GitHub Marketplace \- Publish Agent Skills, accessed on April 25, 2026, [https://github.com/marketplace/actions/publish-agent-skills](https://github.com/marketplace/actions/publish-agent-skills)
14. Jfrog Platform: DEVSECOPS, MLOPS, AND AI ARTIFACT MANAGEMENT \- Google Books, accessed on April 25, 2026, [https://books.google.com/books/about/Jfrog\_Platform.html?id=fZjk0QEACAAJ](https://books.google.com/books/about/Jfrog_Platform.html?id=fZjk0QEACAAJ)
15. rylena/awesome-openclaw \- GitHub, accessed on April 25, 2026, [https://github.com/rylena/awesome-openclaw](https://github.com/rylena/awesome-openclaw)
16. What is an Agent Skills Repository? \- JFrog, accessed on April 25, 2026, [https://jfrog.com/learn/ai-security/agent-skills-repository/](https://jfrog.com/learn/ai-security/agent-skills-repository/)
17. What Multi-Agent Outputs Need to Pass Enterprise Audit: Attributability and Reversibility, accessed on April 25, 2026, [https://www.augmentcode.com/guides/multi-agent-outputs-n-pass-enterprise-audit](https://www.augmentcode.com/guides/multi-agent-outputs-n-pass-enterprise-audit)
18. Portal26 Launches Industry-First AI Agentic Cost Controls to Prevent Runaway Spend, accessed on April 25, 2026, [https://www.businesswire.com/news/home/20260423349657/en/Portal26-Launches-Industry-First-AI-Agentic-Cost-Controls-to-Prevent-Runaway-Spend](https://www.businesswire.com/news/home/20260423349657/en/Portal26-Launches-Industry-First-AI-Agentic-Cost-Controls-to-Prevent-Runaway-Spend)
19. Kong Agent Gateway Is Here — And It Completes the AI Data Path, accessed on April 25, 2026, [https://konghq.com/blog/product-releases/kong-agent-gateway](https://konghq.com/blog/product-releases/kong-agent-gateway)
20. Agent Gateway overview | Gemini Enterprise Agent Platform \- Google Cloud Documentation, accessed on April 25, 2026, [https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview)
21. AI Agent Gateway \- Aembit, accessed on April 25, 2026, [https://aembit.io/glossary/ai-agent-gateway/](https://aembit.io/glossary/ai-agent-gateway/)
22. iflytek/skillhub: Self-hosted, open-source agent skill registry ... \- GitHub, accessed on April 25, 2026, [https://github.com/iflytek/skillhub](https://github.com/iflytek/skillhub)
23. microsoft/agent-governance-toolkit \- GitHub, accessed on April 25, 2026, [https://github.com/microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)
24. OpenAI Agent Skills download | SourceForge.net, accessed on April 25, 2026, [https://sourceforge.net/projects/openai-agent-skills.mirror/](https://sourceforge.net/projects/openai-agent-skills.mirror/)
25. Runtime Governance for AI Agents: Policy-as-Code with OPA \- Gökhan Gökalp, accessed on April 25, 2026, [https://gokhan-gokalp.com/runtime-governance-for-ai-agents-policy-as-code-with-opa/](https://gokhan-gokalp.com/runtime-governance-for-ai-agents-policy-as-code-with-opa/)
26. Agentic AI Use Cases: Transforming Enterprise Operations & Finance, accessed on April 25, 2026, [https://www.youtube.com/shorts/x9TUtbrIHE4](https://www.youtube.com/shorts/x9TUtbrIHE4)
27. RoboPhD: Evolving Diverse Complex Agents Under Tight Evaluation Budgets \- arXiv, accessed on April 25, 2026, [https://arxiv.org/pdf/2604.04347](https://arxiv.org/pdf/2604.04347)
28. Daily Papers \- Hugging Face, accessed on April 25, 2026, [https://huggingface.co/papers?q=Darwin%20G%C3%B6del%20Machine](https://huggingface.co/papers?q=Darwin+G%C3%B6del+Machine)
29. Why Open Policy Agent is the Missing Guardrail for Your AI Agents \- CodiLime, accessed on April 25, 2026, [https://codilime.com/blog/why-use-open-policy-agent-for-your-ai-agents/](https://codilime.com/blog/why-use-open-policy-agent-for-your-ai-agents/)
30. Agentic AI for Enterprises: How It Works, Use Cases & Best Practices \- LatentView, accessed on April 25, 2026, [https://www.latentview.com/glossary/agentic-ai/](https://www.latentview.com/glossary/agentic-ai/)
31. Agentic Resource Planning: The Future of Business Management with Agentic AI \- Citrin Cooperman, accessed on April 25, 2026, [https://www.citrincooperman.com/In-Focus-Resource-Center/Agentic-Resource-Planning-The-Future-of-Business-Management-with-Agentic-AI](https://www.citrincooperman.com/In-Focus-Resource-Center/Agentic-Resource-Planning-The-Future-of-Business-Management-with-Agentic-AI)
32. Agentic Repository: A New Paradigm for Software Delivery \- JFrog, accessed on April 25, 2026, [https://jfrog.com/learn/devops/agentic-repository/](https://jfrog.com/learn/devops/agentic-repository/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAZCAYAAAAIcL+IAAAAcklEQVR4XmNgGAUDCi4B8Qsg/gbETkB8F1UaAv4DcR0S/y9UDAV8xCIIMhldDCzwHIvYF2SBEKhgOrIgVKwSWWAHVBAZyEHFWJEFp0AFkcESJLGlMEFuJEEQcIPyYWIohjhDBUA4Gyr2D8oXgikaBTgBAJv8IeeKuEwpAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAXCAYAAAAGAx/kAAAAp0lEQVR4XmNgGAWkgmgg/gnE/5HwGyT5X2hyt5HksAI3BojCp2ji3ED8D4i50MTxApit6GIkg5UMEI3NUD6IzYyQJh4wMiBc9Q2IBVClSQO/GSAG2aNLkApOMkAMuocuQQqYBcTlDNgDnWjwF4hZoWxnBohBdxDSxIHPQCyKJkayq54AsQm6IAMiKdSgSyCDFgbUpP8SVZphLZIcCJ8D4kIUFaNgpAMAXYMxGjJZzX0AAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADkAAAAYCAYAAABA6FUWAAACd0lEQVR4Xu2Xz4tOURzGv/ldQmyQxYyMIllYiMhCSppoFppMk0JIKZGFQv4AZWGDhZKUlGYa2VloNmKKlaSxURTZ2Pj9m+d5z7m95z7vvffcO+80t/R+6uk95/l+zzn33Pe855zXrEOHhFnQIjWnmFVqVGEpdMncRPL4pUYNPIHWqlmGjdAfaC/0V2IJv6FpatYEn3GumjHY6IL/zJrkNeiumjWyHfqsZgxObLWaAVkTrxs+0zI189hjxZPot+J4XfC3+UBNZQXUC42Zm8QuaEcqw/Ha4p11QxehneJX5RB03pqb31HocjOcYsBKvPw+6KS5RG46LJ9IZTgYP6xmwCvosS9zVXy1EoNnwJ17BrTQXPuX5l7eMR/LovQ4TBxSM4DxbWp6nlrrQKx/FC/GG2hOUGcfI0F5PIiF6Ni5MLFomTG+XE2w2FzsiPj0TosX43hQnm6ujx5fDyevMK8o3mC9xd8G491qgmfW2rbLe1x2E+WUtfabB/PmqalcsXiHjG9V05yvbXmeqleVT1a+j1J5XyyeyPhBNc35PzO8b0E5YQm0L6grbHPDl9nudhDjEcYbWRaxZ2/ApHtqCm+hUTXBGUsPwhsR69ww+Lu6E8ToU/QV3pkZG7TmmX3dx3iN5DebxW6rMMm8nTNhv+V3dtNcjEdQF7TS13+ESeAs9Bw6IH7CO0tP7ruvP0oSMnhoxfEGayz/4ZWyeUXw4rFBzTbgM81UM4HBD9BV6L3E8uASvKVmRV6o0QabrXW1pOAkkytR9IwJaOfb3AKdU7MN+Lev8Jjiv41haLYGIjCfV7aJwM1lsrgPrVNzMpkPLVBzitmkRof/kX9PypGU436f6gAAAABJRU5ErkJggg==>
