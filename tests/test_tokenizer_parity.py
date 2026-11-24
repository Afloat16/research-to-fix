import random
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import tokenizer_benchmark as b


class TokenizerParityTests(unittest.TestCase):
    def test_old_token_sequence_on_mixed_and_random_unicode(self):
        examples = ["TensorCUDA data_loader OOM C++ torch.nn", "混合精度 dtype 与中文 English",
                    "ＡＢＣｄｅｆ １２３ cache_缓存_data", "é e\u0301 Å K ㎏ Straße _foo",
                    "汉A汉_字__测试😀 变量_日本語", "A\tline\nwith\ncontrols\x00!"]
        rng = random.Random(475)
        alphabet = "abcdef ABCDEF 0123456789 _-./:!? \r\n\t\0中文缓存\u3400\u4dbf\u9ffféßＡ１２😀\u0301"
        examples.extend("".join(rng.choices(alphabet, k=rng.randrange(0, 800))) for _ in range(300))
        for text in examples:
            self.assertEqual(b.rc.recall_tokens(text), b.legacy_tokens(text))
            self.assertEqual(b.rc.precision_tokens(text), b.legacy_precision_tokens(text))

    def test_ascii_and_unicode_paths(self):
        report = b.compare(["word attention cache", "缓存 内存 data_loader", ""] * 20, 2)
        self.assertTrue(report["exact_token_sequence_parity"])


if __name__ == "__main__":
    unittest.main()
