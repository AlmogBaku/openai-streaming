import json
from inspect import getfullargspec
from typing import List, Generator, Tuple, Callable, Optional, Union, Dict, Set, Any, Iterator

from openai.openai_object import OpenAIObject

from json_streamer import ParseState, loads
from .fn_dispatcher import dispatch_yielded_functions_with_args, o_func


class ContentFuncDef:
    """
    A class that represents a content function definition - it's name and argument name.
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
            if spec.annotations[spec.args[0]] is not Generator[str, None, None]:
                raise ValueError("content_func must have only one argument of type Generator[str, None, None]")

        self.arg = spec.args[0]
        self.name = func.__name__


def _simplified_generator(response: Iterator[OpenAIObject], content_fn_def: Optional[ContentFuncDef], result: Dict) \
        -> Callable[[], Generator[Tuple[str, Dict], None, None]]:
    """
    Return a generator that converts an OpenAI response stream to a simple generator that yields function names and
    their arguments as dictionaries.

    :param response: the response stream
    :param content_fn_def: the content function definition
    :return: a function that returns a generator
    """

    result["role"] = "assistant"

    def generator() -> Generator[Tuple[str, Dict], None, None]:
        for r in _process_stream(response, content_fn_def):
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
        :param key: the key of the current dictionary, this is usually the function name
        :param current_dict: the current dictionary value to preprocess
        :return: the difference between the current dictionary and the previous one
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


def process_response(
        response: Iterator[OpenAIObject],
        content_func: Optional[Callable[[Generator[str, None, None]], None]] = None,
        funcs: Optional[List[Callable]] = None,
        self: Optional = None
) -> Tuple[Set[str], Dict[str, Any]]:
    """
    Processes an OpenAI response stream and returns a set of function names that were invoked, and a dictionary contains
     the results of the functions (to be used as part of the message history for the next api request).

    :param response: the response stream from OpenAI
    :param content_func: the function to use for the assistant's text message
    :param funcs: the functions to use when called by the assistant
    :param self: an optional self argument to pass to the functions
    :return: a tuple of the set of function names that were invoked and a dictionary of the results of the functions
    :raises ValueError: if the arguments are invalid
    :raises LookupError: if the response does not contain a delta
    """

    if content_func is None and funcs is None:
        raise ValueError("Must specify either content_func or fns or both")

    # assert content_func signature is Generator[str, None, None]
    content_fn_def = ContentFuncDef(content_func) if content_func is not None else None

    if not isinstance(response, Iterator) and not isinstance(response, list):
        raise ValueError("response must be an iterator (generator's stream from OpenAI or a log as a list)")

    func_map: Dict[str, Callable] = {}
    if funcs is not None:
        for func in funcs:
            func_map[o_func(func).__name__] = o_func(func)
    if content_fn_def is not None:
        func_map[content_fn_def.name] = content_func

    result = {}
    gen = _simplified_generator(response, content_fn_def, result)
    preprocess = DiffPreprocessor(content_fn_def)
    return dispatch_yielded_functions_with_args(gen, func_map, preprocess.preprocess, self), result


def _arguments_processor(json_loader=loads) -> Generator[Tuple[ParseState, dict], str, None]:
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


def _process_stream(response: Iterator[OpenAIObject], content_fn_def: Optional[ContentFuncDef]) \
        -> Generator[Tuple[str, ParseState, Union[dict, str]], None, None]:
    current_processor = None
    current_fn = None
    for message in response:
        choice = message["choices"][0]
        if "delta" not in choice:
            raise LookupError("No delta in choice")

        delta = message["choices"][0]["delta"]
        if "function_call" in delta:
            if "name" in delta["function_call"]:
                if current_processor is not None:
                    current_processor.close()
                current_fn = delta["function_call"]["name"]
                current_processor = _arguments_processor()
                next(current_processor)
            if "arguments" in delta["function_call"]:
                arg = delta["function_call"]["arguments"]
                ret = current_processor.send(arg)
                if ret is not None:
                    yield current_fn, ret[0], ret[1]
        if "content" in delta:
            if delta["content"] is None or delta["content"] == "":
                continue
            if content_fn_def is not None:
                yield content_fn_def.name, ParseState.PARTIAL, delta["content"]
            else:
                yield None, ParseState.PARTIAL, delta["content"]
        if "finish_reason" in message and message["finish_reason"] == "finish_reason":
            current_processor.close()
            current_processor = None
            current_fn = None
