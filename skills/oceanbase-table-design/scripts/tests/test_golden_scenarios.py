"""黄金场景测试：给定一个代表性输入，Skill 文本里的规则是否**还够用**。

与合约测试的分工（进阶篇 §6.4）：
  * 合约测试 —— 单条规则是否存在（「每块砖都在」）；
  * 黄金场景 —— 一个完整场景所需的规则组合是否都还在（「砖块拼起来能盖住场景」）。

与 `tests/cases.json` 的分工，避免两套用例集漂移：
  * `tests/cases.json` 描述的是**Agent 输出**的评分标准（`must_include` 等），
    需要有人先跑一遍 Agent 才能判定，由 `run_cases.py --grade` 消费；
  * 本文件判定的是**Skill 文本自身**的规则可达性，零 LLM、随时可跑。
    两者通过共享的规则 ID 关联：每个 golden fixture 的 `rules` 必须都在
    `cases.json` 的规则清单里注册过，否则说明有一侧漏登记。

fixture 字段：
  scenario                 场景描述（人类可读）
  rules                    关联的规则 ID，必须在 cases.json 中已注册
  coverage_rules           这些关键词必须能在 SKILL.md + 关联 source 文件里找到
  anti_example_patterns    抑制/纠错性表述，必须存在，否则 Agent 会犯反向错误
  must_be_absent_from_oracle_bnf  可选：Oracle BNF 镜像里必须查不到的词

运行：python3 -m pytest scripts/tests -q
"""
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "golden")
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
REFS = os.path.join(SKILL_ROOT, "references")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def fenced_only(text):
    keep, infence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            infence = not infence
            continue
        if infence:
            keep.append(ln)
    return "\n".join(keep)


SKILL = read(os.path.join(SKILL_ROOT, "SKILL.md"))
ALL_REFS = "\n".join(
    read(os.path.join(REFS, n)) for n in sorted(os.listdir(REFS))
    if n.endswith(".md"))
CORPUS = SKILL + "\n" + ALL_REFS

with open(os.path.join(SKILL_ROOT, "tests", "cases.json"), encoding="utf-8") as f:
    CASES_SPEC = json.load(f)


def load_fixtures():
    out = []
    for fn in sorted(os.listdir(GOLDEN_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(GOLDEN_DIR, fn), encoding="utf-8") as fh:
                out.append((fn, json.load(fh)))
    return out


FIXTURES = load_fixtures()


class GoldenFixtureShapeTests(unittest.TestCase):
    def test_fixtures_exist(self):
        self.assertGreaterEqual(
            len(FIXTURES), 10,
            "黄金场景数量下降了——是否有 fixture 被误删？")

    def test_required_fields_present(self):
        for fn, g in FIXTURES:
            for field in ("id", "title", "scenario", "rules",
                          "coverage_rules", "anti_example_patterns"):
                self.assertIn(field, g, f"{fn} 缺字段 {field}")
            self.assertTrue(g["coverage_rules"], f"{fn} 的 coverage_rules 为空")
            self.assertTrue(g["anti_example_patterns"],
                            f"{fn} 的 anti_example_patterns 为空——"
                            f"只给正例会让 Agent 犯反向错误")

    def test_ids_unique(self):
        ids = [g["id"] for _, g in FIXTURES]
        self.assertEqual(len(ids), len(set(ids)), "golden id 重复")

    def test_rules_registered_in_cases_json(self):
        """两侧规则清单必须对齐，否则一侧改名另一侧静默失效。"""
        known = set(CASES_SPEC["rules"])
        for fn, g in FIXTURES:
            for rid in g["rules"]:
                self.assertIn(rid, known,
                              f"{fn} 引用了 cases.json 未注册的规则 {rid}")


class GoldenCoverageTests(unittest.TestCase):
    """逐条 coverage_rules / anti_example_patterns 检查。

    用子测试而非一个大循环，失败时能直接看到是哪个场景的哪条规则丢了。
    """

    def test_coverage_rules_present(self):
        for fn, g in FIXTURES:
            for needle in g["coverage_rules"]:
                with self.subTest(fixture=fn, rule=needle):
                    self.assertIn(
                        needle, CORPUS,
                        f"{g['id']} 所需的规则关键词缺失: {needle!r}\n"
                        f"场景: {g['scenario']}\n"
                        f"缺了它，Agent 在该场景下无法给出正确方案。")

    def test_anti_example_patterns_present(self):
        for fn, g in FIXTURES:
            for needle in g["anti_example_patterns"]:
                with self.subTest(fixture=fn, anti=needle):
                    self.assertIn(
                        needle, CORPUS,
                        f"{g['id']} 的抑制性表述缺失: {needle!r}\n"
                        f"场景: {g['scenario']}\n"
                        f"缺了它，Agent 会犯该场景的反向错误。")

    def test_oracle_bnf_absences(self):
        bnf = fenced_only(
            read(os.path.join(REFS, "oracle_mode_create_table_syntax.md")))
        for fn, g in FIXTURES:
            for needle in g.get("must_be_absent_from_oracle_bnf", []):
                with self.subTest(fixture=fn, absent=needle):
                    self.assertNotIn(
                        needle, bnf,
                        f"{g['id']} 假定 Oracle BNF 里没有 {needle!r}，"
                        f"但它出现了——该规则的事实基础已失效，请重新核对官方文档")


class GoldenNegativeControlTests(unittest.TestCase):
    """给检查器自身一个负面对照：不存在的关键词必须判失败。

    没有这条，`assertIn(needle, CORPUS)` 若因 CORPUS 拼装出错而变成空字符串以外的
    任意大字符串，测试仍会全绿而实际上什么也没验证。
    """

    def test_corpus_is_actually_loaded(self):
        self.assertGreater(len(CORPUS), 50000,
                           "语料拼装明显偏小，覆盖检查可能没读到 references/")

    def test_absent_keyword_is_detected_as_absent(self):
        self.assertNotIn("ThisTokenMustNeverAppearInTheSkill", CORPUS)


if __name__ == "__main__":
    unittest.main()
