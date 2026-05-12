# SmartDQC — Smart Data Quality Check & Cleaning Tool
### Project Brief Summary

---

## 1. Overview

**Platform Name:** SmartDQC — Smart Data Quality Check & Cleaning Tool
**Client:** KKM (Kementerian Kesihatan Malaysia)
**Deployment:** Local, accessible via IP address on client's laptop
**Hardware Requirement:** RTX 5060, 8GB VRAM

---

## 2. Data Sources

The platform will ingest and process data from the following sources:

1. myVASS
2. CCMS
3. KPM
4. NCDC
5. NHMS
6. JKN
7. Parliament
8. DDSM
9. Admin Data (1)
10. Admin Data (2)

---

## 3. Platform Modules

The platform is split into two main portions — **Data** and **AI**.

---

### 3.1 Data Portion

#### Upload Dataset
Users can upload datasets into the platform for processing.

#### Data Mapping
Covers column identification, row level calculations, and EDA (Null values, Outliers). Includes a **Schema Mapping** layer where on upload, the schema is passed through the AI to check against supported source schemas. If the schema is recognised, it maps accordingly. If not, a fallback mechanism triggers and the AI creates a new compatible schema dynamically.

#### Data Quality Check
A single unified quality check that runs against two rule sets:
- **Predefined Business Rules** — rules specified and provided by the client
- **Data Quality Rules** — rules designed by the development team

> For the full list of specific features and rules, refer to: **SmartDQC_BP_KKM_Proposed_Features.docx**

#### Data Cleaning
Covers imputation, removals and additions, calculations and computations, and row level editing.

> For the full list of specific features, refer to: **SmartDQC_BP_KKM_Proposed_Features.docx**

---

### 3.2 AI Portion

#### Explainability
Makes AI decisions transparent and understandable to users. Uses a Small Language Model (SLM) under 4 billion parameters, running fully local within VRAM constraints.

#### Smart Analysis
Row-level AI analysis. Applies the **5W1H framework** (Who, What, When, Where, Why, How) to surface insights per record and across the dataset.

#### Predictive Analytics
Covers trends, mappings, and alerts with configurable thresholds.

> For the full list of specific AI features, refer to: **SmartDQC_BP_KKM_Proposed_Features.docx**

> **Note:** The briefing indicated a total of 18 features. The referenced document contains 16. The 2 remaining features are to be confirmed.

---

## 4. Interface

The interface is to be designed with the end user in mind — KKM staff ranging from non-technical to semi-technical. The design direction is:

- **Colour Scheme:** KKM branding
- **Feel:** Clean, simple, and aesthetically pleasing
- **Modes:** Light and Dark mode

Known interface capabilities to be included:

- **History** — session and analysis history
- **Chatbot** — conversational interface powered by the implemented AI models, supporting Bahasa Malaysia and English

> Full interface design is to be planned and wireframed separately.

---

## 5. Deployment & Maintenance

The platform is to be packaged in **Docker** — the full platform (frontend, backend, AI models, database) containerised into an image. The client pulls the image and deploys locally without ever being exposed to the source code.

Remote maintenance and updates are to be handled by pushing new versioned image tags, which the client re-pulls and redeploys. A remote access mechanism should be incorporated for the development team to perform maintenance without requiring physical access to the client's machine.

---

## 6. Open Items

| # | Item |
|---|------|
| 1 | Confirm final feature count — 16 in document, 18 stated in briefing |
| 2 | Client to provide full predefined business rules |
| 3 | SLM model selection to be finalised |
| 4 | Interface wireframes and KKM design assets to be sourced |
| 5 | Confirm schema structure for the 2 Admin Data sources |

---

*Summary based on verbal briefing only. For full feature details, refer to: **SmartDQC_BP_KKM_Proposed_Features.docx***
