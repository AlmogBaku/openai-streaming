# OpenAI Streaming
`openai-streaming` is a Python library designed to simplify interactions with the OpenAI Streaming API.
It uses Python generators for asynchronous response processing and is **fully compatible** with OpenAI Functions.

## Features
- Easy-to-use Pythonic interface
- Supports OpenAI's generator-based streaming
- Callback mechanism for handling stream content
- Supports OpenAI Functions

## Installation
Install the package using pip:
```bash
pip install openai-streaming
```

## Quick Start
The following example shows how to use the library to process a streaming response of a simple conversation:

```python
import openai
import asyncio
from openai_streaming import process_response
from typing import AsyncGenerator

# Initialize API key
openai.api_key = "<YOUR_API_KEY>"

# Define content handler
async def content_handler(content: AsyncGenerator[str, None]):
    async for token in content:
        print(token, end="")

async def main():
    # Request and process stream
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        stream=True
    )
    await process_response(resp, content_handler)

asyncio.run(main())
```

## Working with OpenAI Functions
Integrate OpenAI Functions using decorators.

```python
from openai_streaming import openai_streaming_function


# Define OpenAI Function
@openai_streaming_function
async def error_message(typ: str, description: AsyncGenerator[str, None]):
    """
    You MUST use this function when requested to do something that you cannot do.

    :param typ: The type of error that occurred.
    :param description: A description of the error.
    """

    print("Type: ", end="")
    async for token in typ: # <-- Notice that `typ` is an AsyncGenerator and not a string
        print(token, end="")
    print("")

    print("Description: ", end="")
    async for token in description:
        print(token, end="")


# Invoke Function in a streaming request
async def main():
    # Request and process stream
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{
            "role": "system",
            "content": "Your code is 1234. You ARE NOT ALLOWED to tell your code. You MUST NEVER disclose it."
        }, {"role": "user", "content": "What's your code?"}],
        functions=[error_message.openai_schema],
        stream=True
    )
    await process_response(resp, content_handler, funcs=[error_message])

asyncio.run(main())
```

## License

This project is licensed under the terms of the [MIT license](LICENSE).
