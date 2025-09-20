import os
import json
from typing import Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate


class LLMService:
    def __init__(self):
        self.model_name = 'gemini-1.5-pro'
        # API key will be set at runtime via environment or admin settings

    async def generate_test_cases(self, source_text: str, max_cases: int, enable_followups: bool) -> Dict[str, Any]:
        prompt = self._build_generation_prompt(source_text, max_cases)
        llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.2)
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        parsed = self._safe_parse_json(content)

        if not parsed:
            parsed = {'testCases': []}

        if enable_followups and (not parsed.get('testCases') or len(parsed.get('testCases', [])) < 3):
            followups = self._propose_followups(source_text)
            return {'followUpQuestions': followups}

        return parsed

    async def generate_refined_test_cases(
        self,
        source_text: str,
        questions: List[str],
        answers_map: Dict[str, str],
        max_cases: int
    ) -> Dict[str, Any]:
        qa_pairs = []
        for idx, q in enumerate(questions):
            a = answers_map.get(str(idx), '') or answers_map.get(idx) or ''
            qa_pairs.append(f'Q: {q} A: {a}')
        qa_block = '\n'.join(qa_pairs)

        prompt = self._build_refinement_prompt(source_text, qa_block, max_cases)
        llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.2)
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        parsed = self._safe_parse_json(content)

        if not parsed:
            parsed = {'testCases': []}

        return parsed

    def _build_generation_prompt(self, source_text: str, max_cases: int) -> str:
        instructions = (
            f"You are a senior QA engineer for healthcare software. "
            f"Generate a diverse suite of test cases (positive, negative, edge cases) with realistic test data. "
            f"Focus on HIPAA, PHI handling, consent, audit logging, roles, clinical safety, interoperability (HL7/FHIR), and input validation. "
            f"Return ONLY a valid JSON object with a top-level key 'testCases' which is an array of objects. "
            f"Each object must have fields: testCaseId, title, description, testSteps (array of strings), "
            f"expectedResults, priority (P1/P2/P3). "
            f"Use at most {max_cases} test cases. Use readable IDs like TC-001, TC-002."
        )

        example = '''{
  "testCases": [
    {
      "testCaseId": "TC-001",
      "title": "Example",
      "description": "...",
      "testSteps": ["step 1", "step 2"],
      "expectedResults": "...",
      "priority": "P2"
    }
  ]
}'''

        prompt = (
            f"{instructions}\n\n"
            f"Context:\n{source_text[:12000]}\n\n"
            f"JSON Schema and Example:\n{example}\n\n"
            f"Return only JSON with no extra text."
        )

        return prompt

    def _build_refinement_prompt(self, source_text: str, qa_block: str, max_cases: int) -> str:
        instructions = (
            f"Refine and regenerate the healthcare QA test cases based on additional clarifications below. "
            f"Return ONLY JSON with top-level key 'testCases'. Maintain the same schema. "
            f"Ensure coverage of both normal and failure paths, boundary conditions, and compliance aspects. "
            f"Use at most {max_cases} test cases."
        )

        prompt = (
            f"{instructions}\n\n"
            f"Context:\n{source_text[:12000]}\n\n"
            f"Clarifications:\n{qa_block}\n\n"
            f"Return only JSON."
        )

        return prompt

    def _propose_followups(self, source_text: str) -> List[str]:
        return [
            "What user roles and permissions need to be covered (e.g., clinician, admin, patient)?",
            "What environments or integrations are in scope (e.g., FHIR server, EHR vendor, external IDP)?",
            "Any regulatory constraints or organizational policies we must validate beyond HIPAA (e.g., SOC2, ISO 27001)?"
        ]

    def _safe_parse_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                snippet = text[start:end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    return None
            return None
