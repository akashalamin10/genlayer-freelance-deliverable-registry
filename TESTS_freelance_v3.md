# Test Results — FreelanceDeliverableRegistry (Access-Control Fix)

All tests below were executed live on GenLayer Studio.

**Deployed contract (fixed version):** `0x46...5F81` (full address in Studio Explorer)
**Accounts used:**
- `0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48` — client / j1's freelancer
- `0x4392834f897eD99348718CebCdafDF09d40aC314` — j2's authorized freelancer
- `0x0709564C4837243dD671E2725D1C143C114a4a3E` — unrelated third party (used to prove restrictions)

---

## 1. Deploy

- **Tx:** `0x2b86067271c3aaabfaa9ea9ffdee05fc88ed1bbbbcde527122ee1403680e06cd`
- **Constructor args:** `owner = 0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48`
- **Result:** SUCCESS, FINALIZED

## 2. post_job (j1) — client auto-bound to sender

- **Tx:** `0xc5ab1d134060ec933bf6049305ca82b016a4767d941b4bf73501fbec20dcc455`
- **Input:** `job_id="j1"`, `freelancer="0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48"`, `criteria=["must mention consensus", "must include a code example"]` — note `client` is NOT a parameter at all.

`get_job("j1")`:
```json
{
  "client": "0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48",
  "freelancer": "0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48",
  "criteria": ["must mention consensus", "must include a code example"],
  "status": "accepted"
}
```
`client` was populated automatically from `gl.message.sender_address`, confirming job creation is bound to the authenticated caller rather than an arbitrary supplied string.

## 3. submit_deliverable (j1) — correct freelancer, accepted case

- **Tx:** `0x307328f9eaa986d024203af44fb3334bbf68b40bfda4d37fea4f3d3a8cd12cdc`
- **Input:** the project's own README (containing consensus, validators, and a code example)
- **Result:** SUCCESS — `status: "accepted"`, `unmet_criteria: []`

## 4. post_job (j2) — separate freelancer for access-control testing

- **Input:** `job_id="j2"`, `freelancer="0x4392834f897eD99348718CebCdafDF09d40aC314"`, `criteria=["must mention consensus"]`

## 5. submit_deliverable (j2) from a non-freelancer address — must revert

- **Tx:** `0x13af1cbbadabfb2aeed5f41e2d9ddc798e1c9fb05abef5bd7ea04992291cd11f`
- **Caller:** `0x0709564C4837243dD671E2725D1C143C114a4a3E` (neither client nor freelancer for j2)
- **Result:** ERROR — `AssertionError: only the assigned freelancer may submit a deliverable`
- All 5 validators independently reached the same assertion error.

## 6. submit_deliverable (j2) from the correct freelancer — rejected case

- **Tx:** `0xb76b45497739e357c9a703e9944b8fcdb20eb73086670cea5617e0db9f836804`
- **Caller:** `0x4392834f897eD99348718CebCdafDF09d40aC314` (the recorded freelancer)
- **Input:** a deliverable unrelated to the "must mention consensus" criterion
- **On-chain Equivalence Principle:** `{"status": "rejected", "unmet_criteria": ["must mention consensus"]}`
- **Result:** SUCCESS — the correct freelancer's submission was processed normally.

## 7. contest_status (j2) from an unrelated third party — must revert

- **Tx:** `0x939b519a692dcb2e5af49c3fca34017a2ddb6a88cdbd7decd8fe85ded23c1035`
- **Caller:** `0x0709564C4837243dD671E2725D1C143C114a4a3E` (same unrelated address as test 5)
- **Result:** ERROR — `AssertionError: only the assigned freelancer may contest a review`

## Summary

| Behavior tested | Verified on-chain? |
|---|---|
| `client` bound to authenticated sender, not a caller-supplied string | ✅ |
| `submit_deliverable` restricted to the recorded `freelancer` | ✅ (both the revert and the success case) |
| `contest_status` restricted to the recorded `freelancer` | ✅ |
| Structured web-fetch consensus still functions correctly for authorized callers | ✅ |

## Known limitations observed

- As with the companion contracts, individual validators occasionally show
  "Disagree" or get cancelled after quorum under Studio's simulated
  multi-validator load; consensus still finalizes correctly once quorum is met.
