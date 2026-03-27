# Design Rationale Overview

This section explains each skill's design process in detail, tying the discussion back to the concrete skill content so readers can see the design logic, why the skill is structured that way, which problems it is solving, and what its main design highlights are.

The rationale layer sits between the cross-skill principles in [bestpractice/](../bestpractice/README.md) and the executable artifacts in [skills/](../skills/index.md). Its role is to make the design reasoning, key tradeoffs, and problem framing explicit instead of leaving them implicit inside `SKILL.md`.

Each rationale document typically covers:

- the concrete problem the skill is solving
- why its workflow, gates, references, and output contract are structured that way
- which common alternatives or failure modes the design is avoiding
- what the main strengths of the final design are

Representative rationale docs:

- [google-search](google-search/design.md)
- [go-code-reviewer](go-code-reviewer/design.md)
- [update-doc](update-doc/design.md)
- [tech-doc-writer](tech-doc-writer/design.md)
- [unit-test](unit-test/design.md)

Use the left navigation to browse the full set of skill-specific rationale documents.
