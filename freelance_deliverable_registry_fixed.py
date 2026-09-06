# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import time


STATUSES = ("accepted", "needs_revision", "rejected")


class FreelanceDeliverableRegistry(gl.Contract):
    owner: str
    jobs: TreeMap[str, str]
    submissions: TreeMap[str, str]
    disputes: TreeMap[str, str]
    reputation: TreeMap[str, str]

    def __init__(self, owner: str):
        self.owner = owner
        self.jobs = TreeMap()
        self.submissions = TreeMap()
        self.disputes = TreeMap()
        self.reputation = TreeMap()

    def _now(self) -> int:
        return int(time.time())

    def _sender(self) -> str:
        return str(gl.message.sender_address)

    def _criteria_block(self, criteria: list) -> str:
        return "\n".join(f"- {c}" for c in criteria)

    def _normalize_verdict(self, parsed: dict, criteria: list) -> dict:
        status = str(parsed.get("status", "")).strip().lower()
        if status not in STATUSES:
            status = "needs_revision"
        unmet = parsed.get("unmet_criteria", [])
        if not isinstance(unmet, list):
            unmet = []
        unmet = [str(u) for u in unmet]
        if status == "accepted":
            unmet = []
        return {"status": status, "unmet_criteria": unmet}

    def _evaluation_prompt(self, deliverable_text: str, criteria: list, extra: str = "") -> str:
        return f"""
You are reviewing a freelance deliverable against acceptance criteria.
Return ONLY JSON with exactly these keys:
{{"status":"accepted","unmet_criteria":[],"summary":"short reason"}}

status must be one of: accepted, needs_revision, rejected
unmet_criteria must list exact criteria text that was not satisfied
accepted = all criteria satisfied
needs_revision = close but some criteria unmet, fixable
rejected = deliverable is fundamentally off-target

ACCEPTANCE CRITERIA:
{self._criteria_block(criteria)}

{extra}

DELIVERABLE CONTENT:
\"\"\"{deliverable_text}\"\"\"
""".strip()

    def _agree_verdict(self, prompt: str, criteria: list) -> dict:
        def get_verdict() -> str:
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            normalized = self._normalize_verdict(raw, criteria)
            return json.dumps(normalized, sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "status must be exactly the same. "
                "unmet_criteria may differ in wording only if they refer to the "
                "same underlying unmet criterion; the set of unmet criteria "
                "referenced must match."
            ),
        )
        return json.loads(agreed_raw)

    @gl.public.write
    def post_job(self, job_id: str, freelancer: str, criteria: DynArray[str]) -> None:
        assert job_id not in self.jobs, "job already exists"
        client = self._sender()
        record = {
            "client": client,
            "freelancer": freelancer,
            "criteria": list(criteria),
            "status": "open",
            "revision_count": 0,
            "created_at": self._now(),
        }
        self.jobs[job_id] = json.dumps(record)

    @gl.public.view
    def get_job(self, job_id: str) -> dict:
        assert job_id in self.jobs, "no such job"
        return json.loads(self.jobs[job_id])

    @gl.public.view
    def debug_has_job(self, job_id: str) -> bool:
        return job_id in self.jobs

    @gl.public.write
    def submit_deliverable(self, job_id: str, deliverable_url: str) -> None:
        assert job_id in self.jobs, "no such job"
        job = json.loads(self.jobs[job_id])
        caller = self._sender()
        assert caller == job["freelancer"], "only the assigned freelancer may submit a deliverable"
        assert job["status"] in ("open", "needs_revision"), "job not accepting submissions"
        criteria = job["criteria"]

        def get_verdict() -> str:
            page_text = gl.nondet.web.render(deliverable_url, mode="text")
            prompt = self._evaluation_prompt(page_text, criteria)
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(self._normalize_verdict(raw, criteria), sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "status must be exactly the same. "
                "unmet_criteria may differ in wording only if they refer to the "
                "same underlying unmet criterion; the set of unmet criteria "
                "referenced must match."
            ),
        )
        agreed = json.loads(agreed_raw)

        submission_record = {
            "job_id": job_id,
            "deliverable_url": deliverable_url,
            "status": agreed["status"],
            "unmet_criteria": agreed["unmet_criteria"],
            "revision_number": job["revision_count"],
            "timestamp": self._now(),
        }
        self.submissions[f"{job_id}:{job['revision_count']}"] = json.dumps(submission_record)

        job["status"] = agreed["status"]
        if agreed["status"] == "needs_revision":
            job["revision_count"] += 1
        self.jobs[job_id] = json.dumps(job)

    @gl.public.view
    def get_submission(self, job_id: str, revision_number: int) -> dict:
        key = f"{job_id}:{revision_number}"
        assert key in self.submissions, "no such submission"
        return json.loads(self.submissions[key])

    def _get_reputation(self, address: str) -> dict:
        if address in self.reputation:
            return json.loads(self.reputation[address])
        return {"upheld": 0, "overturned": 0}

    @gl.public.view
    def get_reputation(self, address: str) -> dict:
        return self._get_reputation(address)

    @gl.public.write
    def contest_status(self, job_id: str, contester_argument: str) -> None:
        assert job_id in self.jobs, "no such job"
        job = json.loads(self.jobs[job_id])
        caller = self._sender()
        assert caller == job["freelancer"], "only the assigned freelancer may contest a review"
        assert job["status"] in ("needs_revision", "rejected"), "nothing to contest"
        current_revision = job["revision_count"]
        sub_key = f"{job_id}:{current_revision - 1}" if job["status"] == "needs_revision" \
            else f"{job_id}:{current_revision}"
        assert sub_key in self.submissions, "no submission to contest"
        prior = json.loads(self.submissions[sub_key])
        criteria = job["criteria"]

        extra = (
            f"A prior review reached status '{prior['status']}' citing unmet criteria: "
            f"{prior['unmet_criteria']}. The freelancer disputes this and argues:\n"
            f"{contester_argument}\nRe-evaluate independently; you are not bound by the prior status."
        )

        def get_verdict() -> str:
            page_text = gl.nondet.web.render(prior["deliverable_url"], mode="text")
            prompt = self._evaluation_prompt(page_text, criteria, extra)
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(self._normalize_verdict(raw, criteria), sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "status must be exactly the same. "
                "unmet_criteria may differ in wording only if they refer to the "
                "same underlying unmet criterion; the set of unmet criteria "
                "referenced must match."
            ),
        )
        agreed = json.loads(agreed_raw)
        overturned = agreed["status"] != prior["status"]

        rep = self._get_reputation(caller)
        if overturned:
            rep["overturned"] += 1
        else:
            rep["upheld"] += 1
        self.reputation[caller] = json.dumps(rep)

        job["status"] = agreed["status"]
        self.jobs[job_id] = json.dumps(job)

        self.disputes[job_id] = json.dumps({
            "contester": caller,
            "argument": contester_argument,
            "prior_status": prior["status"],
            "new_status": agreed["status"],
            "overturned": overturned,
            "resolved_at": self._now(),
        })

    @gl.public.view
    def get_dispute(self, job_id: str) -> dict:
        assert job_id in self.disputes, "no dispute recorded"
        return json.loads(self.disputes[job_id])
