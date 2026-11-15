# Between — UI polish backlog

Future interface and accessibility opportunities after the submitted release. This list does not claim a completed accessibility audit or authorize new work. Ask Pip and next-step presentation already exist; the items below concern further refinement.

Keep the existing warm, cozy, playful identity and Pip's original artwork. Undertake further runtime changes only when a new task authorizes them.

- Pip expressions and gentle animations, with reduced-motion support.
- Mobile layout, tap targets, readable questions, and clear next-step presentation.
- Loading and empty states that help the student start without guilt.
- Clear distinctions between syncing, offline access, authentication failure, and rendering errors.
- Refine the existing Ask Pip input and speech bubble while keeping the focus on actionable work.
- Accessible labels, keyboard focus, status announcements, contrast, and error recovery.
- Estimate editing and understandable logged/remaining time.
- Regression checks for JavaScript/HTML references, including question elements.
- Verify service-worker registration and behavior before promising offline use; preserve authentication/cache exclusions.

## Decisions reserved for the owner

Do not change minimum session length, planning hours, or whether recurring study blocks are fixed commitments or fillable time without an explicit choice. Preserve the default of sending calendar times, not private busy-event titles, to Gemini.
