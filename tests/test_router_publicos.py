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


# ─── Testes de classificação de intenção ──────────────────────────────────────

def test_preco_classifica_valor_nao_criterios():
    """'preço' sozinho deve classificar intent=valor, não criterios (bug crítico corrigido)."""
    from src.query_analysis import classify_intent
    assert classify_intent("Qual é o preço do procedimento?") == "valor"
    assert classify_intent("Qual é o preço base?") == "valor"
    assert classify_intent("Qual o preço?") == "valor"


def test_criterios_classifica_corretamente():
    """'critério de adjudicação' deve classificar intent=criterios."""
    from src.query_analysis import classify_intent
    assert classify_intent("Que critérios de adjudicação são referidos?") == "criterios"
    assert classify_intent("É monofator ou multifator?") == "criterios"


def test_prazo_classifica_corretamente():
    """'prazo' deve classificar intent=prazo."""
    from src.query_analysis import classify_intent
    assert classify_intent("Qual é o prazo de apresentação das propostas?") == "prazo"
    assert classify_intent("Qual é a data limite?") == "prazo"


def test_caucao_classifica_corretamente():
    """'caução' deve classificar intent=caucao."""
    from src.query_analysis import classify_intent
    assert classify_intent("Existe prestação de caução?") == "caucao"
    assert classify_intent("Qual é a garantia exigida?") == "caucao"


def test_lotes_classifica_corretamente():
    """'lotes' deve classificar intent=lotes."""
    from src.query_analysis import classify_intent
    assert classify_intent("O procedimento tem lotes?") == "lotes"


def test_augment_query_nao_usa_pipe():
    """A query aumentada não deve usar '|' (prejudica embeddings vetoriais)."""
    from src.query_analysis import augment_query_for_retrieval, analyze_query
    analysis = analyze_query("Qual é o preço base?")
    augmented = augment_query_for_retrieval("Qual é o preço base?", analysis)
    assert "|" not in augmented, f"Query aumentada não deve conter '|': {augmented!r}"


def test_extractor_caucao_tem_percentagem():
    """Extrator de caução deve incluir percentagem quando presente no texto."""
    from src.extractors import extract_structured_from_docs
    from langchain.schema import Document
    text = (
        "Prestação de caução: Sim\n"
        "Percentagem: 5%\n"
        "Regime: Regime geral\n"
    )
    docs = [Document(page_content=text, metadata={})]
    result = extract_structured_from_docs(docs)
    caucao = result.get("caucao") or ""
    assert "Sim" in caucao, f"Caução deve indicar Sim: {caucao!r}"
    assert "5%" in caucao, f"Caução deve incluir percentagem: {caucao!r}"


def test_extractor_criterios_tem_estrutura():
    """Extrator de critérios deve retornar estrutura Monofator/Multifator."""
    from src.extractors import extract_structured_from_docs
    from langchain.schema import Document
    text = (
        "CRITÉRIO DE ADJUDICAÇÃO\n"
        "Monofator: Não\n"
        "Multifator: Sim\n"
        "Nome: Preço Ponderação: 70%\n"
        "Nome: Qualidade Ponderação: 30%\n"
        "24 - CONDIÇÕES DO CONTRATO\n"
    )
    docs = [Document(page_content=text, metadata={})]
    result = extract_structured_from_docs(docs)
    criterios = result.get("criterios") or ""
    assert "Multifator" in criterios, f"Critérios devem indicar Multifator: {criterios!r}"


def test_field_citations_presente():
    """_field_citations deve estar presente no resultado de extração."""
    from src.extractors import extract_structured_from_docs
    from langchain.schema import Document
    text = "Valor do preço base do procedimento: 50.000,00 EUR\n"
    docs = [Document(page_content=text, metadata={})]
    result = extract_structured_from_docs(docs)
    assert "_field_citations" in result, "Proveniência por campo deve estar presente"
    assert result["_field_citations"].get("valor") is not None, "Campo 'valor' deve ter citation index"

