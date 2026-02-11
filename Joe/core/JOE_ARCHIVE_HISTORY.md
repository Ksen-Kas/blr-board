# JOE_ARCHIVE_HISTORY

This file documents the evolution of the Joe agent and its predecessors.  
It does not participate in runtime behavior and must not be loaded into operational agent-context.

## 1. Evolution Overview

- Joe (Джо) is a career engine and analytical core that grew out of the CV-LAB agent built for Andrey Kasyanov.
- CV-LAB initially handled CV and cover letters (CV, cover letters, HR-SCAN).
- Later, its logic was embedded into a broader Job Engine where Joe became the center of gravity:
  - collecting facts and experience,
  - building the profile,
  - evaluating vacancies,
  - forming decisions such as “apply”, “apply with preparation”, or “can skip”.
- Joe operates as a specialized computation layer with strict rules, a validation layer, and clear separation of roles with other agents (Core, SFA, Artyom, Ward, and others).

In the Cursor runtime implementation, only the application execution layer (JOE_APPLY) is active; higher-level career and decision functions are archived.

## 2. CV-LAB (Early Stage)

### 2.1 Purpose and Modes

- CV-LAB was a multi-mode agent for CV and cover letters:
  - ONE-SHOT MENTOR → ATS_OPERATOR → HR-SCAN (`CV-LAB v1.0 · System Core`).
- It operated on:
  - a fixed canonical CV for Andrey,
  - a corpus of Daria’s methodology,
  - notes and examples of letters and HR-SCAN outputs.
- CV-LAB did not invent facts and worked only with existing data.

The methodology of Daria was provided in a concentrated form, split into:

- an operational core for direct use,
- an extended archive for deeper agent learning.

### 2.2 Workflow (High-Level)

- Initialization:
  - create a new agent,
  - insert the `CV-LAB v1.0 · System Core` block,
  - name it `CV-LAB`,
  - trigger initialization (`INIT CV-LAB` or equivalent).
- ONE-SHOT MENTOR:
  - read the project folder (canonical CV, Daria’s methodology, notes, old letters, HR-SCAN samples),
  - output a short summary of what was learned,
  - on command “build the Playbook”, produce `CV-LAB PLAYBOOK v1.0`:
    - canonical CV structure,
    - explicit immutable sections (name, title, experience structure, etc.),
    - rules for summary, skills, letters, and HR-SCAN.
- ATS_OPERATOR and HR-SCAN:
  - standard flow: Summary → Skills → Cover Letter → HR-SCAN,
  - Experience is not modified,
  - CV-LAB lives as a separate pipeline that does not rewrite CLS_Andrey.

In the current runtime, this logic is preserved as background constraints (no-invention, immutable experience, method-driven letters) but is not used as a separate agent.

## 3. Ward → CV-LAB → Joe

### 3.1 Ward as Preprocessor

- `Ward·CV_Preprocessor` accepted unstructured materials:
  - conversations,
  - drafts,
  - fragments of vacancies,
  - observations.
- Ward:
  - structured these inputs,
  - extracted useful facts (achievements, facts, scales, metrics, areas of expertise, signals for recruiters),
  - removed noise (lyrical content, repetition, stylistic noise, unrelated details),
  - produced:
    - a concise summary of useful elements,
    - categories such as Skills, Achievements, Fit, Red flags,
    - tags for CV-LAB (“safe to use”),
    - questions for clarification.

Ward did not interfere with the style of CV-LAB or Joe; it only prepared raw material.

### 3.2 Use in Current Implementation

In the Cursor runtime, Ward is not implemented as a separate agent.  
The preprocessing logic is reflected in:

- strict constraints on facts and style,
- separation between raw notes and final deliverables.

## 4. Joe inside Job Engine (Career Engine)

### 4.1 Architecture

Within the original Job Engine, Joe included:

- `JO_Core v1.1`:
  - central logic for vacancies,
  - worked with:
    - canonical CV,
    - statistics of applications,
    - vacancy and status tables,
    - comments on vacancies.
- `Profile Scanner v1`:
  - inspected LinkedIn profiles,
  - produced:
    - lists of strong areas,
    - weak points of the profile,
    - soft recommendations,
  - did not modify profiles directly; all changes went through validation.
- `Decision Layer v1`:
  - produced decisions:
    - “apply”,
    - “apply with preparation” (referral, extra edits, clarifications),
    - “can skip” (visa, profile mismatch, intermediary risks, etc.).
- `Validation Layer`:
  - required layer for any changes in systemic data.

### 4.2 Vacancy Workflow (Original)

High-level sequence:

1. The user provided Joe with:
   - a new vacancy, or
   - a request to review current applications (e.g., “show where statuses are pending”).
2. Joe:
   - collected all data (CV, letters, statistics, comments),
   - produced a primary assessment (match, risks, potential),
   - returned a decision in the three-option format with explanations.
3. For changes in profile, positioning, or metrics:
   - Joe invoked Profile Scanner,
   - asked for confirmation via a Validation request,
   - applied changes only after explicit confirmation.

In the Cursor runtime, high-level decision-making (“apply / skip”) is not active.  
Only the underlying execution logic (CV, letters, forms, messages) is implemented as JOE_APPLY.

## 5. Joe Script and Interview Pipeline

### 5.1 Joe Script Context

- Joe Script was used as part of interview preparation:
  - modules: recruiter questions, consultant mindset, company context, Joe Script, ACP or STAR examples, constraints and red flags, logistics.
- Per vacancy:
  - connect relevant modules (e.g., company-specific Joe Script version),
  - coordinate execution with a separate Interview Operator:
    - strategy and hypotheses from the producer and Joe,
    - execution and rehearsal by the Interview Operator.

### 5.2 Status in Current Implementation

- Interview preparation and Joe Script are not part of the runtime core in Cursor.
- They remain documented here as historical context for how Joe integrated into a broader career system.

## 6. Versioned JOE_APPLY Instructions

### 6.1 v1.4 — Early Instructions

- Defined JOE_APPLY as an application execution algorithm.
- Introduced:
  - basic role,
  - primary outputs,
  - out-of-scope list,
  - initial canon and data authority rules,
  - initial NO-INVENTION, CV architecture constraints, and CANON CHECK.

Superseded by v1.5 and v1.6 where conflicts occur.

### 6.2 v1.5 — GPT Instructions

- Refined instructions for GPT-based hosting:
  - system-level notes about pasting into GPTs,
  - more detailed delivery formats for letters and CV_TAILOR,
  - verbose DRIFT CONTROL,
  - explicit base CV routing and header linkage.

Host-specific language and configuration details are archive-only; current runtime spec for Cursor removes these host-specific parts while preserving the logic.

### 6.3 v1.6 — Final Instructions

- Marked as “FINAL INSTRUCTIONS”.
- Introduced and finalized:
  - stricter link handling,
  - refined vacancy detection,
  - letter opening rule patch (reasoning linkage for reservoir / subsurface roles),
  - refined letter structure and signature rules,
  - clarified DONE CRITERIA.

The current runtime specification for Cursor aligns with v1.6.  
Where v1.4 or v1.5 conflict with v1.6, v1.6 takes precedence.

## 7. Andrey-Specific Context (Archived)

- Original deployment targeted Andrey Kasyanov (Principal Reservoir Engineer).
- README and knowledge files in the repository include Andrey-specific information.

For a generic agent implementation:

- all references to Andrey are considered non-runtime,
- the agent is now client-agnostic and uses:
  - `CLIENT` as a parameter,
  - client-specific canonical data per session.

## 8. Deprecated Forms

The following are deprecated and must not be used as runtime instructions:

- any CLS_* or CV-LAB system prompts that position them as separate agents,
- early JOE_APPLY snippets that:
  - assume a single fixed client,
  - rely on GPT-specific UI or configuration mechanisms,
  - contain conversational or emotional guidance.

These artifacts remain in the archive for documentation and audit but are excluded from the runtime contract for the Cursor agent.

