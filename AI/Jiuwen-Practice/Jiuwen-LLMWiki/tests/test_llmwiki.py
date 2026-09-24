"""Unit + integration tests. Stdlib unittest; no network, no real model.

Every positive case has a reverse case that must FAIL (PRD §12: discriminating gates).
Run: python3.12 -m unittest discover -s tests -v
"""
import json
import os
import random
import re
import sys
import tempfile
import textwrap
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llmwiki import changesets, config as config_mod, grounding, jiuwen  # noqa: E402
from llmwiki.pages import Page  # noqa: E402
from llmwiki.pipeline import Wiki, detect_lang  # noqa: E402
from llmwiki.store import FileStore, _slugs_from_output, open_store  # noqa: E402

FAKE = ROOT / "tests" / "fakes" / "jiuwenswarm"
TODAY = date.today().isoformat()

OBS = Page(slug="services/obs", title="Object Storage Service (OBS)", type="service",
           compiled_truth="OBS offers Standard, Infrequent Access and Archive storage classes [S:aaaaaaaaaaaaaaaa]. "
                          "A single object can be up to 48.8 TB [S:aaaaaaaaaaaaaaaa]. "
                          "Docs: https://support.huaweicloud.com/obs/index.html [S:aaaaaaaaaaaaaaaa].",
           timeline=[{"date": "2026-09-01", "text": "Max object size documented as 48.8 TB [S:aaaaaaaaaaaaaaaa]"}],
           links=["regions/la-sao-paulo1"], sources=["aaaaaaaaaaaaaaaa"], last_verified=TODAY)
SP = Page(slug="regions/la-sao-paulo1", title="LA-Sao Paulo1", type="region",
          compiled_truth="LA-Sao Paulo1 has 3 availability zones [S:bbbbbbbbbbbbbbbb]. "
                         "OBS is available in LA-Sao Paulo1 [S:bbbbbbbbbbbbbbbb].",
          links=["services/obs"], sources=["bbbbbbbbbbbbbbbb"], last_verified=TODAY)
PRICE = Page(slug="pricing/obs", title="OBS pricing", type="pricing",
             compiled_truth="Standard storage in LA-Sao Paulo1 costs USD 0.0235 per GB-month [S:cccccccccccccccc].",
             sources=["cccccccccccccccc"], last_verified=(date.today() - timedelta(days=200)).isoformat())


class GroundingTests(unittest.TestCase):
    docs = {"services/obs": OBS.to_markdown(), "regions/la-sao-paulo1": SP.to_markdown()}
    terms = ["LA-Sao Paulo1", "LA-Santiago", "LA-Mexico City2"]

    def v(self, text, **kw):
        return grounding.verify(text, self.docs, terms=self.terms, url_domains=["huaweicloud.com"], **kw)

    def test_correct_answer_grounded(self):
        r = self.v("A single OBS object can be up to 48.8 TB [W:services/obs]. "
                   "LA-Sao Paulo1 has 3 availability zones [W:regions/la-sao-paulo1].")
        self.assertEqual(r.status, "grounded", r.issues)
        self.assertEqual(r.claims, 3)   # 48.8, 3, term 'LA-Sao Paulo1' ('1' in 'Paulo1' is not a number claim)

    def test_reverse_fabricated_number(self):
        r = self.v("A single OBS object can be up to 50 TB [W:services/obs].")
        self.assertEqual(r.status, "partially_verified")
        self.assertIn(grounding.REDACTION, r.redacted_text)
        self.assertNotIn("50 TB", r.redacted_text)

    def test_reverse_value_only_in_uncited_page(self):
        # "3" exists in the region page but this sentence cites only the OBS page (GR-2).
        r = self.v("OBS has 3 storage tiers [W:services/obs].")
        self.assertEqual(r.status, "partially_verified")
        self.assertEqual(r.issues[0].reason, "not_in_cited")

    def test_reverse_uncited_fact(self):
        r = self.v("OBS objects can be up to 48.8 TB.")
        self.assertEqual(r.status, "no_citations")

    def test_reverse_unknown_citation(self):
        r = self.v("Objects can be up to 48.8 TB [W:services/evs].")
        self.assertEqual(r.issues[0].reason, "unknown_citation")

    def test_url_grounded_and_reverse_url(self):
        ok = self.v("See https://support.huaweicloud.com/obs/index.html [W:services/obs].")
        self.assertEqual(ok.status, "grounded", ok.issues)
        fake = self.v("See https://support.huaweicloud.com/obs/pricing.html [W:services/obs].")
        self.assertEqual(fake.issues[0].reason, "not_in_cited")
        foreign = self.v("Download https://s3.amazonaws.com/tool.zip [W:services/obs].")
        self.assertEqual(foreign.issues[0].reason, "url_domain")

    def test_region_term_reverse(self):
        r = self.v("OBS is available in LA-Santiago [W:regions/la-sao-paulo1].")
        self.assertEqual([i.claim for i in r.issues], ["LA-Santiago"])

    def test_latam_number_formats(self):
        for text in ("Um objeto pode ter até 48,8 TB [W:services/obs].",
                     "Un objeto puede tener hasta 48,8 TB [W:services/obs]."):
            self.assertEqual(self.v(text).status, "grounded", text)

    def test_table_rows(self):
        r = self.v("| Item | Value |\n|---|---|\n| Max object | 48.8 TB [W:services/obs] |\n"
                   "| AZs | 4 [W:regions/la-sao-paulo1] |")
        self.assertEqual([i.claim for i in r.issues], ["4"])

    def test_abstain(self):
        self.assertEqual(self.v("NOT_IN_WIKI The wiki has no GaussDB pricing.").status, "abstained")

    def test_discrimination_rate(self):
        """GR-5: perturbed numbers must be caught; the unperturbed answer must pass."""
        base = ("A single OBS object can be up to 48.8 TB [W:services/obs]. "
                "LA-Sao Paulo1 has 3 availability zones [W:regions/la-sao-paulo1].")
        self.assertEqual(self.v(base).status, "grounded")
        rnd = random.Random(7)
        caught = 0
        trials = 200
        for _ in range(trials):
            a, b = rnd.choice([(48.8, "48.8"), (3, "3")])
            new = a + rnd.choice([-1, 1]) * rnd.choice([0.1, 1, 2, 5, 10, 100])
            new_s = f"{new:g}"
            if new_s == b or new <= 0:
                caught += 1
                continue
            text = re.sub(r"(?<![\d.])%s(?![\d.])" % re.escape(b), new_s, base, count=1)
            caught += self.v(text).status != "grounded"
        self.assertGreaterEqual(caught / trials, 0.95)


class StoreAndPageTests(unittest.TestCase):
    def test_roundtrip_and_search(self):
        with tempfile.TemporaryDirectory() as d:
            fs = FileStore(Path(d))
            for p in (OBS, SP, PRICE):
                fs.put(p)
            got = fs.get("services/obs")
            self.assertEqual(got.compiled_truth, OBS.compiled_truth)
            self.assertEqual(got.timeline, OBS.timeline)
            self.assertEqual(got.links, OBS.links)
            self.assertEqual(fs.search("maximum object size OBS", 3)[0], "services/obs")
            # Known limitation of the keyword fallback (PRD B-1): a Portuguese query only matches
            # the shared token "obs", so ranking is not meaningful. Pinned so it is not forgotten.
            self.assertNotEqual(fs.search("tamanho máximo objeto OBS", 3)[0], "services/obs")
            self.assertIn("regions/la-sao-paulo1", fs.search("availability zones São Paulo", 3))

    def test_reverse_slug_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            fs = FileStore(Path(d))
            for bad in ("../etc/passwd", "services/../../x", "random/page", "services/"):
                with self.assertRaises(Exception):
                    fs.put(Page(slug=bad))

    def test_gbrain_output_parsing(self):
        self.assertEqual(_slugs_from_output('[{"slug":"services/obs","score":1},{"slug":"x/y"}]'),
                         ["services/obs"])
        self.assertEqual(_slugs_from_output("1. services/obs (0.91)\n2. regions/la-sao-paulo1 (0.4)\n"),
                         ["services/obs", "regions/la-sao-paulo1"])

    def test_staleness(self):
        self.assertTrue(PRICE.is_stale(90))
        self.assertFalse(OBS.is_stale(90))


class JiuwenParseTests(unittest.TestCase):
    REAL = textwrap.dedent("""\
        {"type": "event", "event": "chat.processing_status", "payload": {"event_type": "chat.processing_status", "session_id": "s1", "is_processing": true}}
        {"type": "event", "event": "chat.delta", "payload": {"event_type": "chat.delta", "content": "P", "session_id": "s1"}}
        {"type": "event", "event": "chat.delta", "payload": {"event_type": "chat.delta", "content": "ONG", "session_id": "s1"}}
        {"type": "event", "event": "chat.usage_metadata", "payload": {"event_type": "chat.usage_metadata", "metadata": {"usage_metadata": {"input_tokens": 24658, "output_tokens": 4}, "total_latency_ms": 7114.64, "ttft_ms": 7106.71}}}
        {"type": "event", "event": "chat.final", "payload": {"event_type": "chat.final", "content": "PONG", "session_id": "s1"}}
        """).splitlines()

    def test_real_sample(self):
        r = jiuwen.parse_events(self.REAL)
        self.assertEqual((r.content, r.input_tokens, r.ttft_ms, r.session_id), ("PONG", 24658, 7106.71, "s1"))
        self.assertFalse(r.role_dispatched)   # plain main-agent answer is NOT the role

    def test_real_code_mode_dispatch(self):
        # tool_result line captured on 247, code mode, 2026-09-23
        line = json.dumps({"type": "event", "event": "chat.tool_result", "payload": {
            "event_type": "chat.tool_result",
            "result": "success=True data={'output': 'A single object can be up to 48.8 TB [W:services/obs].', 'agent_id': 'llmwiki'} error=None",
            "tool_name": "Agent", "tool_call_id": "call_7c", "session_id": "s2"}})
        final = json.dumps({"type": "event", "event": "chat.final", "payload": {"content": "It is 48.8 TB."}})
        r = jiuwen.parse_events([line, final])
        self.assertTrue(r.role_dispatched)
        self.assertEqual(r.content, "A single object can be up to 48.8 TB [W:services/obs].")
        self.assertEqual(r.main_final, "It is 48.8 TB.")

    def test_reverse_agent_mode_empty_result(self):
        # agent mode on 0.2.3: task_tool names the role but the sub-agent crashed → empty result
        line = json.dumps({"type": "event", "event": "chat.tool_result", "payload": {
            "result": "", "tool_name": "task_tool", "tool_call_id": "c"}})
        self.assertFalse(jiuwen.parse_events([line]).role_dispatched)

    def test_reverse_other_agent_or_failure(self):
        for res in ("success=True data={'output': 'x', 'agent_id': 'general_agent'} error=None",
                    "success=False data={'output': 'x', 'agent_id': 'llmwiki'} error=boom"):
            line = json.dumps({"type": "event", "event": "chat.tool_result",
                               "payload": {"result": res, "tool_name": "Agent"}})
            self.assertFalse(jiuwen.parse_events([line]).role_dispatched, res)

    def test_json_mode(self):
        self.assertEqual(jiuwen.parse_events(['{"ok": true, "content": "hi"}']).content, "hi")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "cfg.toml").write_text(textwrap.dedent(f"""\
            runtime_dir = "{d}/runtime"
            [gbrain]
            backend = "files"
            files_dir = "{d}/runtime/wiki"
            [jiuwen]
            bin = "{FAKE}"
            data_dir = "{d}/runtime/jiuwen"
            timeout_s = 20
            [ask]
            url_domains = ["huaweicloud.com"]
            """))
        self.cfg = config_mod.load(d / "cfg.toml")
        self.wiki = Wiki(self.cfg)
        self.out = d / "answer.txt"
        self.prompt_log = d / "prompt.txt"
        os.environ.update(FAKE_OUT=str(self.out), FAKE_RC="0", FAKE_PROMPT_LOG=str(self.prompt_log))
        os.environ.pop("FAKE_NO_DISPATCH", None)

    def tearDown(self):
        self.tmp.cleanup()
        for k in ("FAKE_OUT", "FAKE_RC", "FAKE_NO_DISPATCH", "FAKE_PROMPT_LOG"):
            os.environ.pop(k, None)

    def seed(self):
        for p in (OBS, SP, PRICE):
            self.wiki.store.put(p)

    def test_empty_wiki_abstains_without_model_call(self):
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "abstained")
        self.assertFalse(self.prompt_log.exists())

    def test_grounded_answer_and_evidence_in_prompt(self):
        self.seed()
        self.out.write_text("A single OBS object can be up to 48.8 TB [W:services/obs].")
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "grounded", r.issues)
        self.assertEqual(r.input_tokens, 1234)
        prompt = self.prompt_log.read_text()
        self.assertIn("LLMWIKI_TASK: answer", prompt)
        self.assertIn("<<<PAGE slug=services/obs", prompt)

    def test_reverse_fabrication_is_redacted(self):
        self.seed()
        self.out.write_text("A single OBS object can be up to 5 TB and costs USD 0.01 per GB [W:services/obs].")
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "partially_verified")
        self.assertNotIn("5 TB", r.answer)
        self.assertNotIn("0.01", r.answer)

    def test_reverse_uncited_answer_not_served(self):
        self.seed()
        self.out.write_text("OBS objects can be up to 48.8 TB.")
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "no_citations")
        self.assertTrue(r.answer.startswith("NOT_IN_WIKI"))

    def test_role_output_wins_over_main_paraphrase(self):
        self.seed()
        self.out.write_text("A single OBS object can be up to 48.8 TB [W:services/obs].")
        os.environ["FAKE_MAIN_TEXT"] = "OBS objects go up to 50 TB."
        try:
            r = self.wiki.ask("What is the max OBS object size?")
        finally:
            os.environ.pop("FAKE_MAIN_TEXT")
        self.assertEqual(r.status, "grounded")
        self.assertNotIn("50 TB", r.answer)

    def test_reverse_role_not_dispatched(self):
        self.seed()
        self.out.write_text("A single OBS object can be up to 48.8 TB [W:services/obs].")
        os.environ["FAKE_NO_DISPATCH"] = "1"
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "error")
        self.assertIn("role_not_dispatched", r.error)

    def test_gateway_down(self):
        self.seed()
        os.environ["FAKE_RC"] = "3"
        r = self.wiki.ask("What is the max OBS object size?")
        self.assertEqual(r.status, "error")
        self.assertIn("gateway_down", r.error)

    def test_stale_pricing_flagged(self):
        self.seed()
        self.out.write_text("Standard storage costs USD 0.0235 per GB-month [W:pricing/obs].")
        r = self.wiki.ask("OBS standard storage price per GB-month")
        self.assertIn("pricing/obs", r.stale)
        self.assertIn("stale=true", self.prompt_log.read_text())

    def _source(self, text):
        f = Path(self.tmp.name) / "src.md"
        f.write_text(text)
        return self.wiki.sources.add(str(f), kind="doc")

    def test_ingest_dedup_and_reverse_empty(self):
        m1 = self._source("OBS release note: maximum object size is now 48.8 TB for all regions.")
        m2 = self._source("OBS release note: maximum object size is now 48.8 TB for all regions.")
        self.assertTrue(m2.get("duplicate"))
        self.assertEqual(m1["id"], m2["id"])
        with self.assertRaises(Exception):
            self._source("tiny")

    def test_compile_approve_flow(self):
        self.seed()
        meta = self._source("Huawei Cloud news 2026-09-20: OBS is now available in LA-Santiago. "
                            "Maximum object size remains 48.8 TB.")
        sid = meta["id"]
        good = {"pages": [{"slug": "regions/la-santiago", "title": "LA-Santiago", "type": "region",
                           "compiled_truth": f"OBS is available in LA-Santiago [S:{sid}].",
                           "timeline": [{"date": "2026-09-20", "text": f"OBS launched [S:{sid}]"}],
                           "links": ["services/obs"]}],
                "conflicts": []}
        self.out.write_text("```json\n" + json.dumps(good) + "\n```")
        cs = self.wiki.compile(sid)
        self.assertEqual(cs["status"], "pending", cs["problems"])
        with self.assertRaises(changesets.ChangeSetError):
            self.wiki.approve(cs["id"], "llmwiki")               # agent cannot self-approve
        self.assertEqual(self.wiki.approve(cs["id"], "curator-ana"), ["regions/la-santiago"])
        page = self.wiki.store.get("regions/la-santiago")
        self.assertEqual(page.sources, [sid])
        self.assertEqual(page.last_verified, TODAY)
        with self.assertRaises(changesets.ChangeSetError):
            self.wiki.approve(cs["id"], "curator-ana")           # not pending any more

    def test_reverse_compile_fabrication_invalid(self):
        meta = self._source("Huawei Cloud news: OBS is now available in LA-Santiago with 2 AZs.")
        sid = meta["id"]
        bad = {"pages": [{"slug": "pricing/obs", "title": "OBS pricing",
                          "compiled_truth": f"OBS costs USD 0.019 per GB-month in LA-Santiago [S:{sid}].",
                          "timeline": []}]}
        self.out.write_text(json.dumps(bad))
        cs = self.wiki.compile(sid)
        self.assertEqual(cs["status"], "invalid")
        self.assertEqual(cs["protected"], ["pricing"])
        self.assertTrue(any("0.019" in p["problem"] for p in cs["problems"]))

    def test_compile_keeps_old_citations_checked(self):
        old = self._source("OBS spec sheet: a single object can be up to 48.8 TB in size.")
        new = self._source("OBS update: Deep Archive storage class launched on 2026-09-20.")
        truth = (f"A single object can be up to 48.8 TB [S:{old['id']}]. "
                 f"Deep Archive launched on 2026-09-20 [S:{new['id']}].")
        self.out.write_text(json.dumps({"pages": [{"slug": "services/obs", "compiled_truth": truth,
                                                   "timeline": []}]}))
        self.assertEqual(self.wiki.compile(new["id"])["status"], "pending")
        wrong = truth.replace("48.8", "64")
        self.out.write_text(json.dumps({"pages": [{"slug": "services/obs", "compiled_truth": wrong,
                                                   "timeline": []}]}))
        self.assertEqual(self.wiki.compile(new["id"])["status"], "invalid")

    def test_merge_timeline_append_only(self):
        merged = changesets.merge(Page.from_markdown(OBS.slug, OBS.to_markdown()),
                                  {"slug": "services/obs", "compiled_truth": "",
                                   "timeline": [{"date": "2026-09-22", "text": "new"}]}, "dddddddddddddddd", TODAY)
        self.assertEqual([e["date"] for e in merged.timeline], ["2026-09-22", "2026-09-01"])
        self.assertEqual(merged.compiled_truth, OBS.compiled_truth)   # empty proposal keeps truth

    def test_lint(self):
        self.seed()
        rep = self.wiki.lint()
        self.assertIn("pricing/obs", rep["stale"])
        self.assertIn("pricing/obs", rep["orphans"])
        self.assertTrue(rep["unknown_sources"])        # seed pages cite sources not in L1


class LangTests(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(detect_lang("Qual é o preço do OBS na região de São Paulo?"), "pt-BR")
        self.assertEqual(detect_lang("¿Cuál es el precio de OBS en la región de Santiago?"), "es")
        self.assertEqual(detect_lang("What is the price of OBS?"), "en")


class InstallerTests(unittest.TestCase):
    def test_patch_config(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML only in the JiuwenSwarm interpreter")
        sys.path.insert(0, str(ROOT / "deploy"))
        from install_instance import patch_config
        cfg = patch_config({"react": {"subagents": {"browser_agent": {"enabled": True}}},
                            "mcp": {"servers": [{"name": "x"}]}}, "llmwiki")
        self.assertEqual(cfg["react"]["subagents"]["llmwiki"], {"enabled": True})
        self.assertFalse(cfg["react"]["subagents"]["browser_agent"]["enabled"])
        self.assertEqual(cfg["mcp"]["servers"], [])
        self.assertTrue(cfg["permissions"]["enabled"])
        self.assertEqual(cfg["permissions"]["tools"]["bash"], "deny")
        self.assertEqual(cfg["permissions"]["tools"]["write_file"], "deny")


if __name__ == "__main__":
    unittest.main()
