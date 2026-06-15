"""Tests for mce.backbone — governance wrapper over Mem0.

mem0 is NOT installed here. We never call Backbone.from_config (the only path
that imports mem0). Instead we inject a FakeMemory that records .add() calls and
returns canned .search() results.
"""
import pytest

from mce.backbone import Backbone, Scope, PrivacyError


# --------------------------------------------------------------------------- #
# Fake Memory: stands in for a vendored mem0.Memory instance.
# --------------------------------------------------------------------------- #
class FakeMemory:
    def __init__(self, search_return=None):
        self.add_calls = []       # list of (text, user_id, metadata)
        self.search_calls = []    # list of (query, user_id, limit)
        self._search_return = search_return if search_return is not None else []

    def add(self, text, user_id=None, metadata=None):
        self.add_calls.append({"text": text, "user_id": user_id, "metadata": metadata})
        return {"status": "ok"}

    def search(self, query, user_id=None, limit=None):
        self.search_calls.append({"query": query, "user_id": user_id, "limit": limit})
        return self._search_return


class FakeMemoryV3:
    def __init__(self, search_return=None):
        self.search_calls = []
        self.add_calls = []
        self._search_return = search_return if search_return is not None else []

    def add(self, text, user_id=None, metadata=None):
        self.add_calls.append({"text": text, "user_id": user_id, "metadata": metadata})
        return {"status": "ok"}

    def search(self, query, *, filters=None, top_k=None):
        self.search_calls.append({"query": query, "filters": filters, "top_k": top_k})
        return self._search_return


def make_bb(search_return=None):
    mem = FakeMemory(search_return=search_return)
    return Backbone(mem), mem


# --------------------------------------------------------------------------- #
# 1. Privacy gate — secrets MUST raise PrivacyError
# --------------------------------------------------------------------------- #
SECRET_STRINGS = [
    pytest.param("sk-abcdefghijklmnop1234", id="openai-sk-key"),
    pytest.param(
        # Long sk- style token (kept synthetic so it is not a real/detectable
        # provider key shape); still matches the privacy gate's sk-[\w-]{16,}.
        "sk-" + "exampleEXAMPLE0123456789" * 2,
        id="openai-sk-long",
    ),
    pytest.param("here is my key sk-ABCD1234efgh5678ijkl in prod", id="openai-sk-inline"),
    pytest.param("AKIAIOSFODNN7EXAMPLE", id="aws-akia-key"),
    pytest.param(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----",
        id="pem-private-key",
    ),
    pytest.param("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----", id="pem-bare"),
    pytest.param("password: hunter2", id="password-colon"),
    pytest.param("password=hunter2", id="password-equals"),
    pytest.param("api_key=abcdef0123456789", id="api-key-underscore"),
    pytest.param("api-key: deadbeefcafef00d", id="api-key-dash-colon"),
    pytest.param("apikey=zzz999", id="apikey-nodelim"),
    pytest.param(
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123", id="bearer-token"
    ),
]


@pytest.mark.parametrize("text", SECRET_STRINGS)
def test_capture_blocks_secrets(text):
    bb, mem = make_bb()
    with pytest.raises(PrivacyError):
        bb.capture(text, scope=Scope(org="acme"))
    # A blocked write must never reach the backing store.
    assert mem.add_calls == []


def test_capture_accepts_clean_text_and_writes_once():
    bb, mem = make_bb()
    bb.capture("fallback after health-check failure", scope=Scope(org="acme"))
    assert len(mem.add_calls) == 1
    assert mem.add_calls[0]["text"] == "fallback after health-check failure"


def test_clean_text_with_innocuous_words_not_blocked():
    # words that resemble but aren't secrets should pass
    bb, mem = make_bb()
    bb.capture("the password policy requires rotation", scope=Scope(org="acme"))
    # "password policy" has no :/= delimiter+value, so not a secret
    assert len(mem.add_calls) == 1


def test_hyphenated_engineering_text_not_misclassified():
    # Guard against the sk-proj- widening introducing a false positive: hyphen-
    # rich prose like "disk-space-monitoring" contains an "sk-..." substring but
    # is NOT a secret and must still be captured.
    bb, mem = make_bb()
    bb.capture("disk-space-monitoring-tool-v2 ran the task-list-runner", scope=Scope(org="acme"))
    assert len(mem.add_calls) == 1


# --------------------------------------------------------------------------- #
# 2. Scope metadata on capture
# --------------------------------------------------------------------------- #
def test_capture_metadata_includes_nonempty_scope_fields():
    bb, mem = make_bb()
    bb.capture(
        "routing note",
        scope=Scope(org="acme", app="router", user="alice", run="r1"),
        ticket="JIRA-7",
    )
    meta = mem.add_calls[0]["metadata"]
    assert meta["org"] == "acme"
    assert meta["app"] == "router"
    assert meta["user"] == "alice"
    assert meta["run"] == "r1"
    # extra **metadata kwargs flow through
    assert meta["ticket"] == "JIRA-7"


def test_capture_omits_empty_scope_fields():
    bb, mem = make_bb()
    bb.capture("note", scope=Scope(org="acme"))  # app/user/run all ""
    meta = mem.add_calls[0]["metadata"]
    assert meta == {"org": "acme"}
    assert "app" not in meta and "user" not in meta and "run" not in meta


def test_capture_user_id_falls_back_to_org_when_user_empty():
    bb, mem = make_bb()
    bb.capture("note", scope=Scope(org="acme"))
    assert mem.add_calls[0]["user_id"] == "acme"


def test_capture_user_id_uses_user_when_present():
    bb, mem = make_bb()
    bb.capture("note", scope=Scope(org="acme", user="bob"))
    assert mem.add_calls[0]["user_id"] == "bob"


# --------------------------------------------------------------------------- #
# 3. Tenant isolation on recall
# --------------------------------------------------------------------------- #
def _rec(memory_text, org=None, mem_len=8):
    rec = {"memory": memory_text}
    if org is not None:
        rec["metadata"] = {"org": org}
    return rec


def test_recall_filters_foreign_org_records():
    records = [
        _rec("acme record 1", org="acme"),
        _rec("evil corp leak", org="evilcorp"),
        _rec("acme record 2", org="acme"),
        _rec("globex secret", org="globex"),
    ]
    bb, mem = make_bb(search_return=records)
    out = bb.recall("q", scope=Scope(org="acme"), top_k=10, max_tokens=10000)
    texts = [r["memory"] for r in out]
    assert "acme record 1" in texts
    assert "acme record 2" in texts
    # ZERO foreign-org records
    assert "evil corp leak" not in texts
    assert "globex secret" not in texts
    assert all(r["metadata"]["org"] == "acme" for r in out)


def test_recall_treats_missing_org_metadata_as_same_org():
    # Documented behavior in _same_org: meta.get("org", org) == org, so a record
    # with no metadata.org defaults to the caller's org and is kept.
    records = [
        _rec("no-meta record", org=None),          # no metadata at all
        {"memory": "empty-meta", "metadata": {}},   # metadata present, no org key
        _rec("acme record", org="acme"),
        _rec("foreign", org="other"),
    ]
    bb, mem = make_bb(search_return=records)
    out = bb.recall("q", scope=Scope(org="acme"), top_k=10, max_tokens=10000)
    texts = [r.get("memory") for r in out]
    assert "no-meta record" in texts
    assert "empty-meta" in texts
    assert "acme record" in texts
    assert "foreign" not in texts


# --------------------------------------------------------------------------- #
# 4. Token budget + top_k pass-through, both return shapes
# --------------------------------------------------------------------------- #
def test_recall_passes_top_k_as_limit_to_search():
    bb, mem = make_bb(search_return=[])
    bb.recall("q", scope=Scope(org="acme"), top_k=7)
    assert mem.search_calls[0]["limit"] == 7


def test_recall_user_id_falls_back_to_org():
    bb, mem = make_bb(search_return=[])
    bb.recall("q", scope=Scope(org="acme"))
    assert mem.search_calls[0]["user_id"] == "acme"


def test_recall_prefers_mem0_v3_filters_when_supported():
    mem = FakeMemoryV3(search_return=[])
    bb = Backbone(mem)
    bb.recall("q", scope=Scope(org="acme", user="alice"), top_k=7)

    assert mem.search_calls == [{"query": "q", "filters": {"user_id": "alice"}, "top_k": 7}]


def test_recall_accepts_dict_results_shape():
    # mem0 can return {"results": [...]}
    records = [_rec("acme a", org="acme"), _rec("acme b", org="acme")]
    bb, mem = make_bb(search_return={"results": records})
    out = bb.recall("q", scope=Scope(org="acme"), top_k=10, max_tokens=10000)
    assert [r["memory"] for r in out] == ["acme a", "acme b"]


def test_recall_accepts_bare_list_shape():
    records = [_rec("acme a", org="acme"), _rec("acme b", org="acme")]
    bb, mem = make_bb(search_return=records)
    out = bb.recall("q", scope=Scope(org="acme"), top_k=10, max_tokens=10000)
    assert [r["memory"] for r in out] == ["acme a", "acme b"]


def test_recall_token_budget_stops_early():
    # Each record ~ 400 chars => ~101 tokens. A budget of 250 fits only 2.
    big = "x" * 400
    records = [
        {"memory": big, "metadata": {"org": "acme"}} for _ in range(10)
    ]
    bb, mem = make_bb(search_return=records)
    out = bb.recall("q", scope=Scope(org="acme"), top_k=10, max_tokens=250)
    # cost per record = 400//4 + 1 = 101; 2*101=202 ok, 3*101=303 > 250
    assert len(out) == 2


def test_recall_generous_budget_returns_all_topk():
    records = [
        {"memory": "y" * 100, "metadata": {"org": "acme"}} for _ in range(5)
    ]
    bb, mem = make_bb(search_return=records)
    out = bb.recall("q", scope=Scope(org="acme"), top_k=5, max_tokens=100000)
    assert len(out) == 5


def test_recall_dict_shape_with_foreign_org_filtered():
    records = [
        _rec("keep", org="acme"),
        _rec("drop", org="rival"),
    ]
    bb, mem = make_bb(search_return={"results": records})
    out = bb.recall("q", scope=Scope(org="acme"), top_k=10, max_tokens=10000)
    assert [r["memory"] for r in out] == ["keep"]


# --------------------------------------------------------------------------- #
# 5. Scope dataclass contract
# --------------------------------------------------------------------------- #
def test_scope_requires_org():
    with pytest.raises(TypeError):
        Scope()  # org is required positional/keyword


def test_scope_defaults_optional_fields_to_empty():
    s = Scope(org="acme")
    assert s.org == "acme"
    assert s.app == "" and s.user == "" and s.run == ""


def test_scope_is_frozen():
    s = Scope(org="acme")
    with pytest.raises(Exception):  # FrozenInstanceError (subclass of Exception)
        s.org = "other"  # type: ignore[misc]
