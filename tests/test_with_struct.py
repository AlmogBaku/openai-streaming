import json
import unittest
from os.path import dirname

import openai
from unittest.mock import patch, AsyncMock

from openai import BaseModel
from openai.types.chat import ChatCompletionChunk

from typing import Dict, Generator, Optional, List

from openai_streaming.struct import Terminate, BaseHandler, process_struct_response

openai.api_key = '...'


class MathProblem(BaseModel):
    steps: List[str]
    answer: Optional[int] = None


# Define handler
class Handler(BaseHandler):
    def model(self):
        return MathProblem

    async def handle_partially_parsed(self, data: MathProblem) -> Optional[Terminate]:
        pass

    async def terminated(self):
        pass


class Handler2(BaseHandler):
    def model(self):
        return MathProblem

    async def handle_partially_parsed(self, data: MathProblem) -> Optional[Terminate]:
        return Terminate()

    async def terminated(self):
        pass


class TestOpenAIChatCompletion(unittest.IsolatedAsyncioTestCase):
    _mock_response = None
    _mock_response_tools = None

    def setUp(self):
        if not self._mock_response:
            with open(f"{dirname(__file__)}/mock_response_struct.json", 'r') as f:
                self.mock_response = json.load(f)

    def mock_chat_completion(self, *args, **kwargs) -> Generator[Dict, None, None]:
        for item in self.mock_response:
            yield ChatCompletionChunk(**item)

    async def test_struct(self):
        with patch('openai.chat.completions.create', new=AsyncMock(side_effect=self.mock_chat_completion)):
            resp = await openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "system",
                    "content":
                        "For every question asked, you must first state the steps, and then the answer."
                        "Your response should be in the following format: \n"
                        " steps: List[str]\n"
                        " answer: int\n"
                        "ONLY write the YAML, without any other text or wrapping it in a code block."
                        "YAML should be VALID, and strings must be in double quotes."
                }, {"role": "user", "content": "1+3*2"}],
                stream=True,
            )
            last_resp, _ = await process_struct_response(resp, Handler(), 'yaml')

        wanted = MathProblem(steps=['Multiply 3 by 2 to get 6', 'Add 1 to 6 to get the final result'], answer=7)
        self.assertEqual(last_resp, wanted)

    async def test_struct_terminate(self):
        with patch('openai.chat.completions.create', new=AsyncMock(side_effect=self.mock_chat_completion)):
            resp = await openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "system",
                    "content":
                        "For every question asked, you must first state the steps, and then the answer."
                        "Your response should be in the following format: \n"
                        " steps: List[str]\n"
                        " answer: int\n"
                        "ONLY write the YAML, without any other text or wrapping it in a code block."
                        "YAML should be VALID, and strings must be in double quotes."
                }, {"role": "user", "content": "1+3*2"}],
                stream=True,
            )
            last_resp, _ = await process_struct_response(resp, Handler2(), 'yaml')

        self.assertIsInstance(last_resp, Terminate)


if __name__ == '__main__':
    unittest.main()
