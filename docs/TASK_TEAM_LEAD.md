# QA Team Lead Track - Task Description

**Position**: Team Lead - QA (Network Operating System)
**Time Estimate**: 3-4 hours
**Difficulty**: Leadership + Technical

## Overview

This assessment evaluates your ability to define QA strategy, lead technical direction, and demonstrate both hands-on skills and strategic thinking.

## Your Tasks

### Task 1: Test Structure Review (30 minutes)

Review the existing test structure in this repository:
- `tests/conftest.py` - Fixtures
- `tests/test_starter.py` - Test cases
- `mock_nos/` - System under test

Document your findings in `QA_REVIEW.md`:
- What's working well?
- What gaps do you see in test coverage?
- What would you prioritize fixing?

### Task 2: QA Strategy Document (60-90 minutes)

Create `QA_STRATEGY.md` (2-3 pages) covering:

#### 2.1 Test Coverage Strategy
- What types of testing are needed? (unit, integration, system, performance)
- How would you prioritize testing for different NOS components?
- What coverage metrics would you target?

#### 2.2 CI/CD Integration
- How should tests be integrated into the CI/CD pipeline?
- What should block a merge? What should be advisory?
- How to handle flaky tests?

#### 2.3 Test Environment Management
- How to manage test environments for a NOS?
- Virtual vs physical testing strategy
- Test data management

#### 2.4 Team Workflow
- Code review process for tests
- Test documentation standards
- Bug triage and prioritization

#### 2.5 Metrics and Reporting
- What QA metrics would you track?
- How to report quality to stakeholders?

### Task 3: Test Plan (45-60 minutes)

Create `TEST_PLAN_EVPN.md` - a test plan for a hypothetical "EVPN-VXLAN Feature Release":

**Feature Description**: The team is adding EVPN-VXLAN support for Layer 2 extension across the data center fabric.

Your test plan should include:
1. **Scope**: What will be tested?
2. **Test Approach**: How will it be tested?
3. **Test Cases**: At least 10 high-level test cases
4. **Environment Requirements**: What's needed?
5. **Risks and Mitigations**: What could go wrong?
6. **Success Criteria**: When is the feature "done"?

### Task 4: Technical Demonstration (30-45 minutes)

Implement **3 test cases** that demonstrate your recommended testing patterns:

1. A well-designed **fixture** showing best practices
2. A **parameterized test** with comprehensive coverage
3. An **integration test** showing component interaction

These should be exemplary code that you would use to mentor your team.

### Task 5: Bug Analysis (15-30 minutes)

Review the codebase and document at least 2 bugs in `BUGS_FOUND.md`.

For each bug, include:
- Technical description
- Business impact assessment
- Priority recommendation
- Suggested fix approach

## Deliverables

1. `QA_REVIEW.md` - Review of existing test structure
2. `QA_STRATEGY.md` - Comprehensive QA strategy document
3. `TEST_PLAN_EVPN.md` - Feature test plan
4. Implemented test cases demonstrating best practices
5. `BUGS_FOUND.md` - Bug analysis with business impact

## Evaluation Criteria

| Category | Weight | Description |
|----------|--------|-------------|
| **QA Strategy** | 30% | Completeness and practicality |
| **Technical Depth** | 20% | Demonstrated testing expertise |
| **Communication** | 20% | Clarity of written documents |
| **Process Knowledge** | 15% | CI/CD, workflows, metrics |
| **Leadership Indicators** | 15% | Mentorship approach, team focus |

## QA Strategy Template

```markdown
# QA Strategy - NOS Project

## Executive Summary
[Brief overview of QA approach]

## Test Types and Coverage

### Unit Testing
- Scope: ...
- Coverage Target: ...
- Responsibility: ...

### Integration Testing
- Scope: ...
- Coverage Target: ...
- Responsibility: ...

### System Testing
- Scope: ...
- Coverage Target: ...
- Responsibility: ...

## CI/CD Integration

### Pipeline Stages
1. ...
2. ...

### Quality Gates
- ...

## Test Environment Strategy
...

## Team Processes
...

## Metrics and Reporting
...

## Risks and Mitigations
...
```

## What We're Looking For

### Strategic Thinking
- Can you see the big picture?
- Do you balance quality with delivery?
- Are your recommendations practical?

### Technical Leadership
- Can you set technical direction?
- Do you demonstrate best practices?
- Can you mentor through code?

### Communication
- Is your writing clear and concise?
- Can you explain complex topics simply?
- Do you consider your audience?

### Process Orientation
- Do you understand modern QA practices?
- Can you integrate testing with CI/CD?
- Do you think about scalability?

Good luck!
