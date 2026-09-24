"""Extension tests: E3-S5/S6/S7, E4-S5/S6, E5-S1/S7/S8, E6-S7/S8, E7-S5/S7/S8,
E8-S3/S4, E10-S2/S3/S4, E11 (web). Same rules: stdlib only, every positive has a reverse."""
import hashlib
import json
import os
import sys
import tempfile
import textwrap
import threading
import unittest
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llmwiki import auth, changesets, config as config_mod, grounding, sources as sources_mod  # noqa: E402
from llmwiki.cli import main as cli_main  # noqa: E402
from llmwiki.pages import Page  # noqa: E402
from llmwiki.pipeline import Wiki, detect_lang  # noqa: E402
from llmwiki.store import GBrainStore, open_store  # noqa: E402

FAKE = ROOT / "tests" / "fakes" / "jiuwenswarm"
TODAY = date.today().isoformat()


def base_env(tmp: Path) -> dict:
    cfg = tmp / "cfg.toml"
    cfg.write_text(textwrap.dedent(f"""\
        runtime_dir = "{tmp}/runtime"
        [gbrain]
        backend = "files"
        files_dir = "{tmp}/runtime/wiki"
        [jiuwen]
        bin = "{FAKE}"
        data_dir = "{tmp}/runtime/jiuwen"
        timeout_s = 20
        [ask]
        url_domains = ["huaweicloud.com"]
        glossary_terms_file = "{tmp}/glossary.txt"
        [web]
        tokens_file = "{tmp}/tokens.json"
        """))
    return {"cfg": cfg, "env": {"LLMWIKI_CONFIG": str(cfg)}}


class ExtBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.parts = base_env(self.d)
        self.out = self.d / "answer.txt"
        self.prompt_log = self.d / "prompt.txt"
        os.environ.update(FAKE_OUT=str(self.out), FAKE_RC="0", FAKE_PROMPT_LOG=str(self.prompt_log))
        os.environ.pop("FAKE_NO_DISPATCH", None)
        self.cfg = config_mod.load(self.parts["cfg"])
        self.wiki = Wiki(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()
        for k in ("FAKE_OUT", "FAKE_RC", "FAKE_NO_DISPATCH", "FAKE_PROMPT_LOG", "FAKE_MAIN_TEXT"):
            os.environ.pop(k, None)

    def seed(self):
        self.wiki.store.put(Page(slug="services/obs", title="Object Storage Service (OBS)",
                                 type="service",
                                 compiled_truth="OBS offers Standard storage classes [S:aaaaaaaaaaaaaaaa]. "
                                                "A single object can be up to 48.8 TB [S:aaaaaaaaaaaaaaaa].",
                                 sources=["aaaaaaaaaaaaaaaa"], last_verified=TODAY,
                                 links=["regions/la-sao-paulo1"]))
        self.wiki.store.put(Page(slug="regions/la-sao-paulo1", title="LA-Sao Paulo1", type="region",
                                 compiled_truth="LA-Sao Paulo1 has 3 AZs [S:bbbbbbbbbbbbbbbb].",
                                 sources=["bbbbbbbbbbbbbbbb"], last_verified=TODAY))


class HeadingClaimTests(unittest.TestCase):
    docs = {"compliance/iso-27001": "ISO 27001 is an international information security "
                                    "management standard commonly required in LATAM tenders."}

    def test_title_heading_not_flagged_when_body_cites(self):
        r = grounding.verify(
            "## ISO 27001\nISO 27001 is an international information security management "
            "standard commonly required in LATAM public-sector tenders [W:compliance/iso-27001].",
            self.docs, cite_prefix="W", terms=["ISO 27001"])
        self.assertEqual(r.status, "grounded", r.issues)
        self.assertNotIn(grounding.REDACTION, r.redacted_text)

    def test_reverse_fabricated_number_in_heading_caught(self):
        r = grounding.verify(
            "## OBS limits: 99 TB\nOBS is a storage service [W:compliance/iso-27001].",
            self.docs, cite_prefix="W", terms=["OBS limits"])
        self.assertEqual(r.status, "partially_verified")
        self.assertIn("99", r.issues[0].claim)

    def test_heading_without_any_citation_still_no_citations(self):
        r = grounding.verify("## ISO 27001\nSome text.", self.docs, cite_prefix="W")
        self.assertEqual(r.status, "no_citations")


class GBrainFrontmatterTests(unittest.TestCase):
    def test_block_yaml_lists_roundtrip(self):
        text = """---
slug: services/obs
type: service
title: Object Storage Service (OBS)
links:
  - regions/la-sao-paulo1
  - pricing/obs
sources:
  - afd945968c0ca7b9
last_verified: '2026-09-24'
---

# Object Storage Service (OBS)

## Compiled truth
up to 48.8 TB [S:afd945968c0ca7b9]

## Timeline
- 2026-09-24 — seeded [S:afd945968c0ca7b9]
"""
        p = Page.from_markdown("services/obs", text)
        self.assertEqual(p.links, ["regions/la-sao-paulo1", "pricing/obs"])
        self.assertEqual(p.sources, ["afd945968c0ca7b9"])
        self.assertEqual(p.title, "Object Storage Service (OBS)")
        self.assertEqual(p.last_verified, "2026-09-24")
        self.assertIn("48.8 TB", p.compiled_truth)


class FoldedScalarTests(unittest.TestCase):
    def test_folded_title(self):
        text = """---
slug: compliance/lfpdppp
type: compliance
title: >-
  LFPDPPP (Ley Federal de Protección de Datos Personales en Posesión de los
  Particulares)
last_verified: '2026-09-24'
---

# x

## Compiled truth
law text [S:aaaaaaaaaaaaaaaa]

## Timeline
"""
        p = Page.from_markdown("compliance/lfpdppp", text)
        self.assertEqual(p.title, "LFPDPPP (Ley Federal de Protección de Datos Personales en Posesión de los Particulares)")


class TermSynonymTests(unittest.TestCase):
    def test_abbreviation_grounds_full_title(self):
        doc = "Status update: OBS is not available in LA-Santiago this week."
        ok = grounding.verify("Object Storage Service (OBS) is not available in LA-Santiago [W:x].",
                              {"x": doc}, cite_prefix="W",
                              terms=["Object Storage Service (OBS)", "LA-Santiago"],
                              term_synonyms={"Object Storage Service (OBS)":
                                             ["Object Storage Service (OBS)", "OBS"]})
        self.assertEqual(ok.status, "grounded", ok.issues)

    def test_reverse_unrelated_abbreviation_still_fails(self):
        doc = "EVS volumes are available in LA-Santiago."
        bad = grounding.verify("Object Storage Service (OBS) is available in LA-Santiago [W:x].",
                               {"x": doc}, cite_prefix="W",
                               terms=["Object Storage Service (OBS)", "LA-Santiago"],
                               term_synonyms={"Object Storage Service (OBS)":
                                              ["Object Storage Service (OBS)", "OBS"]})
        self.assertEqual(bad.status, "partially_verified")


class DreamReconcileTests(ExtBase):
    def _page(self, slug, title, truth, sources, verified):
        return Page(slug=slug, title=title, type=slug.split("/")[0],
                    compiled_truth=truth, sources=sources, last_verified=verified,
                    timeline=[])
    def _src(self, name, text):
        f = self.d / name
        f.write_text(text)
        return self.wiki.sources.add(str(f), kind="doc")["id"]

    def test_availability_conflict_newest_wins(self):
        old_sid = self._src("old.md", "Old region news 2026-01-01: EVS is available in LA-Santiago for all customers.")
        new_sid = self._src("new.md", "New region news 2026-09-01: EVS is not available in LA-Santiago currently.")
        svc = self._page("services/evs", "EVS", 
                         f"EVS is available in LA-Santiago [S:{old_sid}].", [old_sid], "2026-01-01")
        reg = self._page("regions/la-santiago", "LA-Santiago",
                         f"EVS is not available in LA-Santiago [S:{new_sid}].", [new_sid], "2026-09-01")
        self.wiki.store.put(svc); self.wiki.store.put(reg)
        self.wiki.invalidate_index()
        rep = self.wiki.lint()
        self.assertTrue(any("la-santiago" in c.lower() for c in rep["contradictions"]), rep["contradictions"])

        rec = self.wiki.dream_reconcile()
        self.assertEqual(rec["conflicts"], 1, rec)
        self.assertEqual(len(rec["resolved"]), 1, rec)
        loser = self.wiki.store.get("services/evs")
        self.assertIn("not available in LA-Santiago", loser.compiled_truth)
        self.assertNotIn("] is available in LA-Santiago [", loser.compiled_truth)
        rep2 = self.wiki.lint()
        self.assertFalse(any("la-santiago" in c.lower() for c in rep2["contradictions"]), rep2["contradictions"])

    def test_pricing_conflict_protected_stays_pending(self):
        old_sid = self._src("pold.md", "Old price 2026-01-01: OBS standard costs USD 0.05 per GB-month in LA-Santiago.")
        new_sid = self._src("pnew.md", "New price 2026-09-01: OBS standard costs USD 0.02 per GB-month in LA-Santiago.")
        reg = self._page("regions/la-santiago", "LA-Santiago", "region page", [], "2026-01-01")
        self.wiki.store.put(reg)   # term source for the price region group
        a = self._page("pricing/obs-a", "OBS pricing A",
                       f"OBS standard costs USD 0.05 per GB-month in LA-Santiago [S:{old_sid}].", [old_sid], "2026-01-01")
        b = self._page("pricing/obs-b", "OBS pricing B",
                       f"OBS standard costs USD 0.02 per GB-month in LA-Santiago [S:{new_sid}].", [new_sid], "2026-09-01")
        self.wiki.store.put(a); self.wiki.store.put(b)
        self.wiki.invalidate_index()
        rec = self.wiki.dream_reconcile()
        self.assertEqual(len(rec["pending"]), 1, rec)      # pricing = protected -> human queue
        self.assertEqual(rec["resolved"], [], rec)
        cs_id = rec["pending"][0]["changeset"]
        cs = self.wiki.changes.get(cs_id)
        self.assertEqual(cs["status"], "pending")
        self.assertEqual(cs["protected"], ["pricing"])


class MCPClientTests(unittest.TestCase):
    """AG-M2: fake MCP server replaying the probed gbrain shapes."""

    def _env(self, **extra):
        env = dict(os.environ)
        env["PATH"] = f"{ROOT}/tests/fakes:" + env.get("PATH", "")
        env.update(extra)
        return env

    def test_handshake_search_get_put_list(self):
        from llmwiki.gbrain_client import GBrainMCP
        c = GBrainMCP(str(ROOT / "tests" / "fakes" / "gbrain_mcp_serve"), timeout_s=10)
        try:
            self.assertEqual(c.search("object storage", 5), ["services/obs"])
            page = c.get_page("services/obs")
            self.assertEqual(page["title"], "Object Storage Service (OBS)")
            self.assertIn("48.8 TB", page["compiled_truth"])
            self.assertEqual(c.list_pages()[1]["slug"], "regions/la-sao-paulo1")
            self.assertEqual(c.put_page("services/obs", "# x")["ok"], True)
        finally:
            c.close()

    def test_respawn_after_death(self):
        from llmwiki.gbrain_client import GBrainMCP
        env = self._env(FAKE_MCP_DIE_AFTER="0.6")
        c = GBrainMCP(str(ROOT / "tests" / "fakes" / "gbrain_mcp_serve"),
                      env={"FAKE_MCP_DIE_AFTER": "0.6"}, timeout_s=10)
        try:
            self.assertEqual(c.search("obs", 5), ["services/obs"])   # child alive
            time.sleep(0.8)                                          # child exits
            self.assertEqual(c.search("obs", 5), ["services/obs"])   # respawned transparently
        finally:
            c.close()


class MCPStoreTests(ExtBase):
    def test_store_over_mcp(self):
        self.parts["cfg"].write_text((self.parts["cfg"]).read_text().replace(
            'backend = "files"', f'backend = "gbrain-mcp"\nbin = "{ROOT}/tests/fakes/gbrain_mcp_serve"').replace(
            f'files_dir = "{self.d}/runtime/wiki"', f'files_dir = "{self.d}/mirror"'))
        os.environ["PATH"] = f"{ROOT}/tests/fakes:" + os.environ.get("PATH", "")
        cfg = config_mod.load(self.parts["cfg"])
        st = open_store(cfg)
        # search via MCP
        self.assertEqual(st.search("object storage", 5), ["services/obs"])
        # brain-only page (not in mirror) still readable via MCP get_page (E4-S5)
        p = st.get("services/obs")
        self.assertIsNotNone(p)
        self.assertEqual(p.title, "Object Storage Service (OBS)")
        # put mirrors locally and the mirror read path wins afterwards
        st.put(Page(slug="regions/la-sao-paulo1", title="LA-Sao Paulo1", type="region",
                    compiled_truth="3 AZs [S:bbbbbbbbbbbbbbbb]"))
        self.assertEqual(st.mirror.get("regions/la-sao-paulo1").title, "LA-Sao Paulo1")
        # slugs = mirror ∪ MCP list
        self.assertIn("services/obs", st.slugs())
        self.assertIn("regions/la-sao-paulo1", st.slugs())


# ---- E6-S8 unit-aware matching ------------------------------------------------
class UnitAwareTests(ExtBase):
    docs = {"services/obs": "A single object can be up to 48.8 TB. IOPS limit is 20000."}

    def test_reverse_unit_mismatch_caught(self):
        r = grounding.verify("A single object can be up to 48.8 GB [W:services/obs].",
                             self.docs, cite_prefix="W")
        self.assertEqual(r.status, "partially_verified", r.issues)
        self.assertIn("48.8", r.issues[0].claim)

    def test_unit_match_passes(self):
        r = grounding.verify("A single object can be up to 48.8 TB [W:services/obs].",
                             self.docs, cite_prefix="W")
        self.assertEqual(r.status, "grounded", r.issues)

    def test_bare_number_still_matches(self):
        r = grounding.verify("The IOPS limit is 20000 [W:services/obs].", self.docs, cite_prefix="W")
        self.assertEqual(r.status, "grounded")

    def test_currency_fold(self):
        docs = {"pricing/obs": "Standard storage costs USD 0.0235 per GB-month in LA-Sao Paulo1."}
        ok = grounding.verify("It costs USD 0.0235 per GB-month [W:pricing/obs].", docs, cite_prefix="W")
        bad = grounding.verify("It costs USD 0.0235 per TB-month [W:pricing/obs].", docs, cite_prefix="W")
        self.assertEqual(ok.status, "grounded")
        self.assertEqual(bad.status, "partially_verified")


# ---- E6-S7 dates, word numbers, service terms ----------------------------------
class NewClaimTypesTests(ExtBase):
    def test_date_grounded_and_reverse(self):
        docs = {"services/obs": "Deep Archive launched on 2026-09-20 for all regions."}
        ok = grounding.verify("Deep Archive launched on 2026-09-20 [W:services/obs].", docs, cite_prefix="W")
        bad = grounding.verify("Deep Archive launched on 2026-09-21 [W:services/obs].", docs, cite_prefix="W")
        self.assertEqual(ok.status, "grounded")
        self.assertEqual(bad.status, "partially_verified")

    def test_word_number(self):
        docs = {"regions/x": "LA-Sao Paulo1 has 3 AZs."}
        ok = grounding.verify("LA-Sao Paulo1 has three AZs [W:regions/x].", docs, cite_prefix="W",
                              terms=["LA-Sao Paulo1"])
        bad = grounding.verify("LA-Sao Paulo1 has two AZs [W:regions/x].", docs, cite_prefix="W",
                               terms=["LA-Sao Paulo1"])
        self.assertEqual(ok.status, "grounded")
        self.assertEqual(bad.status, "partially_verified")

    def test_service_title_is_a_term(self):
        self.seed()
        self.assertIn("Object Storage Service (OBS)", self.wiki.terms())
        # exact service name in a sentence citing the WRONG page must fail (GR-2 for terms)
        r = grounding.verify("Object Storage Service (OBS) is in LA-Sao Paulo1 [W:regions/la-sao-paulo1].",
                             {"regions/la-sao-paulo1": "LA-Sao Paulo1 has 3 AZs."},
                             cite_prefix="W", terms=self.wiki.terms())
        self.assertEqual([i.claim for i in r.issues], ["Object Storage Service (OBS)"])

    def test_glossary_terms_loaded(self):
        (self.d / "glossary.txt").write_text("GaussDB\nEVS\n# comment\n")
        self.seed()
        terms = self.wiki.terms()
        self.assertIn("GaussDB", terms)
        self.assertIn("EVS", terms)
        self.assertNotIn("# comment", terms)


# ---- E5-S1 language detection ---------------------------------------------------
class DetectLangTests(unittest.TestCase):
    def test_short_es(self):
        self.assertEqual(detect_lang("¿cómo migrar CCE a otro region?"), "es")

    def test_short_pt(self):
        self.assertEqual(detect_lang("qual o preço do OBS?"), "pt-BR")
        self.assertEqual(detect_lang("como criar um bucket"), "pt-BR")

    def test_en(self):
        self.assertEqual(detect_lang("how do I set up CCE with ELB"), "en")


# ---- E5-S7 retrieval failure -------------------------------------------------
class RetrievalFailureTests(ExtBase):
    def test_retrieval_failed_without_model_call(self):
        self.seed()
        (self.d / "gb.toml").write_text(textwrap.dedent(f"""\
            runtime_dir = "{self.d}/runtime"
            [gbrain]
            backend = "gbrain"
            bin = "/nonexistent-gbrain-xyz"
            files_dir = "{self.d}/runtime/wiki"
            [jiuwen]
            bin = "{FAKE}"
            data_dir = "{self.d}/runtime/jiuwen"
            """))
        wiki = Wiki(config_mod.load(self.d / "gb.toml"))
        r = wiki.ask("OBS max object size")
        self.assertEqual(r.status, "error")
        self.assertIn("retrieval_failed", r.error)
        self.assertFalse(self.prompt_log.exists())     # no model call happened


# ---- E4-S6 term index cache -----------------------------------------------------
class TermsCacheTests(ExtBase):
    def test_terms_built_once_then_cached(self):
        self.seed()
        calls = {"n": 0}
        orig_get = self.wiki.store.get

        def counting(slug):
            if slug == "regions/la-sao-paulo1":        # only read by the terms index, never retrieved
                calls["n"] += 1
            return orig_get(slug)

        self.wiki.store.get = counting
        self.wiki.terms()
        first = calls["n"]
        self.wiki.terms()
        self.assertEqual(calls["n"], first)            # cached: no re-read
        self.out.write_text("A single object can be up to 48.8 TB [W:services/obs].")
        self.wiki.ask("OBS max object size")
        self.wiki.ask("OBS object size again")
        self.assertEqual(calls["n"], first)            # E4-S6: asks add zero term reads


# ---- E4-S5 gbrain slugs union ----------------------------------------------------
class GBrainSlugsTests(ExtBase):
    def test_slugs_union_and_search_parse(self):
        store_dir = self.d / "gb"
        store_dir.mkdir()
        fake = self.d / "fake-gbrain"
        fake.write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            "  list) printf 'services/obs\\tservice\\t2026-09-24\\tOBS\\n"
            "availability/only-in-brain\\tavailability\\t2026-09-24\\tX\\n' ;;\n"
            "  query) printf '[0.9900] services/obs -- A single object can be up to 48.8 TB.\\n' ;;\n"
            '  get) if [ "$2" = "services/obs" ]; then printf -- "---\\ntitle: OBS\\n---\\n\\nx [S:aaaaaaaaaaaaaaaa]\\n"; '
            'else echo "not found" >&2; exit 1; fi ;;\n'
            "  put) cat > /dev/null ;;\n"
            "esac\n")
        fake.chmod(0o755)
        (self.parts["cfg"]).write_text((self.parts["cfg"]).read_text().replace(
            'backend = "files"', f'backend = "gbrain"\nbin = "{fake}"').replace(
            f'files_dir = "{self.d}/runtime/wiki"', f'files_dir = "{store_dir}"')
            + f'\n[gbrain.env]\nGBRAIN_HOME = "{self.d}/gbrain-home"\n')
        cfg = config_mod.load(self.parts["cfg"])
        gs = GBrainStore(cfg)
        p = Page(slug="services/obs", title="OBS", compiled_truth="x [S:aaaaaaaaaaaaaaaa]",
                 sources=["aaaaaaaaaaaaaaaa"])
        gs.put(p)
        self.assertIn("services/obs", gs.slugs())
        self.assertIn("availability/only-in-brain", gs.slugs())      # E4-S5: not in the mirror
        self.assertEqual(gs.search("object", 3), ["services/obs"])
        got = gs.get("services/obs")
        self.assertEqual(got.slug, "services/obs")


# ---- E10-S2/S3/S4 security --------------------------------------------------------
class SecurityTests(ExtBase):
    def add_source(self, ref="note.md", licence="public", text="OBS is available in LA-Sao Paulo1 since 2026."):
        f = self.d / ref
        f.write_text(text)
        return self.wiki.sources.add(str(f), kind="doc", licence=licence)

    def test_confidential_filtered_before_retrieval(self):
        self.seed()
        meta = self.add_source(licence="confidential",
                               text="OBS confidential note: the special discount is 15 percent for LATAM partners.")
        self.wiki.store.put(Page(slug="concepts/private-note", title="Private note", type="concept",
                                 compiled_truth=f"Confidential: the OBS special discount is 15 percent [S:{meta['id']}].",
                                 sources=[meta["id"]], last_verified=TODAY))
        self.out.write_text("The OBS special discount is 15 percent [W:concepts/private-note].")
        self.wiki.invalidate_index()
        r_reader = self.wiki.ask("special discount", role="reader")
        self.assertEqual(r_reader.status, "abstained")            # never entered the pack
        self.assertEqual(r_reader.filtered_confidential, ["concepts/private-note"])
        self.assertNotIn("concepts/private-note", r_reader.retrieved)
        r_curator = self.wiki.ask("special discount", role="curator")
        self.assertEqual(r_curator.status, "grounded", r_curator.issues)
        self.assertIn("concepts/private-note", r_curator.citations)

    def test_audit_log_written(self):
        self.seed()
        meta = self.add_source()
        self.out.write_text(json.dumps({"pages": [
            {"slug": "faq/test", "title": "T", "type": "faq",
             "compiled_truth": f"OBS is available in LA-Sao Paulo1 [S:{meta['id']}].",
             "timeline": [{"date": TODAY, "text": f"filed [S:{meta['id']}]"}]}]}))
        cs = self.wiki.compile(meta["id"])
        self.wiki.approve(cs["id"], "curator-ana")
        audit = self.wiki.audit_log.read_text()
        self.assertIn('"action": "approve"', audit)
        self.assertIn("curator-ana", audit)
        self.assertIn('"action": "compile"', audit)

    def test_token_store_roles(self):
        ts = auth.open_tokens(self.cfg)
        tok = ts.create("curator", "ana", self.cfg)
        self.assertEqual(ts.role_for(tok), ("ana", "curator"))
        self.assertIsNone(ts.role_for("llmwiki_wrong"))
        self.assertTrue(auth.allowed("curator", "approve"))
        self.assertFalse(auth.allowed("contributor", "approve"))
        self.assertTrue(auth.allowed("reader", "ask"))
        self.assertFalse(auth.allowed("reader", "ingest"))
        self.assertTrue(ts.revoke(tok))
        self.assertIsNone(ts.role_for(tok))


# ---- E7-S7 auto-approve -----------------------------------------------------------
class AutoApproveTests(ExtBase):
    def test_timeline_only_auto_applied(self):
        self.seed()
        txt = self.parts["cfg"].read_text() + '\n[review]\nauto_approve_nonprotected = true\n'
        self.parts["cfg"].write_text(txt)
        self.cfg = config_mod.load(self.parts["cfg"])
        self.wiki = Wiki(self.cfg)
        self.wiki.store.put(Page(slug="services/obs", title="Object Storage Service (OBS)",
                                 type="service", compiled_truth="old truth",
                                 sources=["aaaaaaaaaaaaaaaa"], last_verified=TODAY))
        f = self.d / "n.md"
        f.write_text("OBS update 2026-09-24: a new timeline event happened.")
        meta = self.wiki.sources.add(str(f), kind="doc", licence="public")
        good = {"pages": [{"slug": "services/obs", "compiled_truth": "old truth",
                           "timeline": [{"date": TODAY, "text": f"timeline-only note [S:{meta['id']}]"}]}]}
        self.out.write_text(json.dumps(good))
        cs = self.wiki.compile(meta["id"])
        self.assertEqual(cs["status"], "applied", cs["problems"])    # policy applied it
        self.assertIn("auto-approve-policy", [h["actor"] for h in cs["history"]])

    def test_protected_never_auto_applied(self):
        self.seed()
        txt = self.parts["cfg"].read_text() + '\n[review]\nauto_approve_nonprotected = true\n'
        self.parts["cfg"].write_text(txt)
        self.wiki = Wiki(config_mod.load(self.parts["cfg"]))
        f = self.d / "p.md"
        f.write_text("Price update 2026-09-24: OBS standard storage costs USD 0.0235 per GB-month.")
        meta = self.wiki.sources.add(str(f), kind="price", licence="public")
        good = {"pages": [{"slug": "pricing/obs", "compiled_truth":
                           f"USD 0.0235 per GB-month [S:{meta['id']}]",
                           "timeline": [{"date": TODAY, "text": f"price [S:{meta['id']}]"}]}]}
        self.out.write_text(json.dumps(good))
        cs = self.wiki.compile(meta["id"])
        self.assertEqual(cs["status"], "pending")                    # protected: human needed


# ---- E7-S8 file-back ------------------------------------------------------------
class FileBackTests(ExtBase):
    def test_verified_answer_becomes_faq_changeset(self):
        self.seed()
        meta_src = self.wiki.sources.add(str(self.d / "obs.md") if (self.d / "obs.md").write_text(
            "OBS spec: a single object can be up to 48.8 TB.") or True else None, kind="doc")
        # re-point page sources at the real snapshot
        obs = self.wiki.store.get("services/obs")
        obs.sources = [meta_src["id"]]
        self.wiki.store.put(obs)
        self.out.write_text("A single object can be up to 48.8 TB [W:services/obs].")
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "grounded", r.issues)
        cs = self.wiki.fileback("What is the max OBS object size?")
        self.assertEqual(cs["status"], "pending", cs["problems"])
        self.assertTrue(cs["pages"][0]["slug"].startswith("faq/"))
        self.assertIn(f"[S:{meta_src['id']}]", cs["pages"][0]["compiled_truth"])
        self.wiki.approve(cs["id"], "curator-ana")
        self.assertIsNotNone(self.wiki.store.get(cs["pages"][0]["slug"]))


# ---- E8-S3 contradictions ---------------------------------------------------------
class ContradictionTests(ExtBase):
    def test_availability_contradiction_detected(self):
        for slug, title, truth in (
            ("regions/la-santiago", "LA-Santiago",
             "Object Storage Service (OBS) is available in LA-Santiago [S:aaaaaaaaaaaaaaaa]."),
            ("regions/la-sao-paulo1", "LA-Sao Paulo1",
             "Object Storage Service (OBS) is not available in LA-Santiago [S:aaaaaaaaaaaaaaaa]. "
             "LA-Sao Paulo1 has 3 AZs [S:aaaaaaaaaaaaaaaa]."),
            ("services/obs", "Object Storage Service (OBS)", "OBS stores objects."),
        ):
            self.wiki.store.put(Page(slug=slug, title=title, type="x",
                                     compiled_truth=truth, sources=["aaaaaaaaaaaaaaaa"],
                                     last_verified=TODAY))
        rep = self.wiki.lint()
        self.assertTrue(any("availability" in c and "la-santiago" in c.lower() for c in rep["contradictions"]),
                        rep["contradictions"])

    def test_consistent_pages_no_contradiction(self):
        self.seed()
        self.wiki.store.put(Page(slug="regions/la-santiago", title="LA-Santiago", type="region",
                                 compiled_truth="EVS is available in LA-Santiago [S:aaaaaaaaaaaaaaaa].",
                                 sources=["aaaaaaaaaaaaaaaa"], last_verified=TODAY))
        rep = self.wiki.lint()
        self.assertEqual(rep["contradictions"], [])


# ---- E8-S4 re-verification --------------------------------------------------------
class ReverifyTests(ExtBase):
    def test_changed_source_recompiles(self):
        self.seed()
        f = self.d / "live.md"
        f.write_text("OBS news 2026: the max object size is 48.8 TB today across all regions.")
        meta = self.wiki.sources.add(str(f), kind="doc")
        # page citing it, stale
        self.wiki.store.put(Page(slug="services/obs2", title="OBS 2", type="service",
                                 compiled_truth=f"max 48.8 TB [S:{meta['id']}].",
                                 sources=[meta["id"]],
                                 last_verified=(date.today() - timedelta(days=200)).isoformat()))
        # source metadata must point at an http ref for reverify to re-fetch
        mj = self.wiki.sources.root / f"{meta['id']}.json"
        m = json.loads(mj.read_text()); m["ref"] = "http://testserver/live.md"; mj.write_text(json.dumps(m))
        self.wiki.invalidate_index()
        # a compile output the role might produce for the re-verified source
        self.out.write_text(json.dumps({"pages": [
            {"slug": "services/obs2", "compiled_truth": f"max 300 TB [S:{meta['id']}]",
             "timeline": [{"date": TODAY, "text": f"re-verified [S:{meta['id']}]"}]}]}))
        # now change the content behind the URL
        f.write_text("OBS news: max object size is now 300 TB.")

        orig_read = sources_mod._read
        sources_mod._read = lambda ref: (f.read_text(), "md", f.read_text())
        try:
            rows = self.wiki.reverify()
        finally:
            sources_mod._read = orig_read
        self.assertTrue(rows, "reverify should have processed the stale page")
        self.assertTrue(any(r["action"] == "compiled" for r in rows), rows)


# ---- E3-S5/S6/S7 sources ------------------------------------------------------------
class SourcesExtTests(ExtBase):
    def test_lang_detected_and_parser_version(self):
        f = self.d / "es.md"
        f.write_text("El servicio OBS no está disponible en la región de Santiago todavía.")
        meta = self.wiki.sources.add(str(f))
        self.assertEqual(meta["lang"], "es")
        self.assertEqual(meta["parser_version"], sources_mod.PARSER_VERSION)

    def test_price_table_column_mismatch_rejected(self):
        f = self.d / "price.md"
        f.write_text("Price list:\n\n| item | price |\n|---|---|\n| obs | 0.02 |\n| evs | 0.03 | extra |\n")
        with self.assertRaises(sources_mod.SourceError):
            self.wiki.sources.add(str(f), kind="price")

    def test_html_cell_value_loss_rejected(self):
        raw = "<table><tr><td>item</td><td>price</td></tr><tr><td>obs</td><td>0.02</td></tr>" \
              "<tr><td>evs</td><td>0.03</td></tr></table>"
        text_missing = "item | price\nobs | 0.02\nevs |"          # 0.03 lost by the extractor
        with self.assertRaises(sources_mod.SourceError):
            sources_mod._table_self_check(text_missing, "x.html", raw, "html")
        sources_mod._table_self_check("item | price\nobs | 0.02\nevs | 0.03", "x.html", raw, "html")

    def test_pricing_staleness_uses_fetched_at(self):
        self.seed()
        f = self.d / "p.md"
        f.write_text("OBS standard storage price is USD 0.0235 per GB-month in LA-Sao Paulo1.")
        meta = self.wiki.sources.add(str(f), kind="price")
        mj = self.wiki.sources.root / f"{meta['id']}.json"
        m = json.loads(mj.read_text())
        m["fetched_at"] = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(timespec="seconds")
        mj.write_text(json.dumps(m))
        self.wiki.store.put(Page(slug="pricing/obs", title="OBS pricing", type="pricing",
                                 compiled_truth=f"USD 0.0235 per GB-month [S:{meta['id']}]",
                                 sources=[meta["id"]], last_verified=TODAY))
        self.wiki.invalidate_index()
        _, _, stale = self.wiki._evidence(["pricing/obs"])
        self.assertEqual(stale, ["pricing/obs"])          # fresh last_verified, old source


# ---- E5-S8 log retention --------------------------------------------------------------
class RetentionTests(ExtBase):
    def test_old_records_rotated(self):
        self.parts["cfg"].write_text(self.parts["cfg"].read_text().replace(
            "[ask]\n", "[ask]\nlog_retention_days = 30\n"))
        self.wiki = Wiki(config_mod.load(self.parts["cfg"]))
        self.wiki.log.parent.mkdir(parents=True, exist_ok=True)
        old = json.dumps({"question": "old", "at": "2020-01-01T00:00:00+00:00", "status": "abstained"})
        self.wiki.log.write_text(old + "\n")
        self.seed()
        self.out.write_text("A single object can be up to 48.8 TB [W:services/obs].")
        for i in range(127):
            self.wiki.ask(f"question {i}")                # 128th write triggers rotation
        self.assertNotIn('"old"', self.wiki.log.read_text())
        self.assertGreaterEqual(len(self.wiki.log.read_text().splitlines()), 127)


# ---- E7-S5 CLI level -----------------------------------------------------------------
class CliTests(ExtBase):
    def test_cli_ask_json_and_lint(self):
        self.seed()
        self.out.write_text("A single object can be up to 48.8 TB [W:services/obs].")
        os.environ["LLMWIKI_CONFIG"] = str(self.parts["cfg"])
        rc = cli_main(["ask", "What is the max OBS object size?", "--json"])
        self.assertEqual(rc, 0)
        rc = cli_main(["lint", "--json"])
        self.assertEqual(rc, 0)
        rc = cli_main(["review"])
        self.assertEqual(rc, 0)
        rc = cli_main(["doctor"])
        self.assertIn(rc, (0, 1))                          # no gateway in tests → 1 is honest


# ---- E11 web API ---------------------------------------------------------------------
class WebTests(ExtBase):
    @classmethod
    def setUpClass(cls):
        from llmwiki import web
        cls.web = web

    def _start_server(self):
        from http.server import ThreadingHTTPServer
        web = self.web
        web._cfg = self.cfg
        web._wiki = self.wiki
        web._tokens = auth.open_tokens(self.cfg)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd, port

    def _get(self, port, path, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers.get("Content-Type"), r.read().decode("utf-8")

    def _post(self, port, path, body, headers=None):
        data = json.dumps(body).encode()
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8")

    def test_no_citations_discards_provisional(self):
        """GL-A7 V2: an uncited answer streams provisionally but final replaces it
        with the NOT_IN_WIKI message (the only authoritative text)."""
        self.seed()
        self.out.write_text("OBS objects can be up to 48.8 TB.")   # uncited
        httpd, port = self._start_server()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/ask", method="POST",
                                         data=json.dumps({"question": "OBS object size"}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                stream = resp.read().decode("utf-8")
            self.assertIn("event: provisional", stream)
            self.assertIn("event: final", stream)
            final_line = [l for l in stream.splitlines() if l.startswith("data:")][-1]
            final = json.loads(final_line[5:])
            self.assertIn("NOT_IN_WIKI", final["answer"])
            self.assertNotIn("48.8 TB", final["answer"])         # provisional not served
        finally:
            httpd.shutdown()

    def test_health_pages_metrics_ask(self):
        self.seed()
        self.out.write_text("A single object can be up to 48.8 TB [W:services/obs].")
        httpd, port = self._start_server()
        try:
            code, ctype, body = self._get(port, "/health")
            self.assertEqual(code, 200)
            h = json.loads(body)
            self.assertIn("git_sha", h)
            self.assertIn("version", h)
            code, ctype, body = self._get(port, "/metrics")
            self.assertIn("llmwiki_asks_total", body)
            code, ctype, body = self._get(port, "/pages")
            pages = json.loads(body)["pages"]
            self.assertIn("services/obs", [p["slug"] for p in pages])
            obs_entry = [p for p in pages if p["slug"] == "services/obs"][0]
            self.assertEqual(obs_entry["title"], "Object Storage Service (OBS)")
            f = Path(self.tmp.name) / "src-detail.md"
            f.write_text("OBS release note: maximum object size is now 48.8 TB for all regions and tiers.")
            src = self.wiki.sources.add(str(f), kind="doc")
            tok = auth.open_tokens(self.cfg).create("contributor", "bob", self.cfg)
            code, _, body = self._get(port, f"/source?id={src['id']}",
                                      headers={"X-LLMWiki-Token": tok})
            self.assertEqual(code, 200)
            d = json.loads(body)
            self.assertIn("48.8 TB", d["text"])
            self.assertEqual(d["meta"]["id"], src["id"])
            try:
                self._get(port, "/source?id=deadbeefdeadbeef",
                          headers={"X-LLMWiki-Token": tok})
                self.fail("expected 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)
            code, ctype, body = self._get(port, "/search?q=object%20size")
            self.assertIn("services/obs", body)
            code, body = self._post(port, "/ask.json", {"question": "What is the max OBS object size?"})
            r = json.loads(body)
            self.assertEqual(r["status"], "grounded", r)
            # SSE
            req = urllib.request.Request(f"http://127.0.0.1:{port}/ask", method="POST",
                                         data=json.dumps({"question": "OBS object size"}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                stream = resp.read().decode("utf-8")
            for ev in ("event: ack", "event: retrieval", "event: thinking",
                       "event: provisional", "event: final"):
                self.assertIn(ev, stream)
            self.assertIn("conversation_id", stream)
            self.assertIn('"delta": "Let me', stream)          # thinking payload streams
            self.assertLess(stream.index("event: thinking"), stream.index("event: provisional"))
            self.assertLess(stream.index("event: provisional"), stream.index("event: final"))
            final_line = [l for l in stream.splitlines() if l.startswith("data:")][-1]
            self.assertIn("48.8 TB", final_line)                # verified answer is final
            # auth: approve without token is refused
            try:
                self._post(port, "/changesets/approve", {"id": "20260101000000-abcdef"})
                self.fail("should have been 403")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)
            # reader cannot list sources
            try:
                self._get(port, "/sources")
                self.fail("should have been 403")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)
            tok = auth.open_tokens(self.cfg).create("contributor", "bob", self.cfg)
            code, _, body = self._get(port, "/sources", headers={"X-LLMWiki-Token": tok})
            self.assertEqual(code, 200)
        finally:
            httpd.shutdown()


def multipart(fields: dict, filefield: str, filename: str, content: bytes, boundary=b"XbX") -> bytes:
    out = b""
    for k, v in fields.items():
        out += (f"--{boundary.decode()}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    out += (f"--{boundary.decode()}\r\nContent-Disposition: form-data; name=\"{filefield}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: text/markdown\r\n\r\n").encode() + content + b"\r\n"
    out += f"--{boundary.decode()}--\r\n".encode()
    return out


class UploadTests(WebTests):
    def _upload(self, port, body, token=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/upload", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary=XbX",
                     **({"X-LLMWiki-Token": token} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"error": raw.decode("utf-8", "replace")[:200]}

    def test_upload_public_doc_auto_applies(self):
        self.seed()
        content = b"Uploads flow through the real pipeline and update the wiki automatically."
        sid = hashlib.sha256(content).hexdigest()[:16]
        self.out.write_text(json.dumps({"pages": [
            {"slug": "concepts/uploaded-note", "title": "Uploaded note", "type": "concept",
             "compiled_truth": f"Uploads flow through the real pipeline [S:{sid}].",
             "timeline": [{"date": TODAY, "text": f"filed [S:{sid}]"}]}]}))
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "u1", self.cfg)
            body = multipart({"kind": "doc", "licence": "public"}, "file", "note.md", content)
            code, d = self._upload(port, body, tok)
            self.assertEqual(code, 200, d)
            self.assertTrue(d["auto_applied"], d)
            self.assertEqual(d["changeset"]["status"], "applied")
            sid = d["source"]["id"]
            self.assertIn("concepts/uploaded-note", _wiki_slugs(self))
            # roster cache invalidated: page_list sees it
            self.assertIn("concepts/uploaded-note", [p["slug"] for p in self.wiki.page_list()])
        finally:
            httpd.shutdown()

    def test_upload_protected_stays_pending(self):
        self.seed()
        content = b"Price update: OBS standard storage costs USD 0.02 per GB-month today."
        sid = hashlib.sha256(content).hexdigest()[:16]
        self.out.write_text(json.dumps({"pages": [
            {"slug": "pricing/uploaded", "compiled_truth": f"USD 0.02 per GB-month [S:{sid}]",
             "timeline": [{"date": TODAY, "text": f"price [S:{sid}]"}]}]}))
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "u1", self.cfg)
            body = multipart({"kind": "price", "licence": "public"}, "file", "p.md", content)
            code, d = self._upload(port, body, tok)
            self.assertEqual(code, 200, d)
            self.assertFalse(d["auto_applied"])
            self.assertEqual(d["changeset"]["status"], "pending")
            self.assertEqual(d["changeset"]["protected"], ["pricing"])
        finally:
            httpd.shutdown()

    def test_upload_rejections(self):
        self.seed()
        httpd, port = self._start_server()
        try:
            code, d = self._upload(port, b"not multipart at all")   # no token
            self.assertEqual(code, 403)                              # authz fires first
            tok = auth.open_tokens(self.cfg).create("contributor", "u1", self.cfg)
            code, d = self._upload(port, b"not multipart at all", tok)
            self.assertEqual(code, 400)
            tok = auth.open_tokens(self.cfg).create("contributor", "u1", self.cfg)
            code, d = self._upload(port, multipart({"kind": "doc"}, "file", "x.exe", b"MZ..."), tok)
            self.assertEqual(code, 415)
            code, d = self._upload(port, multipart({"kind": "doc", "licence": "public"}, "file",
                                                   "tiny.md", b"too short"), tok)
            self.assertEqual(code, 422)   # ingest rejects <40 chars
        finally:
            httpd.shutdown()


    def test_delete_source(self):
        """Delete flow: uncited source removed (pending cs rejected); cited -> 409."""
        self.seed()
        f = self.d / "del.md"
        f.write_text("A standalone note about EVS disks that no wiki page cites yet, long enough to ingest.")
        meta = self.wiki.sources.add(str(f), kind="doc", licence="internal")
        sid = meta["id"]
        # a pending changeset citing it gets rejected on delete
        self.wiki.changes.create(meta, {"pages": [], "conflicts": []}, [])
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "d1", self.cfg)

            def delete(id_):
                req = urllib.request.Request(f"http://127.0.0.1:{port}/source?id={id_}",
                                             method="DELETE",
                                             headers={"X-LLMWiki-Token": tok})
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    raw = e.read()
                    try:
                        return e.code, json.loads(raw)
                    except Exception:
                        return e.code, {"error": raw.decode()[:120]}

            code, d = delete(sid)
            self.assertEqual(code, 200, d)
            self.assertEqual(d["deleted"], sid)
            self.assertEqual(len(d["rejected_changesets"]), 1)
            self.assertFalse((self.wiki.sources.root / f"{sid}.json").exists())
            code, d = delete("deadbeefdeadbeef")
            self.assertEqual(code, 404)
            # cited source refuses (make a REAL source cited by a page)
            fc = self.d / "cited.md"
            fc.write_text("OBS spec sheet backing the services page: object size and storage classes.")
            cited_meta = self.wiki.sources.add(str(fc), kind="doc", licence="public")
            obs = self.wiki.store.get("services/obs")
            obs.sources = [cited_meta["id"]]
            self.wiki.store.put(obs)
            code, d = delete(cited_meta["id"])
            self.assertEqual(code, 409)
            self.assertIn("services/obs", d["pages"])
        finally:
            httpd.shutdown()


def _wiki_slugs(test):
    return [p["slug"] for p in test.wiki.page_list()]



if __name__ == "__main__":
    unittest.main()


class UploadRefDisplay(unittest.TestCase):
    """MD fix 2026-09-24: uploaded sources must carry a relative display ref —
    absolute server paths leaked into tooltips and citation chips."""

    def test_meta_ref_overrides_display_ref(self):
        from llmwiki.sources import SourceStore
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            f = d / "note.md"
            f.write_text("Obs display-ref regression note with enough text to ingest.")
            store = SourceStore(d / "srcs")
            meta = store.add(str(f), kind="note", meta_ref=f"uploads/{f.name}")
            self.assertEqual(meta["ref"], f"uploads/{f.name}")   # stored ref is relative
            got, _ = store.get(meta["id"])
            self.assertEqual(got["ref"], f"uploads/{f.name}")


class SourceCascadeTests(WebTests):
    """PRD V7: cascade delete — statement-granular retraction + emptied-page deletion,
    one change set per cascade (D-5), 409 advertises the option."""

    def _mk_source(self, name, text):
        f = self.d / name
        f.write_text(text)
        return self.wiki.sources.add(str(f), kind="doc", licence="internal",
                                     meta_ref=f"uploads/{name}")

    def test_retract_statements_surgical(self):
        from llmwiki.pipeline import _retract_statements
        body = ("OBS offers Standard storage classes [S:aaaaaaaaaaaaaaaa]. "
                "A single object can be up to 48.8 TB [S:bbbbbbbbbbbbbbbb]. "
                "Buckets are DNS-named [S:aaaaaaaaaaaaaaaa].\n"
                "Pricing note: storage costs USD 0.099 per GB-month [S:cccccccccccccccc].")
        new, removed = _retract_statements(body, "aaaaaaaaaaaaaaaa")
        self.assertEqual(removed, 2)
        self.assertEqual(new, "A single object can be up to 48.8 TB [S:bbbbbbbbbbbbbbbb].\n"
                              "Pricing note: storage costs USD 0.099 per GB-month [S:cccccccccccccccc].")

    def test_cascade_retracts_mixed_page_and_deletes_emptied_page(self):
        sid_a = "aaaaaaaaaaaaaaaa"
        meta_b = self._mk_source("b.md", "Supplementary EVS note backing one statement only, long enough.")
        sid_b = meta_b["id"]
        self.wiki.store.put(Page(slug="services/obs", title="OBS", type="service",
                                 compiled_truth="OBS offers Standard storage classes [S:%s]. "
                                                "EVS snapshots are incremental [S:%s]." % (sid_a, sid_b),
                                 sources=[sid_a, sid_b], last_verified=TODAY))
        self.wiki.store.put(Page(slug="concepts/evs-notes", title="EVS notes", type="concept",
                                 compiled_truth="EVS snapshots are incremental [S:%s]." % sid_b,
                                 sources=[sid_b], last_verified=TODAY))
        self.wiki.changes.create(meta_b, {"pages": [], "conflicts": []}, [])   # pending cs

        r = self.wiki.delete_source(sid_b)
        self.assertTrue(r["blocked"])                                   # cited → needs cascade
        r = self.wiki.delete_source(sid_b, cascade=True, actor="delete-cascade")
        self.assertEqual(r["deleted"], sid_b)
        by = {a["slug"]: a for a in r["pages"]}
        self.assertEqual(by["services/obs"]["action"], "retracted")
        self.assertEqual(by["services/obs"]["statements_removed"], 1)
        self.assertEqual(by["concepts/evs-notes"]["action"], "page-deleted")
        obs = self.wiki.store.get("services/obs")
        self.assertEqual(obs.compiled_truth, "OBS offers Standard storage classes [S:%s]." % sid_a)
        self.assertEqual(obs.sources, [sid_a])
        self.assertIn("retracted (delete-cascade)", obs.timeline[0]["text"])
        self.assertIsNone(self.wiki.store.get("concepts/evs-notes"))     # emptied → gone
        self.assertTrue(r["rejected_changesets"])                        # pending cs rejected
        applied = [c for c in self.wiki.changes.list() if c["status"] == "applied"
                   and c["source"]["id"] == sid_b]
        self.assertEqual(len(applied), 1)                                # D-5: cs records cascade
        self.assertIn("delete-cascade", applied[0]["history"][0]["actor"])

    def test_http_409_advertises_cascade_and_cascade_succeeds(self):
        self.seed()
        meta = self._mk_source("cited.md", "EVS spec note backing the obs page, long enough to ingest.")
        sid = meta["id"]
        obs = self.wiki.store.get("services/obs")
        obs.compiled_truth += f" EVS detail follows [S:{sid}]."
        obs.sources = obs.sources + [sid]
        self.wiki.store.put(obs)
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "cx", self.cfg)

            def delete(qs):
                req = urllib.request.Request(f"http://127.0.0.1:{port}/source?{qs}",
                                             method="DELETE",
                                             headers={"X-LLMWiki-Token": tok})
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())

            code, d = delete(f"id={sid}")
            self.assertEqual(code, 409)
            self.assertTrue(d["cascade_available"])
            self.assertIn("services/obs", d["pages"])
            code, d = delete(f"id={sid}&cascade=1")
            self.assertEqual(code, 200, d)
            self.assertTrue(d["cascade"])
            self.assertEqual(d["pages"][0]["slug"], "services/obs")
            obs2 = self.wiki.store.get("services/obs")
            self.assertNotIn(sid, obs2.sources)
            self.assertNotIn(f"[S:{sid}]", obs2.compiled_truth)
            self.assertIn("48.8 TB", obs2.compiled_truth)               # survivors intact
        finally:
            httpd.shutdown()


class MCPStoreNotFoundTests(unittest.TestCase):
    """Regression 2026-09-24 (empty-wiki first upload): gbrain answers page_not_found
    with isError for a brand-new slug; GBrainStore.get must map that to None so
    approve()/merge() can CREATE the page instead of crashing the upload autoflow."""

    def test_get_unknown_slug_returns_none_via_mcp(self):
        import tempfile
        from llmwiki.config import GBrainCfg, Config
        from llmwiki.store import GBrainStore
        with tempfile.TemporaryDirectory() as td:
            cfg = Config(gbrain=GBrainCfg(backend="gbrain-mcp",
                                          bin=str(ROOT / "tests" / "fakes" / "gbrain_mcp_serve"),
                                          env={"FAKE_MCP_DIR": td}),
                         jiuwen=None, ask=None)   # type: ignore[arg-type]
            store = GBrainStore(cfg)
            self.assertTrue(store.use_mcp)
            self.assertIsNone(store.get("services/brand-new-page"))    # was StoreError
            page = store.get("services/obs")                           # known page intact
            self.assertIsNotNone(page)
            store._mcp_client().close()


class MultiTurnTests(ExtBase):
    """PRD V8: history widens retrieval (incl. prior [W:] cites) and travels into
    the prompt as context-only; no history keeps the V2 prompt byte-identical."""

    def _ask(self, question, history=None, **kw):
        self.out.write_text("OBS objects can be up to 48.8 TB [W:services/obs].")
        return self.wiki.ask(question, history=history, **kw)

    def test_prompt_carries_conversation_block(self):
        self.seed()
        self._ask("What is OBS?", history=[{"q": "Tell me about storage",
                                            "a": "OBS is object storage [W:services/obs]."}])
        prompt = self.prompt_log.read_text()
        self.assertIn("CONVERSATION SO FAR (context only, NOT evidence", prompt)
        self.assertIn("Q1: Tell me about storage", prompt)
        self.assertIn("A1: OBS is object storage", prompt)
        self.assertIn("QUESTION: What is OBS?", prompt)

    def test_prior_cited_pages_join_retrieval(self):
        self.seed()
        # question alone would not match the obs page; the prior answer's cite pulls it in
        res = self._ask("cuanto cuesta", history=[{"q": "que es OBS",
                                                   "a": "OBS is object storage [W:services/obs]."}])
        self.assertIn("services/obs", res.retrieved)

    def test_no_history_prompt_unchanged(self):
        self.seed()
        self._ask("What is OBS?")
        prompt = self.prompt_log.read_text()
        self.assertIn("QUESTION: What is OBS?", prompt)
        self.assertNotIn("CONVERSATION SO FAR", prompt)

    def test_log_records_conversation_and_turn(self):
        self.seed()
        res = self._ask("What is OBS?", history=[{"q": "prior", "a": "prior answer"}],
                        conversation_id="conv123", turn=2)
        self.assertEqual(res.conversation_id, "conv123")
        line = self.wiki.log.read_text().strip().splitlines()[-1]
        rec = json.loads(line)
        self.assertEqual(rec["conversation_id"], "conv123")
        self.assertEqual(rec["turn"], 2)


class CJKNumberGroundingTests(unittest.TestCase):
    """Regression 2026-09-24 (DeepSeek upload rejected as invalid): 中文排版把数字
    紧贴汉字(于2026年9月10日),NUM_RE 的 Unicode \\w 边界把这些数字整个排除在
    文档数字集之外 → not_in_cited。边界必须只按 ASCII 字符类判定。"""

    def test_cjk_packed_date_grounds(self):
        doc = "DeepSeek-V4.1-Flash是DeepSeek 于2026年9月10日正式发布的新一代大语言模型。"
        r = grounding.verify(
            "DeepSeek-V4.1-Flash 于 2026 年 9 月 10 日正式发布 [S:src1]。",
            {"src1": doc}, cite_prefix="S", terms=["DeepSeek"])
        self.assertEqual(r.status, "grounded", r.issues)

    def test_identifier_protection_unchanged(self):
        # v4.1 / filename-adjacent numbers must still NOT be read as bare numbers
        doc = "版本v4.1发布,构建号20260910-abc。"
        r = grounding.verify(
            "版本为 4.1,构建号 abc [S:src1]。", {"src1": doc}, cite_prefix="S", terms=["版本"])
        self.assertNotEqual(r.status, "grounded")          # 4.1 stays ungrounded
        r2 = grounding.verify(
            "发布日期为 2026 年 [S:src1]。", {"src1": doc}, cite_prefix="S", terms=["发布"])
        self.assertNotEqual(r2.status, "grounded")         # 20260910 ≠ 2026 still holds

    def test_cjk_packed_decimal_grounds(self):
        doc = "推理价格为0.26美元每百万tokens起。"
        r = grounding.verify(
            "推理价格为 0.26 美元每百万 tokens 起 [S:s]。", {"s": doc}, cite_prefix="S",
            terms=["tokens"])
        self.assertEqual(r.status, "grounded", r.issues)


class WebEditTests(WebTests):
    """PRD V9: manual web edits go through the grounding gate + change sets (D-5)."""

    def _seed_edit(self):
        f = self.d / "obs.md"
        f.write_text("OBS offers Standard and Infrequent Access storage classes. "
                     "A single object can be up to 48.8 TB. "
                     "Storage costs USD 0.099 per GB-month.")
        self.sid = self.wiki.sources.add(str(f), kind="doc", licence="public")["id"]
        self.wiki.store.put(Page(slug="services/obs", title="Object Storage Service (OBS)",
                                 type="service",
                                 compiled_truth=f"OBS offers Standard storage classes [S:{self.sid}]. "
                                                f"A single object can be up to 48.8 TB [S:{self.sid}].",
                                 sources=[self.sid], last_verified=TODAY))
        self.wiki.store.put(Page(slug="pricing/obs-storage", title="OBS pricing", type="price",
                                 compiled_truth=f"Storage costs USD 0.099 per GB-month [S:{self.sid}].",
                                 sources=[self.sid], last_verified=TODAY))

    def test_clean_edit_applies(self):
        self._seed_edit()
        new_truth = (f"OBS offers Standard and Infrequent Access storage classes [S:{self.sid}]. "
                     f"A single object can be up to 48.8 TB [S:{self.sid}].")
        r = self.wiki.edit_page("services/obs", new_truth, "robin")
        self.assertTrue(r["applied"], r["problems"])
        p = self.wiki.store.get("services/obs")
        self.assertEqual(p.compiled_truth, new_truth)
        self.assertIn("manual web edit by robin", p.timeline[0]["text"])
        self.assertEqual(p.last_verified, TODAY)
        cs = self.wiki.changes.get(r["changeset"]["id"])
        self.assertEqual(cs["status"], "applied")
        self.assertEqual(cs["source"]["ref"], "web-edit:services/obs")

    def test_uncited_number_refused_page_unchanged(self):
        self._seed_edit()
        before = self.wiki.store.get("services/obs").compiled_truth
        r = self.wiki.edit_page("services/obs",
                                f"OBS offers Standard classes [S:{self.sid}]. "
                                "Objects can be up to 9999 TB.",
                                "robin")
        self.assertFalse(r["applied"])
        joined = " ".join(p["problem"] for p in r["problems"])
        self.assertTrue("not_in_cited" in joined or "uncited" in joined, joined)
        self.assertEqual(self.wiki.store.get("services/obs").compiled_truth, before)

    def test_unknown_citation_is_problem(self):
        self._seed_edit()
        r = self.wiki.edit_page("services/obs",
                                "OBS offers Standard classes [S:deadbeefdeadbeef].", "robin")
        self.assertFalse(r["applied"])
        self.assertIn("unknown_citation", " ".join(p["problem"] for p in r["problems"]))

    def test_citing_new_source_joins_sources(self):
        self._seed_edit()
        f = self.d / "extra.md"
        f.write_text("OBS Archive class exists for rarely accessed cold data.")
        m = self.wiki.sources.add(str(f), kind="doc", licence="public")
        new_truth = (f"OBS offers Standard classes [S:{self.sid}]. "
                     f"An Archive class exists for cold data [S:{m['id']}].")
        r = self.wiki.edit_page("services/obs", new_truth, "robin")
        self.assertTrue(r["applied"], r["problems"])
        self.assertIn(m["id"], self.wiki.store.get("services/obs").sources)

    def test_protected_needs_flag_and_http_role_gate(self):
        self._seed_edit()
        truth = f"Storage costs USD 0.099 per GB-month [S:{self.sid}]."
        with self.assertRaises(Exception):                       # pipeline gate without flag
            self.wiki.edit_page("pricing/obs-storage", "x", "robin")
        r = self.wiki.edit_page("pricing/obs-storage", truth, "robin", allow_protected=True)
        self.assertTrue(r["applied"], r["problems"])
        httpd, port = self._start_server()
        try:
            import urllib.error

            def post(path, body, tok):
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                             data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json",
                                                      "X-LLMWiki-Token": tok}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=10) as rr:
                        return rr.status, json.loads(rr.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())

            ctok = auth.open_tokens(self.cfg).create("contributor", "e1", self.cfg)
            ktok = auth.open_tokens(self.cfg).create("curator", "e2", self.cfg)
            code, d = post("/pages/edit", {"slug": "pricing/obs-storage",
                                           "compiled_truth": truth}, ctok)
            self.assertEqual(code, 403)                          # contributor refused
            code, d = post("/pages/edit", {"slug": "pricing/obs-storage",
                                           "compiled_truth": truth}, ktok)
            self.assertEqual(code, 200, d)
            self.assertTrue(d["applied"], d["problems"])         # curator applies
            code, d = post("/pages/edit", {"slug": "services/obs",
                                           "compiled_truth": f"OBS offers Standard classes [S:{self.sid}]."},
                           ctok)
            self.assertEqual(code, 200, d)
            self.assertTrue(d["applied"], d["problems"])         # non-protected for contributor
        finally:
            httpd.shutdown()


class RecompileTests(WebTests):
    """PRD V10: recompile an existing L1 source through the real pipeline + autoflow."""

    def _src(self):
        f = self.d / "rc.md"
        f.write_text("OBS offers Standard storage classes. A single object can be up to 48.8 TB.")
        return self.wiki.sources.add(str(f), kind="doc", licence="public")

    def _rcpost(self, port, path, body, tok):
        import urllib.error
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "X-LLMWiki-Token": tok}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_recompile_clean_applies(self):
        meta = self._src()
        self.out.write_text(json.dumps({
            "pages": [{"slug": "services/obs", "title": "Object Storage Service (OBS)",
                       "type": "service",
                       "compiled_truth": f"OBS offers Standard storage classes [S:{meta['id']}]. "
                                         f"A single object can be up to 48.8 TB [S:{meta['id']}].",
                       "timeline": [{"date": TODAY, "text": "recompiled"}]}],
            "conflicts": []}))
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "rc", self.cfg)
            code, d = self._rcpost(port, "/recompile", {"id": meta["id"]}, tok)
            self.assertEqual(code, 200, d)
            self.assertTrue(d["auto_applied"], d)
            self.assertEqual(d["changeset"]["status"], "applied")
            self.assertEqual(d["changeset"]["pages"][0]["slug"], "services/obs")
            p = self.wiki.store.get("services/obs")
            self.assertIn("48.8 TB", p.compiled_truth)
            audits = [json.loads(l) for l in
                      Path(self.cfg.runtime_dir, "logs", "audit.jsonl").read_text().splitlines()]
            self.assertTrue(any(a["action"] == "recompile" and a.get("auto_applied")
                                for a in audits))
        finally:
            httpd.shutdown()

    def test_recompile_problems_surfaced_no_write(self):
        meta = self._src()
        before = self.wiki.store.get("services/obs")
        before_truth = before.compiled_truth if before else None
        self.out.write_text(json.dumps({
            "pages": [{"slug": "services/obs", "title": "OBS", "type": "service",
                       "compiled_truth": f"Objects can be up to 9999 TB [S:{meta['id']}]."}],
            "conflicts": []}))
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "rc2", self.cfg)
            code, d = self._rcpost(port, "/recompile", {"id": meta["id"]}, tok)
            self.assertEqual(code, 200, d)
            self.assertFalse(d["auto_applied"])
            self.assertTrue(d["problems"])
            after = self.wiki.store.get("services/obs")
            self.assertEqual(after.compiled_truth if after else None, before_truth)
        finally:
            httpd.shutdown()

    def test_recompile_unknown_404(self):
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "rc3", self.cfg)
            code, d = self._rcpost(port, "/recompile", {"id": "deadbeefdeadbeef"}, tok)
            self.assertEqual(code, 404)
        finally:
            httpd.shutdown()


class ConversationHistoryTests(WebTests):
    """PRD V12: list + delete conversation threads."""

    def test_list_and_delete(self):
        self.seed()
        self.out.write_text("OBS objects can be up to 48.8 TB [W:services/obs].")
        httpd, port = self._start_server()
        try:
            tok = auth.open_tokens(self.cfg).create("contributor", "h1", self.cfg)

            def ask(cid):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/ask.json", method="POST",
                    data=json.dumps({"question": "What is OBS?", "conversation_id": cid}).encode(),
                    headers={"Content-Type": "application/json", "X-LLMWiki-Token": tok})
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read())

            r1 = ask("abc123def456")
            self.assertEqual(r1["conversation_id"], "abc123def456")
            code, ctype, body = self._get(port, "/conversations",
                                          headers={"X-LLMWiki-Token": tok})
            self.assertEqual(code, 200)
            items = json.loads(body)["conversations"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["id"], "abc123def456")
            self.assertEqual(items[0]["title"], "What is OBS?")
            self.assertEqual(items[0]["turns"], 1)
            # delete → gone (list + detail 404)
            req = urllib.request.Request(f"http://127.0.0.1:{port}/conversations/abc123def456",
                                         method="DELETE",
                                         headers={"X-LLMWiki-Token": tok})
            with urllib.request.urlopen(req, timeout=10) as r:
                self.assertEqual(json.loads(r.read())["deleted"], "abc123def456")
            code, ctype, body = self._get(port, "/conversations",
                                          headers={"X-LLMWiki-Token": tok})
            self.assertEqual(json.loads(body)["conversations"], [])
            try:
                self._get(port, "/conversations/abc123def456",
                          headers={"X-LLMWiki-Token": tok})
                self.fail("expected 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)
            # unknown delete → 404
            req = urllib.request.Request(f"http://127.0.0.1:{port}/conversations/ffffffffffff",
                                         method="DELETE",
                                         headers={"X-LLMWiki-Token": tok})
            try:
                urllib.request.urlopen(req, timeout=10)
                self.fail("expected 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)
        finally:
            httpd.shutdown()
