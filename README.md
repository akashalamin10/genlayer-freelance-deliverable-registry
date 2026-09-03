# FreelanceDeliverableRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-verified
freelance deliverable acceptance — usable by any freelance/marketplace platform as
a neutral, tamper-resistant acceptance oracle.

## Why this is a primitive, not a thin demo

- **Real web access as part of consensus**: instead of trusting a submitted text
  blob, validators independently fetch the actual deliverable content from its URL
  via `gl.nondet.web.render` and evaluate that fetched content — this uses
  GenLayer's internet-access capability, not just LLM judgment on user-supplied text.
- **Structured, closed-vocabulary consensus**: validators must agree on a
  `(status, unmet_criteria)` pair via `gl.eq_principle.strict_eq` — a small, closed
  status vocabulary (`accepted` / `needs_revision` / `rejected`) makes strict
  equivalence realistically achievable, unlike asking for identical free text.
- **Revision lifecycle, not a single verdict**: `revision_count` and per-revision
  submission records let a job go through multiple rounds of feedback and
  resubmission — mirroring how real freelance work actually gets accepted.
- **Independent dispute/contest round**: `contest_status` re-runs the whole
  evaluation (including re-fetching the URL) from scratch with the freelancer's
  counter-argument injected, rather than blindly trusting or re-running the same
  prompt. Reputation counters (`upheld` / `overturned`) track contest outcomes
  per address.
- **Decoupled from payment**: the contract does not move funds itself — it exposes
  a verifiable, on-chain acceptance status that an external escrow/payment layer
  (on this or another platform) can read and act on. This keeps the primitive
  narrowly scoped and reusable rather than baking in one platform's payment logic.

## State design

| Field         | Type                | Purpose                                             |
|----------------|---------------------|------------------------------------------------------|
| `owner`        | `str`               | Platform/admin address                               |
| `jobs`         | `TreeMap[str, str]` | job_id -> JSON {client, freelancer, criteria, status, revision_count} |
| `submissions`  | `TreeMap[str, str]` | "job_id:revision_number" -> JSON submission record   |
| `disputes`     | `TreeMap[str, str]` | job_id -> JSON dispute record                        |
| `reputation`   | `TreeMap[str, str]` | address -> JSON {upheld, overturned}                 |

## How consensus is used

1. `submit_deliverable` builds a closure that (a) fetches the deliverable URL via
   `gl.nondet.web.render`, (b) prompts an LLM to classify it against the job's
   criteria into `{status, unmet_criteria}`.
2. `gl.eq_principle.strict_eq` re-runs this closure across validators and only
   accepts the result if they all agree on the same `(status, unmet_criteria)`
   pair — meaning independent fetches of the same URL and independent LLM calls
   converged on the same structured verdict.
3. `contest_status` repeats the same pattern with the freelancer's counter-argument
   injected into the prompt, producing a fresh, independent consensus result.

## Suggested tests (GenLayer Studio)

- **Deploy**, then `post_job` with 2–3 concrete criteria (e.g. "must include a
  working code sample", "must include a summary paragraph").
- **Accepted case**: submit a URL whose content clearly satisfies all criteria,
  assert `status == "accepted"`.
- **Needs-revision case**: submit a URL missing one criterion, assert
  `status == "needs_revision"` and the missing criterion appears in
  `unmet_criteria`, and `revision_count` incremented.
- **Resubmission**: call `submit_deliverable` again with an improved URL, assert
  a new submission record exists under the incremented revision number.
- **Contest — overturned**: contest a `rejected`/`needs_revision` status with a
  strong argument (or an updated URL argument), assert `overturned == True` and
  reputation `overturned` incremented for the contester.
- **Contest — upheld**: contest a correctly-rejected deliverable weakly, assert
  `overturned == False` and reputation `upheld` incremented.
- **Duplicate job guard**: assert `post_job` reverts if `job_id` already exists.

## Caveats

- GenLayer's exact SDK surface (`gl.nondet.web.render`, `gl.eq_principle.*`,
  `gl.message.*`) is evolving — verify current method names/signatures against
  GenLayer's latest docs before deploying.
- `gl.nondet.web.render` requires the deliverable URL to be publicly reachable;
  private/auth-gated URLs won't work without an extension to this pattern.
- No token transfer logic is included (by design, and because GenLayer Studio
  does not currently support token transfers) — pairing this with an escrow
  contract that reads `get_job(job_id).status` is a natural extension.
