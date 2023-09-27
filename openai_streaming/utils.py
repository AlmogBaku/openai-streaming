from typing import List, Iterator

from openai.openai_object import OpenAIObject


def stream_to_log(response: Iterator[OpenAIObject]) -> List[OpenAIObject]:
    """
    A utility function to convert a stream to a log.
    :param response: The response stream from OpenAI
    :return: A list of the response stream
    """

    log = []
    for r in response:
        log.append(r)
    return log


def print_stream_log(log: List[OpenAIObject]):
    """
    A utility function to print the log of a stream nicely.
    This is useful for debugging, when you first save the stream to an array and then use it.

    :param log:
    :return:
    """

    log = log.copy()
    content_print = False
    for l in log:
        delta = l["choices"][0]["delta"]
        if "content" in delta:
            if delta["content"] == "" or delta["content"] is None:
                continue
            if not content_print:
                print("> ", end="")
            content_print = True
            print(delta["content"], end="")
        if "function_call" in delta:
            if content_print:
                content_print = False
                print("\n")
            if "name" in delta["function_call"]:
                print(f"{delta['function_call']['name']}(")
            if "arguments" in delta["function_call"]:
                print(delta["function_call"]["arguments"], end="")
        if "finish_reason" in l and l["finish_reason"] == "function_call":
            print(")")
