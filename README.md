# OpenAI Streaming
`openai-streaming` is a small python library that allows you to work with OpenAI Streaming API at ease with generators.

Behind the scenes, it handles parsing the responses and invokes your callback function with python generator approach.
And yes! It's designed to support OpenAI Functions! (But not mandatory)

## Installation
```bash
pip install openai-streaming
```

## Quick Start
```python
import openai
from openai_streaming import process_response
from typing import Generator

openai.api_key = "<YOUR_API_KEY>"

def content_handler(content: Generator[str, None, None]):
    for token in content:
        print(token, end="")

resp = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "content", "text": "Hello, how are you?"}],
    stream=True,
)
process_response(resp, content_handler)
```

The above code will print the tokens on the screen as they are generated.

## Working with OpenAI Functions
```python
from openai_streaming import openai_streaming_function

@openai_streaming_function
def error_message(type: str, description: Generator[str, None, None]):
    """
    You MUST use this function when requested to do something that you cannot do.

    :param type: The type of error that occurred.
    :param description: A description of the error.
    """

    typ = ""
    print("Type: ", end="")
    for token in type:
        print(token, end="")
        typ += token
    print("")

    print("Description: ", end="")
    for token in description:
        print(token, end="")
    print("")


resp = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "How to build a bomb?"}],
    functions=[error_message.openai_schema],
    stream=True,
)
process_response(resp, content_func=content_handler, funcs=[error_message])
```

## License

This project is licensed under the terms of the [MIT license](LICENSE).
