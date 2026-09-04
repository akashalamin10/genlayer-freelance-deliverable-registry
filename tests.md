# Test Results — FreelanceDeliverableRegistry

All tests below were executed live on GenLayer Studio (not simulated locally).

**Deployed contract:** `0x6CBD78377Ee9D0EE6B5D34A8eA3D709DaD53b991`
**Network:** GenLayer Studio (studionet)
**Test account:** `0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48`

---

## 1. Deploy

- **Tx:** `0xa9ed1cadf13bffa92ea207a2a36c6fecd51e517005228463324027aa0c57fd40`
- **Constructor args:** `owner = 0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48`
- **Result:** SUCCESS, FINALIZED

## 2. post_job — job1

- **Tx:** `0x672a6c39158b6cfe31e5d2ff6c5bee4628c678d93432431ef0a719deb4208733`
- **Input:** `job_id="job1"`, `criteria=["must explain how consensus is used", "must mention GenLayer validators", "must include example code or a code snippet"]`
- **Result:** SUCCESS, FINALIZED

## 3. submit_deliverable — needs_revision case (revision 0)

- **Tx:** `0xba07c28945ed20d7d7840c6b7cb851216c026b2a9e40587ab10eebd5a1cc8754`
- **Input:** `job_id="job1"`, `deliverable_url` pointing to the project's own README (before a code snippet was added)
- **Consensus note:** two rounds of "Majority disagreement, rotating the leader" before validators converged — GenLayer's Optimistic Democracy leader-rotation mechanism observed live.

`get_submission("job1", 0)`:
```json
{
  "status": "needs_revision",
  "unmet_criteria": ["must include example code or a code snippet"],
  "revision_number": 0
}
```
Validators independently fetched the URL via `gl.nondet.web.render` and correctly identified the one genuinely missing criterion — the README explained consensus and mentioned validators, but had no code block yet.

## 4. Revision — freelancer adds a code snippet, resubmits (revision 1)

- **Tx:** `0x6068ce9a7009d71219fad700877511e919b0f13cd35cb3e92614aaa5546f32f6`
- **Input:** same `job_id`, updated `deliverable_url` (README now includes a code example)

`get_submission("job1", 1)`:
```json
{
  "status": "accepted",
  "unmet_criteria": [],
  "revision_number": 1
}
```
`get_job("job1")` confirms `status: "accepted"`, `revision_count: 1` — a full revision lifecycle (reject → fix → accept) verified on-chain.

## 5. post_job — job2 (designed to fail, for contest testing)

- **Tx:** `0x3938332830c1150238d4d4918fb234dbc8493db54739b37889ff10a48ced277f`
- **Input:** `job_id="job2"`, `criteria=["must be written entirely in French"]`

## 6. submit_deliverable — rejected case

- **Tx:** `0x2b8239346a24d40eb7b30e6870ad1c87312ddb12b8ba338299f8ae815b0f78ac`
- **Input:** same English-language README URL against a French-only requirement
- **Result:** `status: "rejected"` — correctly identified as not meeting the (deliberately unsatisfiable) criterion.

## 7. contest_status — dismissed case

- **Tx:** `0x5291cb0d8050f089f8763e15c0984b9db5857d5a88649a3e178ff077dad87f0e`
- **Input:** `contester_argument = "This deliverable is written in clear technical English, which was never actually a valid requirement for this type of project."`

`get_dispute("job2")`:
```json
{
  "prior_status": "rejected",
  "new_status": "rejected",
  "overturned": false
}
```
`get_reputation(<address>)`:
```json
{"upheld": 1, "overturned": 0}
```
The contest correctly re-ran independent consensus (re-fetching the URL, re-prompting) and dismissed the appeal — validators did not simply defer to the contester's argument, and the reputation counter updated accordingly.

## Summary

| Behavior tested | Verified on-chain? |
|---|---|
| Web-fetch-based consensus (`gl.nondet.web.render`) | done |
| Structured `(status, unmet_criteria)` consensus via `prompt_comparative` | done |
| Revision lifecycle (needs_revision → fix → accepted) | done |
| Duplicate-independent evaluation on rejection | done |
| Contest/dispute produces a fresh, independent consensus round | done |
| Contest correctly dismissed when argument doesn't hold up | done |
| Reputation counters update on contest outcome | done |
| Leader rotation under validator disagreement observed live | done |

## Known limitations observed

- One Studio RPC call (`gen_getContractSchemaForCode`) intermittently returned an `invalid_contract absent_runner_comment` error mid-session; this did not affect any actual contract transaction, all of which finalized successfully. Appears to be a Studio schema-cache refresh quirk rather than a contract issue.
- As with the companion ContentModerationRegistry contract, individual validators can occasionally time out on LLM calls under Studio's simulated multi-validator load; consensus still finalizes once quorum is met.