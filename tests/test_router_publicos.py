from __future__ import annotations

import unittest

from src.query_analysis import analyze_query, augment_query_for_retrieval, should_force_dont_know


class RouterPublicosTests(unittest.TestCase):
    def test_prazo_intent(self):
        analysis = analyze_query("Qual é o prazo para apresentação das propostas?")
        self.assertEqual(analysis.intent, "prazo")

    def test_valor_intent(self):
        analysis = analyze_query("Existe preço base do procedimento?")
        self.assertEqual(analysis.intent, "valor")

    def test_guardrail(self):
        self.assertTrue(should_force_dont_know("Quem vai ganhar este concurso?"))
        self.assertFalse(should_force_dont_know("Qual é o critério de adjudicação?"))

    def test_query_augmentation(self):
        analysis = analyze_query("Qual é o prazo para apresentação das propostas?")
        q = augment_query_for_retrieval("Qual é o prazo para apresentação das propostas?", analysis)
        self.assertIn("prazo execução contrato", q)


if __name__ == "__main__":
    unittest.main()
