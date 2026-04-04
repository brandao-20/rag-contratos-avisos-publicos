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

    def test_objeto_intent(self):
        analysis = analyze_query("Qual é o objeto do contrato?")
        self.assertEqual(analysis.intent, "objeto")

    def test_criterios_intent(self):
        analysis = analyze_query("Que critérios de adjudicação são usados?")
        self.assertEqual(analysis.intent, "criterios")

    def test_caucao_intent(self):
        analysis = analyze_query("Existe prestação de caução?")
        self.assertEqual(analysis.intent, "caucao")

    def test_cpv_intent(self):
        analysis = analyze_query("Qual é o CPV do procedimento?")
        self.assertEqual(analysis.intent, "cpv")

    def test_guardrail(self):
        self.assertTrue(should_force_dont_know("Quem vai ganhar este concurso?"))
        self.assertFalse(should_force_dont_know("Qual é o critério de adjudicação?"))

    def test_query_augmentation_prazo(self):
        analysis = analyze_query("Qual é o prazo para apresentação das propostas?")
        q = augment_query_for_retrieval("Qual é o prazo para apresentação das propostas?", analysis)
        self.assertIn("prazo de execução do contrato", q)

    def test_query_augmentation_valor(self):
        analysis = analyze_query("Qual é o preço base?")
        q = augment_query_for_retrieval("Qual é o preço base?", analysis)
        self.assertIn("preço base", q)

    def test_query_augmentation_cpv(self):
        analysis = analyze_query("Qual é o CPV?")
        q = augment_query_for_retrieval("Qual é o CPV?", analysis)
        self.assertIn("CPV", q)


if __name__ == "__main__":
    unittest.main()
