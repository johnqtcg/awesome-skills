# Defense-in-Depth Validation

## Table of Contents

1. [Overview](#overview)
2. [Why Multiple Layers](#why-multiple-layers)
3. [The Four Layers](#the-four-layers)
4. [Applying the Pattern](#applying-the-pattern)
5. [Example from Session](#example-from-session)
6. [Key Insight](#key-insight)

## Overview

When you fix a bug caused by invalid data, adding validation at one place feels sufficient. But that single check can be bypassed by different code paths, refactoring, or mocks.

**Core principle:** Validate at EVERY layer data passes through. Make the bug structurally impossible.

## Why Multiple Layers

Single validation: "We fixed the bug"
Multiple *preventive* layers: "We made the bug impossible"

Layers 1-3 are preventive — each rejects bad input/state before it can do damage, and together that's what "structurally impossible" refers to:
- Entry validation catches most bugs
- Business logic catches edge cases
- Environment guards prevent context-specific dangers

Layer 4 (debug logging) is different in kind: it's observability, not prevention. It doesn't stop anything from happening — it makes sure that if layers 1-3 ever have a gap, you can see what happened instead of debugging blind. Don't count it toward "impossible"; count it toward "fast to diagnose if it ever isn't."

## The Four Layers

### Layer 1: Entry Point Validation
**Purpose:** Reject obviously invalid input at API boundary

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === '') {
    throw new Error('workingDirectory cannot be empty');
  }
  if (!existsSync(workingDirectory)) {
    throw new Error(`workingDirectory does not exist: ${workingDirectory}`);
  }
  if (!statSync(workingDirectory).isDirectory()) {
    throw new Error(`workingDirectory is not a directory: ${workingDirectory}`);
  }
  // ... proceed
}
```

### Layer 2: Business Logic Validation
**Purpose:** Ensure data makes sense for this operation

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) {
    throw new Error('projectDir required for workspace initialization');
  }
  // ... proceed
}
```

### Layer 3: Environment Guards
**Purpose:** Prevent dangerous operations in specific contexts

```typescript
async function gitInit(directory: string) {
  // In tests, refuse git init outside temp directories
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    const tmpDir = normalize(resolve(tmpdir()));

    // Plain startsWith(tmpDir) is a prefix-match bug: "/tmp-evil" starts
    // with "/tmp" as a string even though it is not inside /tmp. Require
    // either an exact match or a match up to a real path separator.
    const isInsideTmpDir =
      normalized === tmpDir || normalized.startsWith(tmpDir + sep);
    if (!isInsideTmpDir) {
      throw new Error(
        `Refusing git init outside temp dir during tests: ${directory}`
      );
    }
  }
  // ... proceed
}
```

### Layer 4: Debug Instrumentation
**Purpose:** Capture context for forensics

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  logger.debug('About to git init', {
    directory,
    cwd: process.cwd(),
    stack,
  });
  // ... proceed
}
```

## Applying the Pattern

When you find a bug:

1. **Trace the data flow** - Where does bad value originate? Where used?
2. **Map all checkpoints** - List every point data passes through
3. **Add validation at each layer** - Entry, business, environment, debug
4. **Test each layer** - Try to bypass layer 1, verify layer 2 catches it

### Relationship to the Single-Fix Rule

`SKILL.md` Phase 4 requires ONE minimal fix per root cause, no bundled changes. This does not conflict with adding validation at every layer above — it's a scope clarification, not an exception:

- When the confirmed root cause is "this invalid data can enter through multiple layers," validating at every layer it actually passes through **is** the single fix for that single root cause. Four layers touched by one root cause is still one fix.
- What Phase 4 forbids is bundling in layers, checks, or hardening that the *evidence* didn't implicate — e.g., adding a validation layer to a fifth, unrelated code path "while you're in there," or hardening a component that the data-flow trace (step 1 above) never actually reached.
- Practical test: if you removed one of the layers you're about to add, would the confirmed root cause still be reachable through it? If yes, that layer is part of the fix. If the layer only guards against a *different*, unconfirmed concern, it's scope creep — split it into its own investigation.

## Example from Session

Bug: Empty `projectDir` caused `git init` in source code

**Data flow:**
1. Test setup → empty string
2. `Project.create(name, '')`
3. `WorkspaceManager.createWorkspace('')`
4. `git init` runs in `process.cwd()`

**Four layers added:**
- Layer 1: `Project.create()` validates not empty/exists/writable
- Layer 2: `WorkspaceManager` validates projectDir not empty
- Layer 3: `WorktreeManager` refuses git init outside tmpdir in tests
- Layer 4: Stack trace logging before git init

**Result:** All 1847 tests passed, bug impossible to reproduce

## Key Insight

All four layers earned their place, but not for the same reason. During testing, each of the three preventive layers caught bugs the others missed:
- Different code paths bypassed entry validation
- Mocks bypassed business logic checks
- Edge cases on different platforms needed environment guards

Debug logging (layer 4) caught none of these on its own — it doesn't reject anything — but it's what let the investigation confirm exactly which layer was missing before layers 1-3 existed, and it's what will make the *next* structural-misuse bug fast to diagnose instead of a fresh investigation from zero.

**Don't stop at one validation point.** Add preventive checks at every layer the data actually passes through, and keep the diagnostic layer so the next gap is fast to find.
