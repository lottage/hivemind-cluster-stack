"""Offline tests for the household vocabulary (server setup/voice-server/vocab.py)."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server setup", "voice-server"))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))

import vocab  # noqa: E402

NAMES = ["Kylo", "Luna", "Savannah", "Austin"]


class TestCorrect(unittest.TestCase):
    def test_the_misses_heard_on_real_recordings_are_fixed(self):
        # heard 2026-09-30 from John's own voice: Parakeet wrote "Kyla" for Kylo and "Alston" for Austin
        self.assertEqual(vocab.correct("Where's Kyla?", NAMES), "Where's Kylo?")
        self.assertEqual(vocab.correct("It is Alston home.", NAMES), "It is Austin home.")

    def test_possessives_and_case(self):
        self.assertEqual(vocab.correct("Is Kyla's bowl empty", NAMES), "Is Kylo's bowl empty")
        self.assertEqual(vocab.correct("where is savanah", NAMES), "where is Savannah")

    def test_correct_names_and_ordinary_words_are_untouched(self):
        for t in ("Where's Kylo?", "Is Luna in the kitchen?", "Is Savannah home?", "Is Austin home?", "Turn on the porch light.",
                  "What's the temperature inside?", "Show me the backyard camera.", "Tell me a joke about toasters."):
            self.assertEqual(vocab.correct(t, NAMES), t)

    def test_every_recorded_phrase_survives(self):
        import voice_bench
        for p in voice_bench.PHRASES:
            self.assertEqual(vocab.correct(p["text"], NAMES), p["text"], p["text"])

    def test_a_different_first_letter_is_not_a_near_miss(self):
        self.assertEqual(vocab.correct("Justin is here", NAMES), "Justin is here")   # one edit from Austin, but another name

    def test_short_words_and_far_words_are_left_alone(self):
        self.assertEqual(vocab.correct("Lun is a word", NAMES), "Lun is a word")
        self.assertEqual(vocab.correct("Kylie said hello", NAMES), "Kylie said hello")     # 2 edits from Kylo, too far for a short word
        self.assertEqual(vocab.correct("Alaska is cold", NAMES), "Alaska is cold")

    def test_no_names_or_no_text_is_a_no_op(self):
        self.assertEqual(vocab.correct("Where's Kyla?", []), "Where's Kyla?")
        self.assertEqual(vocab.correct("", NAMES), "")

    def test_a_swapped_pair_of_letters_is_one_edit(self):
        self.assertEqual(vocab.correct("Where is Kyol", NAMES), "Where is Kylo")


class TestLoad(unittest.TestCase):
    def test_names_hints_and_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# comment\nKylo\n\n+thermostat  # a device word\n+TV lights\nLuna\n")
            path = f.name
        try:
            names, hints = vocab.load(path)
        finally:
            os.unlink(path)
        self.assertEqual(names, ["Kylo", "Luna"])
        self.assertEqual(hints, ["Kylo", "thermostat", "TV lights", "Luna"])          # names are hinted too; +words only hint
        self.assertEqual(vocab.prompt_from(hints), "Kylo, thermostat, TV lights, Luna.")

    def test_a_missing_file_is_empty_not_an_error(self):
        self.assertEqual(vocab.load("/nonexistent/vocab.txt"), ([], []))
        self.assertEqual(vocab.prompt_from([]), "")

    def test_the_shipped_vocab_file_has_the_household(self):
        names, hints = vocab.load(os.path.join(ROOT, "server setup", "voice-server", "vocab.txt"))
        for n in ("Kylo", "Luna", "Savannah", "Austin"):
            self.assertIn(n, names)
        self.assertNotIn("Computer", names)                    # a common word: hinted, never corrected to
        self.assertIn("Computer", hints)


if __name__ == "__main__":
    unittest.main()
