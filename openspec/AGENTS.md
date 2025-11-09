# OpenSpec Instructions

Instructions for AI coding assistants using OpenSpec for spec-driven development in the NDAS project.

## TL;DR Quick Checklist

- Search existing work: `openspec list --specs`, `openspec list`
- Decide scope: new capability vs modify existing capability
- Pick unique `change-id`: kebab-case, verb-led (`add-`, `update-`, `remove-`, `refactor-`)
- Scaffold: `proposal.md`, `tasks.md`, `design.md` (if needed), delta specs per affected capability
- Write deltas: use `## ADDED|MODIFIED|REMOVED|RENAMED Requirements` with at least one `#### Scenario:` per requirement
- Validate: `openspec validate [change-id] --strict` and fix issues
- Request approval: Do not start implementation until proposal is approved

## Three-Stage Workflow

### Stage 1: Creating Changes
Create proposal when you need to:
- Add features or functionality
- Make breaking changes (database schema, API)
- Change architecture or patterns
- Update security patterns
- Modify medical data validation logic

Triggers (examples):
- "Help me create a change proposal"
- "Help me plan a change"
- "I want to create a spec"

Skip proposal for:
- Bug fixes restoring intended behavior
- Typos, formatting, comments
- Dependency updates (non-breaking)
- Configuration changes
- Tests for existing behavior

**Workflow**
1. Review `openspec/project.md`, `openspec list`, and `openspec list --specs` for context
2. Choose unique verb-led `change-id` and scaffold files under `openspec/changes/<id>/`
3. Draft spec deltas using `## ADDED|MODIFIED|REMOVED Requirements` with `#### Scenario:` per requirement
4. Run `openspec validate <id> --strict` before sharing

### Stage 2: Implementing Changes
Track these steps as TODOs and complete them one by one:
1. **Read proposal.md** - Understand what's being built
2. **Read design.md** (if exists) - Review technical decisions
3. **Read tasks.md** - Get implementation checklist
4. **Implement tasks sequentially** - Complete in order
5. **Confirm completion** - Ensure every item in `tasks.md` is finished
6. **Update checklist** - Set every task to `- [x]` after completion
7. **Approval gate** - Do not start implementation until proposal is approved

### Stage 3: Archiving Changes
After deployment:
- Move `changes/[name]/` → `changes/archive/YYYY-MM-DD-[name]/`
- Update `specs/` if capabilities changed
- Use `openspec archive <change-id> --yes` (always pass change ID explicitly)
- Run `openspec validate --strict` to confirm archived change passes checks

## Before Any Task

**Context Checklist:**
- [ ] Read relevant specs in `specs/[capability]/spec.md`
- [ ] Check pending changes in `changes/` for conflicts
- [ ] Read `openspec/project.md` for NDAS conventions
- [ ] Run `openspec list` to see active changes
- [ ] Run `openspec list --specs` to see existing capabilities

**NDAS-Specific Considerations:**
- Check if change affects medical data models (Patient, Assessment types)
- Verify compliance with security middleware stack
- Consider impact on AdminLTE UI patterns
- Review file upload validation requirements
- Ensure user tracking middleware compatibility

**Before Creating Specs:**
- Always check if capability already exists
- Prefer modifying existing specs over creating duplicates
- Use `openspec show [spec]` to review current state
- If request is ambiguous, ask clarifying questions before scaffolding

## Quick Start

### CLI Commands

```bash
# Essential commands
openspec list                  # List active changes
openspec list --specs          # List specifications
openspec show [item]           # Display change or spec
openspec validate [item]       # Validate changes or specs
openspec archive <change-id> [--yes|-y]   # Archive after deployment

# Project management
openspec init [path]           # Initialize OpenSpec
openspec update [path]         # Update instruction files

# Interactive mode
openspec show                  # Prompts for selection
openspec validate              # Bulk validation mode

# Debugging
openspec show [change] --json --deltas-only
openspec validate [change] --strict
```

### Command Flags

- `--json` - Machine-readable output
- `--type change|spec` - Disambiguate items
- `--strict` - Comprehensive validation
- `--no-interactive` - Disable prompts
- `--skip-specs` - Archive without spec updates
- `--yes`/`-y` - Skip confirmation prompts

## Directory Structure

```
openspec/
├── project.md              # NDAS conventions and context
├── specs/                  # Current truth - what IS built
│   └── [capability]/       # Single focused capability
│       ├── spec.md         # Requirements and scenarios
│       └── design.md       # Technical patterns
├── changes/                # Proposals - what SHOULD change
│   ├── [change-name]/
│   │   ├── proposal.md     # Why, what, impact
│   │   ├── tasks.md        # Implementation checklist
│   │   ├── design.md       # Technical decisions (optional)
│   │   └── specs/          # Delta changes
│   │       └── [capability]/
│   │           └── spec.md # ADDED/MODIFIED/REMOVED
│   └── archive/            # Completed changes
```

## Creating Change Proposals

### Decision Tree

```
New request?
├─ Bug fix restoring spec behavior? → Fix directly
├─ Typo/format/comment? → Fix directly
├─ New feature/capability? → Create proposal
├─ Breaking change (schema, API)? → Create proposal
├─ Architecture change? → Create proposal
└─ Unclear? → Create proposal (safer)
```

### Proposal Structure

1. **Create directory:** `changes/[change-id]/` (kebab-case, verb-led, unique)

2. **Write proposal.md:**
```markdown
# Change: [Brief description]

## Why
[1-2 sentences on problem/opportunity]

## What Changes
- [Bullet list of changes]
- [Mark breaking changes with **BREAKING**]

## Impact
- Affected specs: [list capabilities]
- Affected code: [key files/systems]
- Database migrations: [Yes/No]
- UI changes: [Yes/No]
```

3. **Create spec deltas:** `specs/[capability]/spec.md`
```markdown
## ADDED Requirements
### Requirement: New Feature
The system SHALL provide...

#### Scenario: Success case
- **WHEN** user performs action
- **THEN** expected result

## MODIFIED Requirements
### Requirement: Existing Feature
[Complete modified requirement with all scenarios]

## REMOVED Requirements
### Requirement: Old Feature
**Reason**: [Why removing]
**Migration**: [How to handle]
```

4. **Create tasks.md:**
```markdown
## 1. Database Changes
- [ ] 1.1 Create/modify models
- [ ] 1.2 Create migrations
- [ ] 1.3 Update validators/choices

## 2. Backend Implementation
- [ ] 2.1 Update views
- [ ] 2.2 Update forms
- [ ] 2.3 Add business logic

## 3. Frontend Implementation
- [ ] 3.1 Create/update templates
- [ ] 3.2 Update JavaScript
- [ ] 3.3 Update CSS (if needed)

## 4. Testing & Validation
- [ ] 4.1 Write unit tests
- [ ] 4.2 Test UI responsiveness
- [ ] 4.3 Verify security headers
```

5. **Create design.md when needed:**
Create `design.md` if any of the following apply:
- Database schema changes affecting multiple models
- New architectural patterns
- Security or performance complexity
- Medical data validation changes
- Breaking changes requiring migration

Minimal `design.md` skeleton:
```markdown
## Context
[Background, medical/technical constraints]

## Goals / Non-Goals
- Goals: [...]
- Non-Goals: [...]

## Decisions
- Decision: [What and why]
- Alternatives considered: [Options + rationale]

## Database Impact
[Schema changes, migrations, data integrity]

## Security Considerations
[HIPAA compliance, user tracking, access control]

## UI/UX Impact
[AdminLTE patterns, responsive design, accessibility]

## Migration Plan
[Steps, rollback strategy, data migration]

## Open Questions
- [...]
```

## NDAS-Specific Patterns

### Model Changes
When proposing model changes, always consider:
```markdown
## Database Impact
- Inherits from TimeStampedModel, UserTrackingMixin: Yes/No
- New choices in ndas/custom_codes/choice.py: [list]
- New validators in ndas/custom_codes/validators.py: [list]
- Searchable fields with db_index: [list]
- Medical data with help_text: [list]
- Migration strategy: [automatic/manual/data migration]
```

### UI Changes
When proposing UI changes:
```markdown
## UI/UX Impact
- AdminLTE components used: [info-box/card/table]
- Bootstrap 4.6 compatibility: Verified
- Template extends: src/base.html or src/basic_plane.html
- CSRF token included: Yes
- Responsive design: Desktop/Tablet/Mobile tested
- JavaScript libraries: [Select2/HTMX/Video.js/etc]
```

### Security Changes
When proposing security changes:
```markdown
## Security Considerations
- Middleware stack impact: [position/order]
- User tracking compatibility: Verified
- CSRF protection: Maintained
- File upload validation: [new validators]
- Session security: [timeout/cookies]
- Medical data privacy: HIPAA considerations
```

## Spec File Format

### Critical: Scenario Formatting

**CORRECT** (use #### headers):
```markdown
#### Scenario: User login success
- **WHEN** valid credentials provided
- **THEN** return JWT token
```

**WRONG**:
```markdown
- **Scenario: User login**  ❌
**Scenario**: User login     ❌
### Scenario: User login      ❌
```

Every requirement MUST have at least one scenario.

### Requirement Wording
- Use SHALL/MUST for normative requirements
- Include medical context when applicable
- Reference validators and choices by name

### Delta Operations

- `## ADDED Requirements` - New capabilities
- `## MODIFIED Requirements` - Changed behavior (include full requirement)
- `## REMOVED Requirements` - Deprecated features
- `## RENAMED Requirements` - Name changes

When using MODIFIED:
1. Locate existing requirement in `openspec/specs/<capability>/spec.md`
2. Copy entire requirement block (header + scenarios)
3. Paste under `## MODIFIED Requirements` and edit
4. Ensure header text matches exactly (whitespace-insensitive)
5. Keep at least one `#### Scenario:`

## Troubleshooting

### Common Errors

**"Change must have at least one delta"**
- Check `changes/[name]/specs/` exists with .md files
- Verify files have operation prefixes (## ADDED Requirements)

**"Requirement must have at least one scenario"**
- Check scenarios use `#### Scenario:` format (4 hashtags)
- Don't use bullet points or bold for scenario headers

**Silent scenario parsing failures**
- Exact format required: `#### Scenario: Name`
- Debug with: `openspec show [change] --json --deltas-only`

### Validation Tips

```bash
# Always use strict mode
openspec validate [change] --strict

# Debug delta parsing
openspec show [change] --json | jq '.deltas'

# Check specific requirement
openspec show [spec] --json -r 1
```

## Best Practices

### NDAS Code Quality
- Follow Django 4.2 LTS best practices
- Use centralized validators and choices
- Maintain AdminLTE UI consistency
- Include comprehensive help_text for medical fields
- Test on mobile devices (tablets in medical settings)

### Simplicity First
- Default to <100 lines of new code
- Single-file implementations until proven insufficient
- Follow existing NDAS patterns (see project.md)
- Use established form/view/template patterns

### Clear References
- Use `file.py:42` format for code locations
- Reference specs as `specs/auth/spec.md`
- Link related changes and PRs
- Include database model names

### Capability Naming
- Use verb-noun: `patient-management`, `video-assessment`
- Single purpose per capability
- 10-minute understandability rule
- Split if description needs "AND"

### Change ID Naming
- Use kebab-case: `add-two-factor-auth`
- Verb-led prefixes: `add-`, `update-`, `remove-`, `refactor-`
- Ensure uniqueness; append `-2`, `-3` if needed

## Error Recovery

### Change Conflicts
1. Run `openspec list` to see active changes
2. Check for overlapping specs
3. Coordinate with change owners
4. Consider combining proposals

### Validation Failures
1. Run with `--strict` flag
2. Check JSON output for details
3. Verify spec file format
4. Ensure scenarios properly formatted

### Missing Context
1. Read project.md first
2. Check related specs
3. Review recent archives
4. Ask for clarification

## Quick Reference

### Stage Indicators
- `changes/` - Proposed, not yet built
- `specs/` - Built and deployed
- `archive/` - Completed changes

### File Purposes
- `proposal.md` - Why and what
- `tasks.md` - Implementation steps
- `design.md` - Technical decisions
- `spec.md` - Requirements and behavior

### CLI Essentials
```bash
openspec list              # What's in progress?
openspec show [item]       # View details
openspec validate --strict # Is it correct?
openspec archive <change-id> --yes  # Mark complete
```

### NDAS Quick Reference
- Model base classes: `TimeStampedModel, UserTrackingMixin`
- Choices location: `ndas/custom_codes/choice.py`
- Validators location: `ndas/custom_codes/validators.py`
- Template base: `src/base.html` (authenticated) or `src/basic_plane.html` (public)
- CSS framework: AdminLTE 3.2 + Bootstrap 4.6 (DO NOT CHANGE)
- Test command: `python manage.py test`
- Migration command: `python manage.py makemigrations && python manage.py migrate`

Remember: Specs are truth. Changes are proposals. Keep them in sync with NDAS conventions.
