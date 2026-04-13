"""Core Neuro-Symbolic Agent for solving ARC-AGI tasks."""

import json
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
import numpy as np
import requests
from openai import AsyncOpenAI

from config import config
from prompts import SYSTEM_PROMPT, REASONING_PROMPT_TEMPLATE, REFINEMENT_PROMPT_TEMPLATE
from sandbox import run_verification, run_test_inference, extract_code_from_response


@dataclass
class TaskSolution:
    """Result of solving an ARC task."""

    success: bool
    final_code: Optional[str]
    final_output: Optional[np.ndarray]
    num_retries: int
    error_message: Optional[str]


class NeuroSymbolicAgent:
    """Main agent for solving ARC-AGI tasks using reasoning and verification."""

    def __init__(self):
        """Initialize the agent."""
        self.config = config
        self.llm_client = None
        self._init_llm()

    def _init_llm(self):
        """Initialize the LLM client or local HTTP settings."""
        # support a local LLM endpoint (vLLM, etc.)
        # if config.USE_LOCAL_LLM:
        #     # nothing to initialize, we'll call HTTP directly in _call_llm
        #     self.llm_client = None
        #     return
        
        self.llm_client = AsyncOpenAI(
            api_key=config.LOCAL_LLM_API_KEY,
            base_url=config.LOCAL_LLM_BASE_URL
        )
        self.model = config.LOCAL_LLM_MODEL

        # For now, using a mock LLM. In production, integrate with actual API.
        # Supported: OpenAI, Anthropic, DeepSeek, etc.
        # if config.MODEL_ID != "mock":
        #     try:
        #         import anthropic

        #         self.llm_client = anthropic.Anthropic(api_key=config.API_KEY)
        #     except ImportError:
        #         print(
        #             "Warning: anthropic not installed. Using mock LLM. Install with: pip install anthropic"
        #         )
        #         self.llm_client = None
        # else:
        #     self.llm_client = None

    async def _call_llm(
        self, system_prompt: str, user_message: str
    ) -> Optional[str]:
        """
        Call the LLM with the given prompts.

        Args:
            system_prompt: System role and instructions.
            user_message: The user's message/query.

        Returns:
            The LLM's response, or None if using mock mode.
        """
        print(f'USE LOCAL_LLM: {config.USE_LOCAL_LLM}, MODEL: {config.LOCAL_LLM_MODEL}')
        # local LLM via HTTP
        if config.USE_LOCAL_LLM:
            try:
                '''
                payload = {
                    "model": config.LOCAL_LLM_MODEL,
                    "input": system_prompt + "\n" + user_message,
                    "temperature": config.TEMPERATURE,
                    # other fields may be supported by local server
                }
                headers = {}
                # only include auth header if a non-empty, non-"EMPTY" key is provided
                if config.LOCAL_LLM_API_KEY and config.LOCAL_LLM_API_KEY.strip().upper() not in ("", "EMPTY"):
                    headers["Authorization"] = f"Bearer {config.LOCAL_LLM_API_KEY}"
                resp = requests.post(config.LOCAL_LLM_BASE_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                # assume response text in data["output"] or similar
                if isinstance(data, dict):
                    # try some common keys
                    return data.get("output") or data.get("text") or str(data)
                return str(data)
                '''
            
                response = await self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=config.TEMPERATURE,
                    # max_tokens=self.router_max_tokens,
                )
                content = (response.choices[0].message.content or "").strip()
                return content
            except Exception as e:
                print(f"Local LLM error: {e}")
                return None

        print(f"Calling LLM with system prompt: 2nd time maybe...")
        if self.llm_client is None:
            # Mock mode - return a simple response
            print("[MOCK LLM] Generating response...")
            return self._generate_mock_response(user_message)

        try:
            response = self.llm_client.messages.create(
                model=config.MODEL_ID,
                max_tokens=4096,
                temperature=config.TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"LLM Error: {e}")
            return None

    def _generate_mock_response(self, user_message: str) -> str:
        """Generate a mock response for testing without actual LLM."""
        # Extract shape info if available
        if "Training Examples" in user_message:
            # Simple rule: copy the input
            code = """import numpy as np

def transform(grid):
    # Mock: identity transformation
    return grid
"""
        else:
            code = """import numpy as np

def transform(grid):
    return grid
"""

        response = {
            "perception": "Mock perception analysis",
            "hypothesis_1": "Mock hypothesis 1",
            "hypothesis_2": "Mock hypothesis 2",
            "hypothesis_3": "Mock hypothesis 3",
            "chosen_hypothesis": "Identity transformation",
            "code": code,
            "verification_logic": "Mock verification logic",
        }
        return json.dumps(response)

    def _extract_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract structured JSON from LLM response.

        Args:
            response_text: Raw LLM response.

        Returns:
            Parsed JSON dict, or empty dict if parsing fails.
        """
        # Try to find JSON block
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: treat entire response as potential JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {}

    def _format_examples_for_prompt(self, tasks: list) -> str:
        """Format training examples for the prompt."""
        formatted = []
        for idx, example in enumerate(tasks):
            formatted.append(
                f"**Example {idx + 1}:**\n"
                f"Input shape: {np.array(example['input']).shape}\n"
                f"Input:\n{np.array(example['input'])}\n"
                f"Output shape: {np.array(example['output']).shape}\n"
                f"Output:\n{np.array(example['output'])}\n"
            )
        return "\n".join(formatted)

    async def solve_task(self, task_dict: Dict) -> TaskSolution:
        """
        Solve an ARC-AGI task using the reasoning loop.

        Args:
            task_dict: Task dictionary with 'train' and 'test' keys.
                Format: {
                    'train': [{'input': grid, 'output': grid}, ...],
                    'test': [{'input': grid, 'output': optional_grid}, ...]
                }

        Returns:
            TaskSolution with results.
        """
        train_pairs = task_dict.get("train", [])
        test_cases = task_dict.get("test", [])
        
        # train_pairs = []
        # test_cases = []
        # for task in task_dict:
        #     train_pairs.extend(task.get("train", []))
        #     test_cases.extend(task.get("test", []))
            
        print(f"Number of training examples: {len(train_pairs)}, Number of test cases: {len(test_cases)}")

        if not train_pairs:
            return TaskSolution(
                success=False,
                final_code=None,
                final_output=None,
                num_retries=0,
                error_message="No training examples provided",
            )

        if not test_cases:
            return TaskSolution(
                success=False,
                final_code=None,
                final_output=None,
                num_retries=0,
                error_message="No test cases provided",
            )

        print("\n" + "=" * 70)
        print("NEURO-SYMBOLIC ARC SOLVER")
        print("=" * 70)

        # Step 1: Initial reasoning and code generation
        print("\n[STEP 1] Generating initial hypothesis and code...")
        examples_str = self._format_examples_for_prompt(train_pairs)
        test_input_str = str(np.array(test_cases[0]["input"]))

        user_message = REASONING_PROMPT_TEMPLATE.format(
            examples=examples_str, test_input=test_input_str
        )

        response =  await self._call_llm(SYSTEM_PROMPT, user_message)
        if not response:
            return TaskSolution(
                success=False,
                final_code=None,
                final_output=None,
                num_retries=0,
                error_message="LLM call failed",
            )

        # Parse response
        response_dict = self._extract_json_response(response)
        code = extract_code_from_response(
            response_dict.get("code", "") or response
        )

        print(f"[REASONING] {response_dict.get('perception', 'N/A')[:100]}...")
        print(f"[HYPOTHESIS] {response_dict.get('chosen_hypothesis', 'N/A')[:100]}...")

        # Step 2-4: Verification loop
        retry_count = 0
        while retry_count < self.config.MAX_RETRIES:
            print(f"\n[ATTEMPT {retry_count + 1}] Verifying code...")
            success, error_msg = run_verification(code, train_pairs)

            if success:
                print("✓ Verification PASSED on all training examples!")

                # Step 5: Run on test input
                print("\n[STEP 5] Running on test input...")
                test_input = test_cases[0]["input"]
                result = run_test_inference(code, test_input)

                if isinstance(result, tuple):  # Error case
                    return TaskSolution(
                        success=False,
                        final_code=code,
                        final_output=None,
                        num_retries=retry_count,
                        error_message=result[1],
                    )

                print("✓ Test inference complete!")
                return TaskSolution(
                    success=True,
                    final_code=code,
                    final_output=result,
                    num_retries=retry_count,
                    error_message=None,
                )

            # Verification failed - refine code
            print(f"✗ Verification failed:\n{error_msg}")
            retry_count += 1

            if retry_count >= self.config.MAX_RETRIES:
                return TaskSolution(
                    success=False,
                    final_code=code,
                    final_output=None,
                    num_retries=retry_count,
                    error_message=f"Max retries ({self.config.MAX_RETRIES}) exceeded. Last error: {error_msg}",
                )

            # Request refinement from LLM
            print(f"\n[REFINEMENT] Requesting code refinement from LLM...")

            train_input = np.array(train_pairs[0]["input"])
            expected_output = np.array(train_pairs[0]["output"])

            refinement_message = REFINEMENT_PROMPT_TEMPLATE.format(
                error_message=error_msg,
                input_shape=train_input.shape,
                output_shape=expected_output.shape,
                expected_output=str(expected_output),
                actual_output="(see error)",
                previous_hypothesis=response_dict.get("chosen_hypothesis", ""),
                previous_code=code,
            )

            ref_response = await self._call_llm(SYSTEM_PROMPT, refinement_message)
            if not ref_response:
                return TaskSolution(
                    success=False,
                    final_code=code,
                    final_output=None,
                    num_retries=retry_count,
                    error_message="LLM refinement call failed",
                )

            # Extract refined code
            ref_dict = self._extract_json_response(ref_response)
            new_code = extract_code_from_response(ref_dict.get("code", "") or ref_response)

            if new_code and new_code != code:
                code = new_code
                print(f"[REFINED] Using new code from LLM")
            else:
                return TaskSolution(
                    success=False,
                    final_code=code,
                    final_output=None,
                    num_retries=retry_count,
                    error_message="LLM failed to provide new code in refinement",
                )

        return TaskSolution(
            success=False,
            final_code=code,
            final_output=None,
            num_retries=retry_count,
            error_message="Max retries exceeded",
        )
