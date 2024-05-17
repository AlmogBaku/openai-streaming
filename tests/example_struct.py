import os
from time import sleep

from openai import AsyncOpenAI
import asyncio

from pydantic import BaseModel

from typing import Optional, List
from openai_streaming.struct import BaseHandler, process_struct_response, Terminate

# Initialize OpenAI Client
client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)


class MathProblem(BaseModel):
    steps: List[str]
    answer: Optional[int] = None


# Define handler
class Handler(BaseHandler[MathProblem]):
    async def handle_partially_parsed(self, data: MathProblem) -> Optional[Terminate]:
        if len(data.steps) == 0 and data.answer:
            return Terminate()

        print(f"Steps: {', '.join(data.steps)}", end="\r")
        sleep(0.1)
        if data.answer:
            print(f"\nAnswer: {data.answer}")

    async def terminated(self):
        print("Terminated")


# Invoke OpenAI request
async def main():
    resp = await client.chat.completions.create(
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
        stream=True
    )
    await process_struct_response(resp, Handler(), 'yaml')


# Start the script asynchronously
asyncio.run(main())
