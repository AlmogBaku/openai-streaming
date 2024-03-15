import os
from time import sleep

from openai import AsyncOpenAI
import asyncio

from pydantic import BaseModel

from typing import Optional
from openai_streaming.struct import BaseHandler, process_struct_response, Terminate

# Initialize OpenAI Client
client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)


class Letter(BaseModel):
    title: str
    to: Optional[str] = None
    content: Optional[str] = None


# Define handler
class Handler(BaseHandler):
    def model(self):
        return Letter

    last_content = ""

    async def handle_partially_parsed(self, data: Letter) -> Optional[Terminate]:
        if data.to and data.to.lower() != "larry":
            print("You can only write a letter to Larry")
            return Terminate()
        if data.content:
            # here we mingle with the content a bit for the sake of the animation
            data.content = data.content[len(self.last_content):]
            self.last_content = self.last_content + data.content
            print(data.content, end="")
            sleep(0.1)

    async def terminated(self):
        print("Terminated")


# Invoke Function in a streaming request
async def main():
    # Request and process stream
    resp = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{
            "role": "system",
            "content":
                "You are a letter writer able to communicate only with VALID YAML. "
                "You must include only these fields: title, to, content."
                "ONLY write the YAML, without any other text or wrapping it in a code block."
        }, {"role": "user", "content":
            "Write a SHORT letter to my friend Larry congratulating him for his newborn baby Lily."
            "It should be funny and rhythmic. It MUST be very short!"
            }],
        stream=True
    )
    await process_struct_response(resp, Handler(), 'yaml')


# Start the script asynchronously
asyncio.run(main())
