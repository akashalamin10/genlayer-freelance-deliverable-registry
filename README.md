# FreelanceDeliverableRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-verified
freelance deliverable acceptance — usable by any freelance/marketplace platform as
a neutral, tamper-resistant acceptance oracle.

**Deployed contract (GenLayer Studio):** `0x6CBD78377Ee9D0EE6B5D34A8eA3D709DaD53b991`
[View on Explorer](https://explorer-studio.genlayer.com/address/0x6CBD78377Ee9D0EE6B5D34A8eA3D709DaD53b991)

## Why this is a primitive, not a thin demo

- **Real web access as part of consensus**: instead of trusting a submitted text
  blob, validators independently fetch the actual deliverable content from its URL
  via `gl.nondet.web.render` and evaluate that fetched content — this uses
  GenLayer's internet-access capability, not just LLM judgment on user-supplied text.
- **Structured consensus with tolerance for wording**: validators must agree on a
  `(status, unmet_criteria)` result via `gl.eq_principle.prompt_comparative`, with
  an explicit principle describing what counts as agreement — the status must match
  exactly, but `unmet_criteria` wording can vary as long as it refers to the same
  underlying unmet item. This is more robust than requiring byte-identical LLM output.
- **Revision lifecycle, not a single verdict**: `revision_count` and per-revision
  submission records let a job go through multiple rounds of feedback and
  resubmission — mirroring how real freelance work actually gets accepted.
- **Independent dispute/contest round**: `contest_status` re-runs the whole
  evaluation (including re-fetching the URL) from scratch with the contester's
  counter-argument injected, rather than blindly trusting or re-running the same
  prompt. Reputation counters (`upheld` / `overturned`) track contest outcomes
  per address.
- **Decoupled from payment**: the contract does not move funds itself — it exposes
  a verifiable, on-chain acceptance status that an external escrow/payment layer
  can read and act on, keeping the primitive narrowly scoped and reusable.

## State design

| Field         | Type                | Purpose                                             |
|----------------|---------------------|--------------------------------------------------------|
| `owner`        | `str`               | Platform/admin address                               |
| `jobs`         | `TreeMap[str, str]` | job_id -> JSON {client, freelancer, criteria, status, revision_count} |
| `submissions`  | `TreeMap[str, str]` | "job_id:revision_number" -> JSON submission record   |
| `disputes`     | `TreeMap[str, str]` | job_id -> JSON dispute record                        |
| `reputation`   | `TreeMap[str, str]` | address -> JSON {upheld, overturned}                 |

## How consensus is used

1. `submit_deliverable` builds a closure that (a) fetches the deliverable URL via
   `gl.nondet.web.render`, (b) prompts an LLM to classify it against the job's
   criteria into `{status, unmet_criteria}`.
2. `gl.eq_principle.prompt_comparative` re-runs this closure across validators and
   only accepts the result if they agree under the stated principle — independent
   fetches of the same URL and independent LLM calls converge on the same
   structured verdict.
3. `contest_status` repeats the same pattern with the contester's counter-argument
   injected into the prompt, producing a fresh, independent consensus result.

```python
def get_verdict() -> str:
    page_text = gl.nondet.web.render(deliverable_url, mode="text")
    prompt = self._evaluation_prompt(page_text, criteria)
    raw = gl.nondet.exec_prompt(prompt, response_format="json")
    return json.dumps(self._normalize_verdict(raw, criteria), sort_keys=True)

agreed = gl.eq_principle.prompt_comparative(
    get_verdict,
    principle="status must be exactly the same; unmet_criteria may differ in "
              "wording only if they refer to the same underlying unmet criterion."
)
```

## Verified on-chain test results

All transactions below were executed live on GenLayer Studio and are visible on
[the Explorer page for this contract](https://explorer-studio.genlayer.com/address/0x6CBD78377Ee9D0EE6B5D34A8eA3D709DaD53b991).

| Step | Method | Tx Hash | Result |
|---|---|---|---|
| 1 | Deploy | `0xa9ed1cad...0c57fd40` | SUCCESS |
| 2 | `post_job` (job1) | `0x672a6c39...b4208733` | SUCCESS |
| 3 | `submit_deliverable` (job1, rev 0) | `0xba07c289...a1cc8754` | SUCCESS — `needs_revision`, missing a code snippet |
| 4 | `submit_deliverable` (job1, rev 1) | `0x6068ce9a...546f32f6` | SUCCESS — `accepted`, all criteria met |
| 5 | `post_job` (job2) | `0x39383328...8ced277f` | SUCCESS |
| 6 | `submit_deliverable` (job2) | `0x2b823934...5b0f78ac` | SUCCESS — `rejected` (deliberately unsatisfiable French-language criterion) |
| 7 | `contest_status` (job2) | `0x5291cb0d...dad87f0e` | SUCCESS — contest dismissed, `overturned: false` |

Full test narrative and raw responses are in [TESTS.md](./TESTS.md).

### What this demonstrates

- A deliverable correctly moved from `needs_revision` to `accepted` after the
  freelancer fixed the one genuinely missing criterion — validators did not just
  rubber-stamp either submission, they identified the specific gap both times.
- A deliberately unsatisfiable job (English content against a French-only
  requirement) was correctly rejected, and a weak contest against that rejection
  was correctly dismissed rather than blindly overturned — with the contester's
  reputation `upheld` counter incrementing to reflect that.
- Multiple validator rounds showed real GenLayer Optimistic Democracy behavior
  (leader rotation on disagreement) rather than a single-model rubber stamp.

## Suggested tests to reproduce (GenLayer Studio)

- Deploy, then `post_job` with 2–3 concrete criteria.
- Submit a URL missing one criterion — confirm `needs_revision` and the correct
  `unmet_criteria` entry, and `revision_count` increments.
- Resubmit an improved URL — confirm `accepted` and a new revision record exists.
- Contest a rejected/needs_revision status with a weak argument — confirm
  `overturned: false` and `upheld` reputation increments.
- Contest with a materially different (better) URL/argument — confirm
  `overturned: true` is possible when justified.
- Assert `post_job` reverts on a duplicate `job_id`.

## Caveats

- GenLayer's exact SDK surface (`gl.nondet.web.render`, `gl.eq_principle.*`,
  `gl.message.*`) is evolving — verify current method names/signatures against
  GenLayer's latest docs before deploying.
- `gl.nondet.web.render` requires the deliverable URL to be publicly reachable;
  private/auth-gated URLs won't work without an extension to this pattern.
- No token transfer logic is included (by design, and because GenLayer Studio
  does not currently support token transfers) — pairing this with an escrow
  contract that reads `get_job(job_id).status` is a natural extension.

  ### Example: how the consensus closure looks

```python
def get_verdict() -> str:
    page_text = gl.nondet.web.render(deliverable_url, mode="text")
    prompt = self._evaluation_prompt(page_text, criteria)
    raw = gl.nondet.exec_prompt(prompt, response_format="json")
    return json.dumps(self._normalize_verdict(raw, criteria), sort_keys=True)

agreed = gl.eq_principle.prompt_comparative(
    get_verdict,
    principle="status must be exactly the same; unmet_criteria may differ in wording only if they refer to the same underlying unmet criterion."
)
```
Each GenLayer validator independently fetches the deliverable URL and queries its own LLM; `prompt_comparative` only accepts the result into consensus once validators agree under the stated principle.
