## ADDED Requirements

### Requirement: README operating guidance matches tracked evidence
The project README SHALL state prerequisites and command context consistently with the current tracked implementation, without claiming unavailable artifacts or runtime verification.

#### Scenario: A reader follows the corrected guidance
- **WHEN** a reader uses the affected README section
- **THEN** its documented behavior and prerequisites match the tracked evidence
- **AND** existing safety, authorization, attribution, and acceptance boundaries remain intact

#### Scenario: The change is reviewed
- **WHEN** the documentation correction is validated
- **THEN** validation is scoped to documentation and any unrun runtime or unavailable tool checks are disclosed
