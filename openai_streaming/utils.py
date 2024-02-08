from typing import List, Iterator, Union, AsyncIterator, AsyncGenerator

from openai.types.chat import ChatCompletion, ChatCompletionChunk

OAIResponse = Union[ChatCompletion, ChatCompletionChunk]


async def stream_to_log(response: Union[Iterator[OAIResponse], AsyncIterator[OAIResponse]]) -> List[OAIResponse]:
    """
    A utility function to convert a stream to a log.
    :param response: The response stream from OpenAI
    :return: A list of the response stream
    """

    log = []
    if isinstance(response, AsyncGenerator) or isinstance(response, AsyncIterator):
        async for r in response:
            log.append(r)
    else:
        for r in response:
            log.append(r)
    return log


async def print_stream_log(log: List[OAIResponse]):
    """
    A utility function to print the log of a stream nicely.
    This is useful for debugging, when you first save the stream to an array and then use it.

    :param log:
    :return:
    """

    if isinstance(log, AsyncGenerator) or isinstance(log, AsyncIterator):
        log = await stream_to_log(log)

    log = log.copy()
    content_print = False
    for l in log:
        delta = l.choices[0].delta
        if delta.content:
            if delta.content == "" or delta.content is None:
                continue
            if not content_print:
                print("> ", end="")
            content_print = True
            print(delta.content, end="")
        if delta.function_call:
            if content_print:
                content_print = False
                print("\n")
            if delta.function_call.name:
                print(f"{delta.function_call.name}(")
            if delta.function_call.arguments:
                print(delta.function_call.arguments, end="")
        if delta.tool_calls:
            for call in delta.tool_calls:
                if call.function:
                    if content_print:
                        content_print = False
                        print("\n")
                    if call.function.name:
                        print(f"{call.function.name}(")
                    if call.function.arguments:
                        print(call.function.arguments, end="")
        if (l.choices[0].finish_reason and l.choices[0].finish_reason == "function_call" or
                l.choices[0].finish_reason == "tool_calls"):
            print(")")


async def logs_to_response(logs: List[OAIResponse]) -> AsyncGenerator[OAIResponse, None]:
    for item in logs:
        yield ChatCompletionChunk(**item)
