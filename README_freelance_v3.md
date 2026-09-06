# FreelanceDeliverableRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-verified
freelance deliverable acceptance — usable by any freelance/marketplace platform as
a neutral, tamper-resistant acceptance oracle.

**Deployed contract (GenLayer Studio):** `0x46...5F81` (full address in Studio Explorer)

## Why this is a primitive, not a thin demo

- **Real web access as part of consensus**: validators independently fetch the
  actual deliverable content from its URL via `gl.nondet.web.render` and evaluate
  that fetched content — this uses GenLayer's internet-access capability, not
  just LLM judgment on user-supplied text.
- **Structured consensus with tolerance for wording**: validators must agree on a
  `(status, unmet_criteria)` result via `gl.eq_principle.prompt_comparative`.
- **Authenticated party binding**: `post_job` binds the `client` field to
  `gl.message.sender_address` automatically — the caller cannot supply an
  arbitrary client identity. `submit_deliverable` and `contest_status` are both
  restricted to the specific `freelancer` address recorded at job creation; any
  other caller is reverted. This closes a griefing vector where an unrelated
  address could submit or contest someone else's job and accumulate reputation
  under an unauthorized identity.
- **Revision lifecycle**: `revision_count` and per-revision submission records
  let a job go through multiple rounds of feedback and resubmission.
- **Independent dispute round**: `contest_status` re-runs the whole evaluation
  (re-fetching the URL) from scratch with the freelancer's counter-argument
  injected, and updates on-chain reputation counters per address.
- **Decoupled from payment**: the contract only exposes a verifiable acceptance
  status; an external escrow/payment layer can read and act on it.

## State design

| Field         | Type                | Purpose                                             |
|----------------|---------------------|--------------------------------------------------------|
| `owner`        | `str`               | Platform/admin address                               |
| `jobs`         | `TreeMap[str, str]` | job_id -> JSON {client, freelancer, criteria, status, revision_count} |
| `submissions`  | `TreeMap[str, str]` | "job_id:revision_number" -> JSON submission record   |
| `disputes`     | `TreeMap[str, str]` | job_id -> JSON dispute record                        |
| `reputation`   | `TreeMap[str, str]` | address -> JSON {upheld, overturned}                 |

## How consensus and access control work together

1. `post_job(job_id, freelancer, criteria)` — the caller becomes `client`
   automatically via `gl.message.sender_address`; `freelancer` is the specific
   address authorized to act on this job.
2. `submit_deliverable` asserts `caller == job["freelancer"]` before doing
   anything else, then fetches the deliverable URL and runs
   `gl.eq_principle.prompt_comparative` for a structured `(status,
   unmet_criteria)` consensus result.
3. `contest_status` asserts the same `caller == job["freelancer"]` restriction,
   then re-fetches the URL and re-runs an independent consensus round with the
   freelancer's counter-argument injected. Reputation updates only happen for
   this verified caller.

```python
@gl.public.write
def submit_deliverable(self, job_id: str, deliverable_url: str) -> None:
    job = json.loads(self.jobs[job_id])
    caller = self._sender()
    assert caller == job["freelancer"], "only the assigned freelancer may submit a deliverable"
    ...
```

## Verified on-chain test evidence

| Test | Tx | Result |
|---|---|---|
| Deploy (fixed contract) | `0x2b86067271c3aaabfaa9ea9ffdee05fc88ed1bbbbcde527122ee1403680e06cd` | SUCCESS |
| `post_job` (j1) — client auto-bound to sender | `0xc5ab1d134060ec933bf6049305ca82b016a4767d941b4bf73501fbec20dcc455` | SUCCESS |
| `submit_deliverable` (j1) by the correct freelancer | `0x307328f9eaa986d024203af44fb3334bbf68b40bfda4d37fea4f3d3a8cd12cdc` | SUCCESS — `accepted` |
| `submit_deliverable` (j2) by a non-freelancer address | `0x13af1cbbadabfb2aeed5f41e2d9ddc798e1c9fb05abef5bd7ea04992291cd11f` | ERROR: `only the assigned freelancer may submit a deliverable` |
| `submit_deliverable` (j2) by the correct freelancer | `0xb76b45497739e357c9a703e9944b8fcdb20eb73086670cea5617e0db9f836804` | SUCCESS — `rejected` |
| `contest_status` (j2) by an unrelated third-party address | `0x939b519a692dcb2e5af49c3fca34017a2ddb6a88cdbd7decd8fe85ded23c1035` | ERROR: `only the assigned freelancer may contest a review` |

`get_job("j1")` confirms `client` was populated automatically from the caller's
address, never supplied as a raw string parameter:
```json
{
  "client": "0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48",
  "freelancer": "0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48",
  "criteria": ["must mention consensus", "must include a code example"],
  "status": "accepted"
}
```

Full test narrative in [TESTS.md](./TESTS.md).

## Suggested tests to reproduce (GenLayer Studio)

- Deploy, then `post_job` — confirm `client` in `get_job` matches your connected
  wallet address even though you never passed it as a parameter.
- Attempt `submit_deliverable` from a different address than the recorded
  `freelancer` — confirm it reverts.
- Submit from the correct `freelancer` address — confirm it succeeds.
- Attempt `contest_status` from an address other than the `freelancer` —
  confirm it reverts.
- Contest from the correct `freelancer` — confirm it succeeds and updates
  reputation.

## Caveats

- GenLayer's exact SDK surface (`gl.nondet.web.render`, `gl.eq_principle.*`,
  `gl.message.*`) is evolving — verify current method names/signatures against
  GenLayer's latest docs before deploying.
- `gl.nondet.web.render` requires the deliverable URL to be publicly reachable.
- No token transfer logic is included (Studio does not currently support
  token transfers) — pairing this with an escrow contract that reads
  `get_job(job_id).status` is a natural extension.
