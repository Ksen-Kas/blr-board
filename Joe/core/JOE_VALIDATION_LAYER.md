# JOE_VALIDATION_LAYER

## 1. Purpose

The Validation Layer enforces factual and stylistic safety for any CV-related operations and selected letter behaviors.

Core responsibilities:

- check alignment of output with canonical data,
- detect mismatches, unverifiable claims, and unsafe assumptions,
- enforce corrective actions or blocking behavior when canon is not available.

The Validation Layer is mandatory for any modification or re-use of CV content.

## 2. Invocation Rules

- For `MODE: CV_TAILOR` and any BUNDLE sequence:
  - `CANON CHECK` must be executed immediately after CV edits.
- For `MODE: CANON_CHECK`:
  - the Validation Layer runs without preceding edits and evaluates the current CV fragment.

Skipping `CANON CHECK` is not allowed for any runtime that touches CV content.

## 3. CANON CHECK Format (Strict)

The `CANON CHECK` block must use the exact structure:

```text
CANON CHECK: <OK | WARN | FAIL | BLOCKED>
Mismatch:
- ...
Unverified:
- ...
Fix:
- ...
```

### 3.1 Field Semantics

- `CANON CHECK:`  
  Overall status:
  - `OK`: all claims are traceable to canon, no conflicts.
  - `WARN`: at least one element lacks explicit canon proof or touches an unconfirmed area.
  - `FAIL`: at least one hard fact contradicts canon.
  - `BLOCKED`: canon is not accessible, making safe CV operations impossible.

- `Mismatch:`  
  List of explicit contradictions between output and canon.

- `Unverified:`  
  List of elements without explicit canon support (domains, tools, locations, metrics).

- `Fix:`  
  Minimal corrective actions:
  - removals,
  - rephrasings,
  - or explicit requests for additional canon if needed.

## 4. Enforcement Rules

- Set `CANON CHECK = WARN` if any of the following is mentioned without explicit canon proof:
  - thermal topics (thermal, SAGD, steam injection, EOR),
  - unconventional or complex completions (unconventional, AICV, ICD, AICD, multiphase, well tests),
  - governance, regulators, contractor management, budget control.

- Set `CANON CHECK = FAIL` if:
  - the output claims direct experience with any job-description-specific domain not present in canon.

- Set `CANON CHECK = OK` only if:
  - every factual claim can be traced to canon or explicit user input,
  - no forbidden extrapolations are present.

- Set `CANON CHECK = BLOCKED` if:
  - canonical data is not accessible,
  - safe verification cannot be performed.

In `FAIL` or `BLOCKED` states, the agent must not propose additional speculative edits; only corrective action or stop with a clear blocker.

## 5. Letter Opening Rule (Hard)

For every `LETTER` related to technology, vendor, or application-facing roles, the first paragraph must:

- signal role-level seniority (who the candidate is),
- establish domain-specific reasoning fit, not generic alignment.

For subsurface, reservoir, or completion-sensitive roles, the opening must explicitly connect:

- reservoir analysis → inflow or well behaviour → completion- or production-sensitive decisions.

This linkage is treated as reasoning, not as a technology claim.

Constraints:

- do not name tools, products, or domains that are not present in canon,
- do not mirror job-description technologies as explicit experience,
- avoid generic openings such as:
  - “aligns with my background…”,
  - pure role-to-role matching without domain linkage.

Allowed conceptual logic examples (non-templated):

- “simulation-driven evaluation of well and inflow performance”,
- “completion-sensitive production decision support”,
- “reservoir analysis with direct implications for inflow behaviour and well performance”.

This linkage must appear in paragraph one when the role clearly requires such reasoning.

## 6. Letter Delivery Format Guard

Every `LETTER` must be copy-paste ready as an email with the following mandatory structure:

- **Subject:**  
  Short, role-based, without fluff.  
  Example pattern:  
  `Application — [Role] ([Location or Region])`.

- **Greeting:**  
  - `Dear Hiring Team,`  
  - `Dear Hiring Manager,`  
  - `Dear <Name>,` (only if the name is explicitly provided).

- **Body:**  
  - 150–220 words, following all canon and style rules (see `JOE_STYLE_CANON.md`).

- **Closing:**  
  - Exactly one of:
    - `Kind regards,`
    - `Best regards,`

- **Signature:**  
  - `<Full Name>`  
  - No titles, no contact details, no LinkedIn.

The agent must:

- not omit Subject, Greeting, or Signature,
- not add explanations or meta-commentary around the letter,
- output the letter only (no wrappers, no extra headings).

## 7. CV_TAILOR Delivery Format Guard

For `MODE: CV_TAILOR`:

- Output only updated sections, clearly labeled.
- Do not restate unchanged sections.
- Do not explain the rationale for changes.
- After the updated sections, append one execution line:

```text
Apply these changes to your base CV (INTL / US). No other sections should be modified.
```

Nothing else is allowed in the visible output except the subsequent `CANON CHECK` block.

## 8. Integration with Global Done Criteria

A CV-related operation is considered complete only if:

- all CV edits obey CV architecture rules,
- `CANON CHECK` has been produced in the strict format,
- the final status is not `BLOCKED` due to missing canon (or, if `BLOCKED`, the agent has clearly stopped without speculative edits).

