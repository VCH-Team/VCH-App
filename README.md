# VCH Project: Team Charter

**Project:** VCH Simulation App and companion book
**Director:** Sambridda Ranabhat
**Status:** Active development (app in progress, book not yet started)

---

## 1. Project Overview

VCH (Vessel-Coil-Hydronic) is a two-part project built around one idea: an engineer should be able to understand a thermal-hydraulic system, simulate it, and then design its control system with confidence.

| Deliverable | Purpose | Status |
|---|---|---|
| **Simulation App** | Simulates tank filling, drainage, and heat transfer between coil and tank contents | In progress (architecture being redesigned) |
| **VCH Book** | Explains the simulation engine and the physics behind it, then moves on to system design for control system engineers | Not started |

The app and the book are designed to go hand in hand: the book explains why the engine works the way it does, and the app lets readers see that physics in action.

---

## 2. Background

The project began during an internship at Mechatronics Engineering Pvt. Ltd. (MEPL), where the task was to build an automation system that keeps oil in a liquid state across three containers for long-term storage. While analysing that system and its possible throughput, simulations were developed to test the design.

Before this, the *VCH Sizing Framework* was written as a design guidebook for this class of system. In hindsight it was a specification: it said what to do, but not how or why the underlying engine behaves as it does. Lessons learned since then are the motivation for a refreshed book paired with a purpose-built simulation app.

### Project history

1. **Founding team.** Bikesh Shrestha and Risan Shrestha joined as volunteers and built the first working model.
2. **Review.** The first version worked, but the engine output and the terminal-based interface did not meet the quality bar.
3. **Expansion.** The team was expanded with Kritish Yadav and Avinash Patel as software contributors, and the architecture is being redesigned (3D engine, proper GUI, reporting and visualisation).

---

## 3. Team Structure

```
                 Sambridda Ranabhat
         Director and Head of ME Team
                        |
          +-------------+--------------+
          |                            |
      ME Team                       CE Team
  Bikesh Shrestha            Risan Shrestha (Head)
                              |             |
                      Avinash Patel   Kritish Yadav
```

---

## 4. Roles and Responsibilities

### Sambridda Ranabhat: Director, Head of ME Team
- Sets project direction and manages both the ME and CE teams
- Delegates tasks and keeps work aligned across teams
- Takes an active hands-on part in development, programming, and experimentation
- Owns the physics and engineering definition of the engine and the book's content

### Bikesh Shrestha: ME Contributor
- Mechanical engineering contributor to the team
- Supports the engineering and physics side of the app and the book

### Risan Shrestha: Head of CE Team
- Contributes directly to the software
- Leads the CE team and delegates software responsibilities to speed up development

### Avinash Patel: CE Contributor
- Core software contributor on the application
- Skilled in illustrating the physics reports and in the software side of the system

### Kritish Yadav: CE Contributor
- Core software contributor on the application
- Skilled in illustrating the physics reports and in the software side of the system

---

## 5. How the Two Teams Work Together

| Team | Focus | Hands over to the other team |
|---|---|---|
| **ME Team** | Physics, equations, engineering assumptions, validation of results | Specifications of the physics and expected behaviour |
| **CE Team** | Implementation, interface, performance, reporting and visualisation | Working software and outputs for engineering review |

The ME team defines *what the physics should do*. The CE team builds *how the software does it*. Results flow back to the ME team for validation before they are considered final.

---

## 6. Technical Snapshot

- **Language and performance:** Python with Numba for fast numerical computation
- **Engine:** 3D cell-based model, conserved state per cell (mass and enthalpy), with derived temperature and properties from material property tables
- **Planned operators:** temperature, falling, flattening, thermal expansion, NTU coil transfer, convection, conduction, drain, fill
- **First geometry:** cylindrical tank with serpentine coil, with more complex shapes planned
- **Configuration:** a single source of truth for all inputs, from which the GUI builds its forms
- **Outputs:** per-cycle summaries (hourly), a final summary, and a 3D view of the tank

---

## 7. Working Agreements

### 7.1 Communication
- The team communicates primarily through **Discord**, organised by the Director.
- There is **no chain of command** for communication. Anyone can raise a problem, give advice, offer criticism, or share an idea directly with the Director, at any time.

### 7.2 Task Tracking
- Tasks are tracked through **progress announcements and open communication** with the team.
- Say what you are picking up, post when you finish a chunk, and flag blockers early.

### 7.3 Decisions and Sign-off

| Area | Signed off by |
|---|---|
| Physics code | Sambridda Ranabhat |
| Architectural decisions | Sambridda Ranabhat |
| Software (implementation, interface, tooling) | Risan Shrestha |

This structure exists to **keep decisions centralised and avoid chaos later in development**. It is not about status or hierarchy, and it does not limit who can contribute ideas or challenge a decision.

### 7.4 Git Workflow

**Rules**
1. **`main` is sacred.** Never write code directly on `main`.
2. **Never push directly to `main`.** Always use a Pull Request (PR).
3. **Always commit with `-m "your message"`**, otherwise Git opens a text editor.

**Daily workflow**

1. **Start fresh:** pull the latest code and create a new branch.
   ```bash
   git checkout main
   git pull
   git checkout -b feat/your-task-name
   ```
2. **Do the work:** after each chunk of work, commit and push.
   ```bash
   git add .
   git commit -m "feat: explain what you did here"
   git push -u origin feat/your-task-name
   ```
3. **Merge on GitHub:** click **Compare & pull request**, then **Create pull request**. Wait for the green checkmark (CI tests passing), then **Merge pull request** and **Confirm merge**.
4. **Sync your computer:**
   ```bash
   git checkout main
   git pull
   ```
5. **Clean up:** delete the merged branch.
   ```bash
   git branch -d feat/your-task-name
   ```

**Branch naming**

Keep names simple and descriptive:

- `feat/add-coil-march`
- `fix/drain-bug`
- `docs/update-readme`

**Troubleshooting**

| Problem | What to do |
|---|---|
| "My files disappeared!" | You are probably on `main` before your PR is merged. Run `git checkout your-branch-name`. The files are not lost. |
| Git will not let me checkout `main` because of local changes | Git is protecting your work. Commit first: `git add .` then `git commit -m "wip: saving current work"`. |
| Stuck in a strange terminal screen | You forgot `-m` and Git opened Vim. Press `Esc`, type `:wq`, press `Enter`. |
| Red X on GitHub | Your tests failed. Click the red X, then **Details**, and read the logs. Fix the code and push to the same branch. The X turns green automatically. |

### 7.5 Terms of Participation
- This is a **hobby project**. There is no monetary compensation for any team member.
- Every contributor will be **credited by name in the book's acknowledgements**.

---

## 8. Acknowledgements

Thank you to the people who make this project possible:

- Bikesh Shrestha
- Risan Shrestha
- Avinash Patel
- Kritish Yadav
