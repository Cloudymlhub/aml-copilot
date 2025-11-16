# 🎯 Agentic Compliance Architecture — From Assisted Review to Full Automation

---

### 🟦 **Phase 1 — Investigator Support Layer**

**Goal:** Empower L2 reviewers with explainable insights

**Main Components**

- 🧠 Model Explainability Service → pulls SHAP / feature importance
- 🧩 Typology Mapper → maps features to human red flags & typologies
- 💬 Guided Summary Generator → produces top-reasons and next steps

**Data Flow**

```mermaid
flowchart LR
    A[Model Outputs] --> B[Explainability Service]
    B --> C[Typology Mapper]
    C --> D[Guided Summary Generator]
    D --> E[Investigator Dashboard]
    style A fill:#DDEEFF,stroke:#3366CC
    style E fill:#E6FFEC,stroke:#22AA55

```

**Key Outcome:**

Investigators instantly see *why* an alert is risky, mapped to familiar AML typologies.

---

### 🟩 **Phase 2 — Agentic System (Assisted Investigation)**

**Goal:** Enable natural-language interaction and automated data retrieval

**Specialized Agents**

- 🧭 **Coordinator Agent** — orchestrates the workflow
- 🤖 **Intent Mapping Agent** — understands queries and maps to features (API or column names)
- 📦 **Retrieval Agent** — executes fast data lookups via tool registry
- 🧩 **Procedural Guidance Agent** — provides contextual next-step advice

**Agentic Flow**

```mermaid
flowchart TD
    U[Investigator UI] --> C[Coordinator Agent]
    C --> I[Intent Mapping Agent]
    I -->|Returns structured intent| C
    C --> R[Retrieval Agent]
    C --> G[Procedural Guidance Agent]
    R -->|Data| C
    G -->|Next-step advice| U
    C -->|Aggregated response| U
    style U fill:#E6FFEC,stroke:#22AA55
    style C fill:#FFF3CC,stroke:#D1A200
    style I fill:#E3F2FD,stroke:#1976D2
    style R fill:#F3E5F5,stroke:#8E24AA
    style G fill:#E8F5E9,stroke:#43A047

```

**UX Example:**

> Investigator: “Show me all transactions for this customer in the last 7 days.”
> 
> 
> Agentic system → maps query → retrieves data → suggests related checks.
> 

---

### 🟨 **Phase 3 — Progressive Automation**

**Goal:** Evolve from assisted review to autonomous decision execution

**Stages**

1. **Augmented Review:** Agent explains model output; investigator confirms actions.
2. **Partial Automation:** Agent prepares SAR drafts and supporting evidence.
3. **Full Automation with Oversight:** Agent executes low-risk workflows; humans validate edge cases.

**Evolution Diagram**

```mermaid
flowchart LR
    A[Human-Driven Review] --> B[Augmented Review]
    B --> C[Co-Pilot Automation]
    C --> D[Autonomous Agent + Oversight]
    style A fill:#FFE6E6,stroke:#CC0000
    style B fill:#FFF3CC,stroke:#D1A200
    style C fill:#E6FFEC,stroke:#22AA55
    style D fill:#CCE5FF,stroke:#0077CC

```

---

### ⚙️ **Integration & Infrastructure Layer**

```mermaid
flowchart TB
    FS[Feature Store / Data Lake] --> API[API Gateway & Retrieval Tools]
    API --> LLM[Agentic Services (Coordinator + Specialized Agents)]
    LLM --> AUDIT[Secure Audit Trail & Logging]
    AUDIT --> FEEDBACK[Human Feedback Loop]
    style FS fill:#E3F2FD,stroke:#1976D2
    style API fill:#FFF3CC,stroke:#D1A200
    style LLM fill:#F3E5F5,stroke:#8E24AA
    style AUDIT fill:#E8F5E9,stroke:#43A047
    style FEEDBACK fill:#E6FFEC,stroke:#22AA55

```

---

### 🌍 **End-to-End System Overview**

```mermaid
flowchart LR
    subgraph ML[Model Layer]
        M1[Risk Scoring Model] --> M2[Explainability Engine]
        M2 --> M3[Typology Mapper]
    end

    subgraph Support[Phase 1: Investigator Support Layer]
        M3 --> S1[Guided Summary Generator]
        S1 --> S2[Investigator Dashboard]
    end

    subgraph Agentic[Phase 2: Agentic System]
        S2 --> A1[Coordinator Agent]
        A1 --> A2[Intent Mapping Agent]
        A1 --> A3[Retrieval Agent]
        A1 --> A4[Procedural Guidance Agent]
        A3 --> A5[Data Services / Feature Store]
    end

    subgraph Auto[Phase 3: Progressive Automation]
        A4 --> AUTO1[Automated Decision Layer]
        AUTO1 --> AUTO2[Oversight & Audit Engine]
        AUTO2 --> FEED[Human Feedback Loop]
    end

    FEED --> ML
    A5 -.->|Read-only| DB[(AML Data Lake)]

    style ML fill:#E3F2FD,stroke:#1976D2
    style Support fill:#E8F5E9,stroke:#43A047
    style Agentic fill:#FFF3CC,stroke:#D1A200
    style Auto fill:#F3E5F5,stroke:#8E24AA
    style DB fill:#F1F8E9,stroke:#388E3C

```

---

### 📊 **Key Benefits**

| Dimension | Before | After |
| --- | --- | --- |
| Explainability | Static PDFs & scores | Interactive reasoning & typology mapping |
| Investigator Speed | Manual queries | Instant retrieval via agent chat |
| Consistency | Reviewer-dependent | Policy-driven guidance |
| Scalability | Limited human bandwidth | Semi-/Fully automated agent loop |

---

### 🚀 **Implementation Roadmap**

1. Define red-flag → typology mapping dictionary
2. Deploy Explainability API for existing models
3. Build Intent Mapping Agent (RAG + feature catalog)
4. Implement Retrieval Agent with limited tool set
5. Add Procedural Guidance Agent + UI integration
6. Collect investigator feedback → fine-tune prompts
7. Phase-in progressive automation & governance