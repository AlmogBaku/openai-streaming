import json
from inspect import getfullargspec
from typing import List, Generator, Tuple, Callable, Optional, Union, Dict, Any, Iterator, AsyncGenerator, Awaitable, \
    Set, AsyncIterator

from openai import AsyncStream, Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from json_streamer import ParseState, loads
from .fn_dispatcher import dispatch_yielded_functions_with_args, o_func

OAIResponse = Union[
    ChatCompletion,
    AsyncStream[ChatCompletionChunk],
    Stream[ChatCompletionChunk],
    Stream[ChatCompletion],
    List[ChatCompletionChunk],
    AsyncGenerator[ChatCompletion, None],
]


class ContentFuncDef:
    """
    A class that represents a Content Function definition: function name, and argument name.
    """

    name: str
    arg: str

    def __init__(self, func: Callable):
        spec = getfullargspec(o_func(func))
        if spec.args[0] == "self":
            spec.args.pop(0)

        if len(spec.args) != 1:
            raise ValueError("content_func must have only one argument (aside to self)")

        if len(spec.annotations) == 1:
            if spec.annotations[spec.args[0]] is not AsyncGenerator[str, None]:
                raise ValueError("content_func must have only one argument of type AsyncGenerator[str, None]")

        self.arg = spec.args[0]
        self.name = func.__name__


def _simplified_generator(
        response: OAIResponse,
        content_fn_def: Optional[ContentFuncDef],
        result: Dict
) -> Callable[[], AsyncGenerator[Tuple[str, Dict], None]]:
    """
    Return an async generator that converts an OpenAI response stream to a simple generator that yields function names
     and their arguments as dictionaries.

    :param response: The response stream
    :param content_fn_def: The content function definition
    :return: A function that returns a generator
    """

    result["role"] = "assistant"

    async def generator() -> AsyncGenerator[Tuple[str, Dict], None]:
        async for r in _process_stream(response, content_fn_def):
            if content_fn_def is not None and r[0] == content_fn_def.name:
                yield content_fn_def.name, {content_fn_def.arg: r[2]}

                if "content" not in result:
                    result["content"] = ""
                result["content"] += r[2]
            else:
                yield r[0], r[2]
                if r[1] == ParseState.COMPLETE:
                    result["function_call"] = {"name": r[0], "arguments": json.dumps(r[2])}

    return generator


class DiffPreprocessor:
    """
    Preprocessor that returns only the difference between the current dictionary and the previous one.
    It is used to convert the parsed JSON stream to a dictionary of the changes, so we can stream the changes to the
    function calls.
    """

    def __init__(self, content_fn: Optional[ContentFuncDef] = None):
        self.content_fn = content_fn
        self.prev_dicts = {}

    def preprocess(self, key, current_dict):
        """
        Preprocesses the current dictionary by returning only the difference between the current dictionary and the
            previous one.
        :param key: The key of the current dictionary, this is usually the function name
        :param current_dict: The current dictionary value to preprocess
        :return: The difference between the current dictionary and the previous one
        """
        if self.content_fn is not None and key == self.content_fn.name:
            return current_dict

        prev_dict = self.prev_dicts.get(key, {})
        diff_dict = {}
        for field_key in current_dict:
            if field_key not in prev_dict:
                diff_dict[field_key] = current_dict[field_key]
            elif current_dict[field_key] != prev_dict[field_key]:
                diff_dict[field_key] = current_dict[field_key][len(prev_dict[field_key]):]
        self.prev_dicts[key] = current_dict
        return diff_dict


async def process_response(
        response: OAIResponse,
        content_func: Optional[Callable[[AsyncGenerator[str, None]], Awaitable[None]]] = None,
        funcs: Optional[List[Callable[[], Awaitable[None]]]] = None,
        self: Optional = None
) -> Tuple[Set[str], Dict[str, Any]]:
    """
    Processes an OpenAI response stream and returns a set of function names that were invoked, and a dictionary contains
     the results of the functions (to be used as part of the message history for the next api request).

    :param response: The response stream from OpenAI
    :param content_func: The function to use for the assistant's text message
    :param funcs: The functions to use when called by the assistant
    :param self: An optional self argument to pass to the functions
    :return: A tuple of the set of function names that were invoked and a dictionary of the results of the functions
    :raises ValueError: If the arguments are invalid
    :raises LookupError: If the response does not contain a delta
    """

    if content_func is None and funcs is None:
        raise ValueError("Must specify either content_func or fns or both")

    # assert content_func signature is Generator[str, None, None]
    content_fn_def = ContentFuncDef(content_func) if content_func is not None else None

    if (not isinstance(response, Iterator) and not isinstance(response, List)
            and not isinstance(response, AsyncIterator) and not isinstance(response, AsyncGenerator)):
        raise ValueError("response must be an iterator (generator's stream from OpenAI or a log as a list)")

    func_map: Dict[str, Callable] = {}
    if funcs is not None:
        for func in funcs:
            func_map[o_func(func).__name__] = func
    if content_fn_def is not None:
        func_map[content_fn_def.name] = content_func

    result = {}
    gen = _simplified_generator(response, content_fn_def, result)
    preprocess = DiffPreprocessor(content_fn_def)
    return await dispatch_yielded_functions_with_args(gen, func_map, preprocess.preprocess, self), result


def _arguments_processor(json_loader=loads) -> Generator[Tuple[ParseState, dict], str, None]:
    """
    A generator that processes a JSON stream and yields the parsed arguments.
    :param json_loader: The JSON loader to use
    :return: A generator that yields the parsed arguments
    """

    loader = json_loader()
    next(loader)

    recv = yield
    while recv is not None:
        try:
            if recv is None or recv == "":
                recv = yield
                continue
            _parsed = loader.send(recv)
            if _parsed is None:
                recv = yield
            while _parsed is not None:
                recv = yield _parsed
                try:
                    _parsed = next(loader)
                except StopIteration:
                    pass
        except StopIteration:
            break


class StreamProcessorState:
    content_fn_def: Optional[ContentFuncDef] = None
    current_processor: Optional[Generator[Tuple[ParseState, dict], str, None]] = None
    current_fn: Optional[str] = None

    def __init__(self, content_fn_def: Optional[ContentFuncDef]):
        self.content_fn_def = content_fn_def


async def _process_stream(
        response: OAIResponse,
        content_fn_def: Optional[ContentFuncDef]
) -> AsyncGenerator[Tuple[str, ParseState, Union[dict, str]], None]:
    """
    Processes an OpenAI response stream and yields the function name, the parse state and the parsed arguments.
    :param response: The response stream from OpenAI
    :param content_fn_def: The content function definition
    :return: A generator that yields the function name, the parse state and the parsed arguments
    """

    state = StreamProcessorState(content_fn_def=content_fn_def)
    if isinstance(response, AsyncGenerator) or isinstance(response, AsyncIterator):
        async for message in response:
            for res in _process_message(message, state):
                yield res
    else:
        for message in response:
            for res in _process_message(message, state):
                yield res


def _process_message(
        message: ChatCompletionChunk,
        state: StreamProcessorState
) -> Generator[Tuple[str, ParseState, Union[dict, str]], None, None]:
    """
    This function processes the responses as they arrive from OpenAI, and transforms them as a generator of
    partial objects
    :param message: the message from OpenAI
    :param state: The processing state
    :return: Generator
    """
    choice = message.choices[0]
    if not choice.model_fields.get("delta"):
        raise LookupError("No delta in choice")

    delta = message.choices[0].delta
    if delta.function_call or delta.tool_calls:
        func = delta.function_call or delta.tool_calls[0].function
        if func.name:
            if state.current_processor is not None:
                state.current_processor.close()
            state.current_fn = func.name
            state.current_processor = _arguments_processor()
            next(state.current_processor)
        if func.arguments:
            arg = func.arguments
            ret = state.current_processor.send(arg)
            if ret is not None:
                yield state.current_fn, ret[0], ret[1]
    if delta.content:
        if delta.content is None or delta.content == "":
            return
        if state.content_fn_def is not None:
            yield state.content_fn_def.name, ParseState.PARTIAL, delta.content
        else:
            yield None, ParseState.PARTIAL, delta.content
    if message.choices[0].finish_reason and (
            message.choices[0].finish_reason == "function_call" or message.choices[0].finish_reason == "tool_calls"
    ):
        if state.current_processor is not None:
            state.current_processor.close()
            state.current_processor = None
        state.current_fn = None
