# MIT License
#
# Copyright (c) 2023 Jason Liu
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
# Since the original project has taken a huge pivot and provide many unnecessary features - this is a stripped version
# of the openai_function decorator copied from
# https://github.com/jxnl/instructor/blob/0.2.8/instructor/function_calls.py

import json
from docstring_parser import parse
from functools import wraps
from typing import Any, Callable
from pydantic import validate_arguments


def _remove_a_key(d, remove_key) -> None:
    """Remove a key from a dictionary recursively"""
    if isinstance(d, dict):
        for key in list(d.keys()):
            if key == remove_key and "type" in d.keys():
                del d[key]
            else:
                _remove_a_key(d[key], remove_key)


class openai_function:
    """
    Decorator to convert a function into an OpenAI function.

    This decorator will convert a function into an OpenAI function. The
    function will be validated using pydantic and the schema will be
    generated from the function signature.

    Example:
        ```python
        @openai_function
        def sum(a: int, b: int) -> int:
            return a + b

        completion = openai.ChatCompletion.create(
            ...
            messages=[{
                "content": "What is 1 + 1?",
                "role": "user"
            }]
        )
        sum.from_response(completion)
        # 2
        ```
    """

    def __init__(self, func: Callable) -> None:
        self.func = func
        self.validate_func = validate_arguments(func)
        self.docstring = parse(self.func.__doc__ or "")

        parameters = self.validate_func.model.model_json_schema()
        parameters["properties"] = {
            k: v
            for k, v in parameters["properties"].items()
            if k not in ("v__duplicate_kwargs", "args", "kwargs")
        }
        for param in self.docstring.params:
            if (name := param.arg_name) in parameters["properties"] and (
                    description := param.description
            ):
                parameters["properties"][name]["description"] = description
        parameters["required"] = sorted(
            k for k, v in parameters["properties"].items() if not "default" in v
        )
        _remove_a_key(parameters, "additionalProperties")
        _remove_a_key(parameters, "title")
        self.openai_schema = {
            "name": self.func.__name__,
            "description": self.docstring.short_description,
            "parameters": parameters,
        }
        self.model = self.validate_func.model

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        @wraps(self.func)
        def wrapper(*args, **kwargs):
            return self.validate_func(*args, **kwargs)

        return wrapper(*args, **kwargs)

    def from_response(self, completion, throw_error=True):
        """
        Parse the response from OpenAI's API and return the function call

        Parameters:
            completion (openai.ChatCompletion): The response from OpenAI's API
            throw_error (bool): Whether to throw an error if the response does not contain a function call

        Returns:
            result (any): result of the function call
        """
        message = completion["choices"][0]["message"]

        if throw_error:
            assert "function_call" in message, "No function call detected"
            assert (
                    message["function_call"]["name"] == self.openai_schema["name"]
            ), "Function name does not match"

        function_call = message["function_call"]
        arguments = json.loads(function_call["arguments"], strict=False)
        return self.validate_func(**arguments)
