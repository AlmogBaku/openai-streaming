from collections.abc import AsyncGenerator
from inspect import iscoroutinefunction, signature
from types import FunctionType
from typing import Generator, get_origin, Union, Optional, Any, get_type_hints
from typing import get_args

from docstring_parser import parse
from openai.types.beta.assistant import ToolFunction
from openai.types.shared import FunctionDefinition
from pydantic import create_model


def openai_streaming_function(func: FunctionType) -> Any:
    """
    Decorator that creates an OpenAI Schema for your function, while support using Generators for Streaming.
    
    To document your function (so the model will know how to use it), simply use docstring.
    Using standard docstring styles will also allow you to document your argument's description

    :Example:
    ```python
    @openai_streaming_function
    async def error_message(typ: str, description: AsyncGenerator[str, None]):
        \"""
        You MUST use this function when requested to do something that you cannot do.
    
        :param typ: The error's type
        :param description: The error description
        \"""
        pass
    ```

    :param func: The function to convert
    :return: Your function with additional attribute `openai_schema`
    """
    if not iscoroutinefunction(func):
        raise ValueError("openai_streaming only supports async functions.")

    type_hints = get_type_hints(func)
    for key, val in type_hints.items():

        args = get_args(val)

        # Unpack optionals
        optional = False
        if val is Optional or (get_origin(val) is Union and len(args) == 2 and args[1] is type(None)):
            optional = True
            val = args[0]
            args = get_args(val)

        if get_origin(val) is get_origin(Generator):
            raise ValueError("openai_streaming does not support `Generator` type, instead use `AsyncGenerator`.")
        if get_origin(val) is AsyncGenerator:
            val = args[0]

        if optional:
            val = Optional[val]

        type_hints[key] = val

    # Prepare fields for the dynamic model
    fields = {
        param.name: (type_hints[param.name], ...)
        for param in signature(func).parameters.values()
        if param.name in type_hints
    }

    # Create a Pydantic model dynamically
    model = create_model(func.__name__, **fields)

    # parse the function docstring
    docstring = parse(func.__doc__ or "")

    # prepare the parameters(arguments)
    parameters = model.model_json_schema()

    # extract parameter documentations from the docstring
    for param in docstring.params:
        if (name := param.arg_name) in parameters["properties"] and (description := param.description):
            parameters["properties"][name]["description"] = description

    func.openai_schema = ToolFunction(type='function', function=FunctionDefinition(
        name=func.__name__,
        description=docstring.short_description,
        parameters=parameters,
    ))

    return func
