# Scoring Module Config

## Fit Levels
- Strong: High match, no blockers
- Stretch: Possible but has gaps
- Mismatch: Different role type / domain

## Flags
- visa_required (STOP): USA + work visa explicitly required
- citizenship (STOP): EU/other citizenship required
- exp_gap (WARNING): Part of required experience missing — show %
- junior_role (WARNING): Looking for ≤5 years experience
- strong_mismatch (REVIEW): Wrong role type entirely

## Not a flag
- Location / relocation — does not block or warn
