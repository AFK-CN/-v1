import unittest

from tools.jianghushuo_stage3_6 import METHOD_SPECS, blind_decision, build_prompt_cases


class JianghushuoStage36Tests(unittest.TestCase):
    def test_blind_decision_requires_two_mechanism_signals(self) -> None:
        method = {"trigger_signals": ["信号甲", "信号乙", "信号丙"]}
        self.assertEqual(blind_decision(method, "只有信号甲"), (False, ["信号甲"]))
        self.assertEqual(blind_decision(method, "同时有信号甲和信号乙"), (True, ["信号甲", "信号乙"]))

    def test_v22_pressure_cases_include_commercial_and_ablation_tests(self) -> None:
        method_ids = list(METHOD_SPECS)
        current_id, sibling_id = method_ids[:2]
        current = {
            "title": "当前方法",
            "trigger_signals": METHOD_SPECS[current_id]["signals"],
            "trigger_model": {"transferable_scenes": METHOD_SPECS[current_id]["scenes"]},
        }
        sibling = {
            "title": "兄弟方法",
            "trigger_signals": METHOD_SPECS[sibling_id]["signals"],
            "trigger_model": {"transferable_scenes": METHOD_SPECS[sibling_id]["scenes"]},
        }

        case_types = {item["type"] for item in build_prompt_cases(current_id, current, sibling_id, sibling)}

        self.assertTrue({"commercial_contamination", "mechanism_ablation", "composition_ablation"}.issubset(case_types))


if __name__ == "__main__":
    unittest.main()
