# AI Failure Agent — V1 Foundation

> **Implementation choice:** V1 uses [`pi-coding-agent-action`](https://github.com/shaftoe/pi-coding-agent-action/tree/develop) as the agent runtime. We build the workflow, prompts, schemas, orchestration and safety boundaries around it instead of implementing a coding-agent runtime from scratch.


## 1. Cel projektu

Zbudować agenta AI uruchamianego w GitHub Actions, który reaguje na failure w istniejącym CI workflow.

Wersja V1 ma:

1. wykryć failure,
2. uruchomić mocnego agenta **Inspector/Triage**,
3. przeanalizować logi, zmiany w PR i kod,
4. utworzyć ustrukturyzowany raport z hipotezami,
5. zdecydować, czy potrzebny jest agent naprawczy,
6. uruchomić tańszego/słabszego agenta **Fixer**, jeśli jest potrzebny,
7. skopiować/checkoutować repozytorium i pracować na branchu istniejącego PR,
8. zweryfikować hipotezę,
9. wprowadzić fix,
10. uruchomić testy,
11. jeśli fix działa — zrobić commit i push do istniejącego PR.

### Najważniejsza zasada

**Inspector diagnozuje. Fixer wykonuje i weryfikuje. GitHub Actions orkiestruje.**

---

# 2. Architektura V1

```text
                         GitHub Repository
                                │
                                ▼
                         Existing CI workflow
                                │
                    ┌───────────┴───────────┐
                    │                       │
                  PASS                    FAILURE
                                            │
                                            ▼
                                  AI Failure Agent
                                            │
                                            ▼
                              ┌─────────────────────┐
                              │ Inspector / Triage   │
                              │ Strong LLM           │
                              │                     │
                              │ • logs              │
                              │ • PR changes        │
                              │ • repository        │
                              │ • hypotheses        │
                              │ • confidence        │
                              └──────────┬──────────┘
                                         │
                                  TriageReport
                                         │
                                         ▼
                              GitHub Actions decision
                                         │
                         ┌───────────────┴───────────────┐
                         │                               │
                   needs_fix=false                needs_fix=true
                         │                               │
                         ▼                               ▼
                       END                         ┌─────────────┐
                                                   │   Fixer     │
                                                   │ weaker LLM  │
                                                   │             │
                                                   │ • checkout  │
                                                   │ • inspect   │
                                                   │ • validate  │
                                                   │ • fix       │
                                                   │ • test      │
                                                   │ • commit    │
                                                   │ • push      │
                                                   └──────┬──────┘
                                                          │
                                                          ▼
                                                    Existing PR
```

---

# 3. Podział odpowiedzialności

## Inspector

Inspector jest agentem diagnostycznym.

Powinien:

- pobrać informacje o failed workflow,
- znaleźć failed jobs i steps,
- pobrać relevant logs,
- przeanalizować zmiany w PR,
- przeanalizować istotne fragmenty repozytorium,
- zidentyfikować prawdopodobną przyczynę,
- stworzyć jedną lub kilka hipotez,
- ocenić confidence,
- określić, czy problem nadaje się do automatycznej naprawy,
- przekazać rekomendację Fixerowi.

Inspector **nie powinien modyfikować repozytorium**.

### Inspector nie powinien robić

- commitów,
- push,
- tworzenia PR,
- arbitralnego modyfikowania kodu.

Jego zadaniem jest odpowiedzieć:

> Co się zepsuło, dlaczego prawdopodobnie się zepsuło i czy warto próbować to automatycznie naprawić?

---

## Fixer

Fixer jest agentem wykonawczym.

Powinien:

- otrzymać raport Inspectora,
- checkoutować właściwy branch/commit PR,
- samodzielnie sprawdzić kod,
- zweryfikować hipotezę Inspectora,
- znaleźć właściwe miejsce zmiany,
- wprowadzić minimalny fix,
- uruchomić odpowiednie testy,
- ocenić rezultat,
- w razie potrzeby iterować,
- uruchomić szerszą walidację,
- zrobić commit,
- wypchnąć commit do istniejącego PR.

### Kluczowa zasada

Fixer **nie powinien ślepo ufać Inspectorowi**.

Inspector dostarcza hipotezę:

```text
Hipothesis: email is not normalized before repository insertion.
Confidence: 0.87
```

Fixer musi ją potwierdzić:

```text
Czy rzeczywiście kod zachowuje się w ten sposób?
Czy ta zmiana naprawia failure?
```

Dopiero wtedy powinien wykonać fix.

---

# 4. GitHub Actions jako orchestrator

GitHub Actions powinien być warstwą orkiestracji.

Nie potrzebujemy osobnego "master LLM".

Przepływ:

```text
CI failure
    │
    ▼
workflow_run
    │
    ▼
Inspector
    │
    ▼
structured JSON
    │
    ▼
GitHub Actions
    │
    ├── needs_fix = false → END
    │
    └── needs_fix = true → Fixer
```

Decyzje typu:

```text
if needs_fix == true
```

powinny być wykonywane deterministycznie przez workflow, a nie przez kolejny model.

---

# 5. Trigger

V1 wykorzystuje GitHub Actions `workflow_run`.

Przykład:

```yaml
name: AI Failure Agent

on:
  workflow_run:
    workflows: ["CI"]
    types:
      - completed
```

Następnie workflow sprawdza:

```yaml
if: ${{ github.event.workflow_run.conclusion == 'failure' }}
```

Dzięki temu AI workflow reaguje tylko na failure istniejącego CI.

---

# 6. Inspector input

Inspector powinien mieć dostęp przynajmniej do:

```text
Workflow run
├── run id
├── workflow name
├── conclusion
├── branch
├── commit SHA
└── PR information

Jobs
├── job names
├── status
├── conclusion
└── steps

Logs
└── failed/relevant logs

Repository
├── relevant files
├── configuration
└── source code

PR changes
├── changed files
└── diff
```

Nie należy bez potrzeby wrzucać całego repozytorium i całych logów do promptu.

---

# 7. Log processing

Typowy CI może wygenerować tysiące lub dziesiątki tysięcy linii logów.

Nie należy przekazywać całych logów bezpośrednio do LLM.

Lepszy pipeline:

```text
Raw logs
    │
    ▼
Log parser
    │
    ▼
Find failed step
    │
    ▼
Extract errors / stack traces
    │
    ▼
Relevant context
    │
    ▼
Inspector
```

Przykładowy fragment wejściowy:

```text
ERROR: AssertionError
Expected: 200
Actual: 500

tests/test_api.py:42

FAILED tests/test_api.py::test_create_user
```

Inspector powinien dostać przede wszystkim informacje związane z failure, a nie cały noise z CI.

---

# 8. Inspector output — kontrakt

Najważniejszym elementem komunikacji pomiędzy agentami powinien być **structured output**.

Przykład:

```json
{
  "needs_fix": true,
  "confidence": 0.87,
  "failure": {
    "type": "test_failure",
    "job": "unit-tests",
    "step": "Run tests",
    "test": "test_create_user"
  },
  "hypotheses": [
    {
      "description": "Email is not normalized before repository insertion",
      "confidence": 0.87,
      "evidence": [
        "tests/test_users.py:42",
        "src/users/service.py:71",
        "PR changed email validation logic"
      ]
    }
  ],
  "recommended_action": {
    "type": "code_change",
    "description": "Normalize email before calling UserRepository.create()"
  }
}
```

Model powinien generować ten output zgodnie ze zdefiniowanym schematem.

Należy go następnie walidować po stronie aplikacji.

---

# 9. Pydantic / schema

Przykładowy model:

```python
from pydantic import BaseModel


class Hypothesis(BaseModel):
    description: str
    confidence: float
    evidence: list[str]


class Failure(BaseModel):
    type: str
    job: str
    step: str
    test: str | None = None


class Action(BaseModel):
    type: str
    description: str


class TriageReport(BaseModel):
    needs_fix: bool
    confidence: float
    failure: Failure
    hypotheses: list[Hypothesis]
    recommended_action: Action
```

Dzięki temu przepływ wygląda tak:

```text
LLM
 ↓
JSON
 ↓
Pydantic validation
 ↓
TriageReport
 ↓
GitHub Actions decision
 ↓
Fixer
```

Nie powinno być:

```text
LLM A → random text → LLM B
```

---

# 10. Fixer workflow

Fixer powinien działać w ephemeral środowisku GitHub Actions runnera.

```text
GitHub-hosted runner
        │
        ├── checkout repository
        ├── install dependencies
        ├── run agent
        ├── modify code
        ├── run tests
        ├── git commit
        └── git push
               │
               ▼
        runner destroyed
```

Na V1 nie ma potrzeby używania ECS/Fargate.

Fargate lub inny izolowany sandbox może być późniejszym etapem, szczególnie jeśli projekt będzie wykonywał niezaufany kod.

---

# 11. Fixer loop

Fixer powinien mieć ograniczoną pętlę naprawczą.

```text
Receive TriageReport
        │
        ▼
Checkout PR branch
        │
        ▼
Inspect repository
        │
        ▼
Validate hypothesis
        │
        ├── hypothesis wrong
        │       │
        │       ▼
        │   investigate
        │
        ▼
Implement minimal fix
        │
        ▼
Run targeted tests
        │
    ┌───┴────┐
    │        │
  PASS      FAIL
    │        │
    │        ▼
    │     analyze
    │     & retry
    │
    ▼
Run broader validation
    │
    ▼
Commit
    │
    ▼
Push to PR branch
```

W V1 należy ograniczyć liczbę iteracji, np. do 2–3.

Agent nie powinien mieć nieskończonej pętli:

```text
fix → test → fail → fix → test → fail → ...
```

---

# 12. Existing PR

V1 powinien działać na **istniejącym PR**.

Preferowany przepływ:

```text
PR #123
    │
    ▼
CI failure
    │
    ▼
Inspector
    │
    ▼
Fixer
    │
    ▼
checkout PR branch
    │
    ▼
modify files
    │
    ▼
commit
    │
    ▼
push to SAME branch
    │
    ▼
PR #123 updated
```

Nie tworzymy nowego PR dla każdego automatycznego fixa.

Dzięki temu użytkownik widzi historię:

```text
PR #123

commit 1: original changes
commit 2: AI fix

CI
❌
↓
🤖 fix
↓
✅
```

---

# 13. GitHub API

Agent będzie potrzebował GitHub API do:

```text
Workflow runs
Jobs
Job logs
PR information
PR diff
Repository files
Commits
```

W przypadku użycia Pi nie budujemy tego wrappera na starcie. Pi Action zapewnia GitHub-oriented tooling.

Jeżeli V1 ujawni konkretny brak w dostępnych narzędziach, dodamy mały custom tool zamiast od razu budować pełnego klienta GitHub API.

---

# 14. Tools Inspectora

Inspector powinien mieć kontrolowany zestaw tools.

Przykładowo:

```python
get_workflow_run()
get_failed_jobs()
get_job_logs()
get_pull_request()
get_pull_request_diff()
get_file()
search_repository()
get_commit()
```

Architektura:

```text
                 Inspector
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   GitHub tools   repo tools   analysis
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
              TriageReport
```

Tools powinny być małe i mieć jasno określone odpowiedzialności.

---

# 15. Tools Fixera

Fixer potrzebuje dodatkowo operacji związanych z edycją i walidacją:

```text
read_file()
search_repository()
get_git_diff()
edit_file()
run_command()
run_tests()
git_status()
git_diff()
git_commit()
git_push()
```

Warto rozdzielić:

```text
Read tools
    ↓
Analysis
    ↓
Write tools
    ↓
Validation
    ↓
Git tools
```

---

# 16. Security — V1

Początkowo Inspector powinien mieć minimalne uprawnienia:

```yaml
permissions:
  actions: read
  contents: read
```

Fixer będzie potrzebował dodatkowych uprawnień do pracy z branchami/PR, ale należy przyznać tylko te, które są faktycznie potrzebne.

Najważniejsze zasady:

- minimal permissions,
- ograniczony zakres GitHub tokena,
- ephemeral runner,
- brak sekretów przekazywanych do promptu,
- nie wykonywać bezpośrednio poleceń wygenerowanych przez LLM bez kontroli,
- ograniczyć dostęp agenta do repository,
- ograniczyć liczbę iteracji,
- logować działania agenta.

---

# 17. Model strategy

V1 zakłada dwa poziomy modeli.

## Inspector

**Strong / reasoning-oriented model**

Cel:

- dobre rozumowanie,
- analiza logów,
- analiza diffów,
- tworzenie hipotez,
- wysoka jakość diagnozy.

Koszt i latency są mniej istotne.

## Fixer

**Cheaper / weaker model**

Cel:

- wykonywanie jasno określonego zadania,
- praca z kodem,
- iteracyjne testowanie,
- minimalne zmiany.

Fixer dostaje kontekst przygotowany przez Inspectora, więc nie musi wykonywać całego procesu diagnostycznego od zera.

---

# 18. Prompt design

Prompt Inspectora powinien jasno określać rolę:

```text
You are the Inspector agent.

Your job is to diagnose a failed CI workflow.

You must:
1. inspect the failure,
2. inspect relevant PR changes,
3. inspect relevant repository files,
4. generate plausible hypotheses,
5. assess confidence,
6. determine whether the failure is suitable for automated fixing.

You must NOT modify the repository.

Return only the defined structured output.
```

Prompt Fixera:

```text
You are the Fixer agent.

You received a triage report from another agent.

Your job is to:
1. inspect the repository,
2. validate the proposed hypothesis,
3. implement the smallest reasonable fix,
4. run relevant tests,
5. verify that the failure is fixed,
6. run broader validation,
7. commit and push the fix to the existing PR branch.

Do not blindly trust the triage report.
If the hypothesis is incorrect, investigate the actual root cause.

Do not make unrelated changes.
```

---

# 19. Repository structure

Proponowana struktura:

```text
.github/
└── workflows/
    ├── ci.yml
    └── ai-failure-agent.yml

agent/
├── inspector/
│   ├── agent.py
│   ├── prompts.py
│   └── schema.py
│
├── fixer/
│   ├── agent.py
│   ├── prompts.py
│   └── tools.py
│
├── github/
│   ├── client.py
│   ├── workflows.py
│   ├── jobs.py
│   ├── logs.py
│   ├── repository.py
│   └── pull_requests.py
│
└── common/
    └── models.py

tests/
├── inspector/
└── fixer/
```

---

# 20. V1 — minimal scope

V1 powinien być celowo mały.

### Musimy mieć

- [x] GitHub Actions trigger
- [x] detection of CI failure
- [x] Inspector agent
- [x] strong LLM
- [x] GitHub API access
- [x] log extraction
- [x] PR diff access
- [x] structured triage report
- [x] conditional Fixer step
- [x] weaker/cheaper LLM
- [x] repository checkout
- [x] code inspection
- [x] hypothesis validation
- [x] code modification
- [x] test execution
- [x] commit
- [x] push to existing PR branch

### Nie potrzebujemy jeszcze

- [ ] RAG
- [ ] vector database
- [ ] long-term memory
- [ ] multi-agent swarm
- [ ] reviewer agent
- [ ] Fargate
- [ ] Kubernetes
- [ ] automatic issue creation
- [ ] new PR creation
- [ ] complex observability platform
- [ ] failure history database
- [ ] custom GitHub API client (only if Pi tooling proves insufficient)

---

# 21. Definition of Done

V1 można uznać za działającą, kiedy:

```text
1. Developer opens PR
          ↓
2. CI fails
          ↓
3. workflow_run triggers AI agent
          ↓
4. Inspector receives failure context
          ↓
5. Inspector identifies likely root cause
          ↓
6. Inspector returns valid TriageReport
          ↓
7. GitHub Actions evaluates needs_fix
          ↓
8. Fixer starts
          ↓
9. Fixer checks out PR branch
          ↓
10. Fixer validates hypothesis
          ↓
11. Fixer modifies code
          ↓
12. Tests pass
          ↓
13. Fixer commits
          ↓
14. Fixer pushes to existing PR
          ↓
15. CI runs again
          ↓
16. CI passes
```

---

# 22. Najważniejsze decyzje architektoniczne

## Decision 1

**GitHub Actions = orchestrator**

LLM nie steruje całym systemem.

## Decision 2

**Inspector ≠ Fixer**

Inspector diagnozuje, Fixer wykonuje.

## Decision 3

**Structured output pomiędzy agentami**

Nie przekazujemy dowolnego tekstu.

```text
Inspector
    ↓
TriageReport
    ↓
Fixer
```

## Decision 4

**Fixer musi zweryfikować hipotezę**

Raport Inspectora jest wskazówką, nie prawdą absolutną.

## Decision 5

**Existing PR branch**

Agent aktualizuje istniejący PR zamiast tworzyć kolejny.

## Decision 6

**Pi Coding Agent Action as agent runtime**

Nie budujemy własnego coding-agent runtime; Pi jest warstwą wykonawczą dla Inspectora i Fixera.

## Decision 7

**Ephemeral GitHub runner**

Na V1 nie potrzebujemy Fargate.

## Decision 8

**Minimal permissions**

Agent dostaje tylko wymagane uprawnienia.

## Decision 9

**Limited repair loop**

Agent może wykonać ograniczoną liczbę prób.

---

# 23. Naturalne rozszerzenia po V1

Po stabilnym V1 można dodać:

```text
V1
│
├── Inspector
├── Fixer
└── Existing PR
      │
      ▼
V2
├── failure history
├── better log parsing
├── reviewer agent
├── human approval
└── richer GitHub integration
      │
      ▼
V3
├── isolated sandbox
├── Fargate
├── persistent memory
├── failure knowledge base
└── multi-agent workflow
```

Najpierw jednak należy doprowadzić V1 do sytuacji, w której agent potrafi **powtarzalnie zdiagnozować i naprawić prosty failure bez ingerencji człowieka**.
