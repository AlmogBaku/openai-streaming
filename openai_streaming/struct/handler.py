from typing import Protocol, Literal, AsyncGenerator, Optional, Type, TypeVar, Union, Dict, Any, Tuple

from pydantic import BaseModel

from json_streamer import Parser, JsonParser
from .yaml_parser import YamlParser
from ..stream_processing import OAIResponse, process_response

TModel = TypeVar('TModel', bound=BaseModel)


class Terminate:
    pass


class BaseHandler(Protocol[TModel]):
    """
    The base handler for the structured response from OpenAI.
    """

    def model(self) -> Type[TModel]:
        """
        The Pydantic Data Model that we parse
        :return: type of the Pydantic model
        """
        pass

    async def handle_partially_parsed(self, data: TModel) -> Optional[Terminate]:
        """
        Handle partially parsed model
        :param data: The partially parsed object
        :return: None or Terminate if we want to terminate the parsing
        """
        pass

    async def terminated(self):
        """
        Called when the parsing was terminated
        """


OutputSerialization = Literal["json", "yaml"]


class _ContentHandler:
    parser: Parser = None
    _last_resp: Optional[Union[TModel, Terminate]] = None

    def __init__(self, handler: BaseHandler, output_serialization: OutputSerialization = "yaml"):
        self.handler = handler
        if output_serialization == "json":
            self.parser = JsonParser()
        elif output_serialization == "yaml":
            self.parser = YamlParser()

    async def handle_content(self, content: AsyncGenerator[str, None]):
        """
        Handle the content of the response from OpenAI.
        :param content: A generator that yields the content of the response from OpenAI
        :return: None
        """

        loader = self.parser()  # create a Streaming loader
        next(loader)

        last_resp = None

        async for token in content:
            parsed = loader.send(token)  # send the token to the JSON loader
            while parsed:  # loop until through the parsed parts as the loader yields them
                last_resp = await self._handle_parsed(parsed[1])  # handle the parsed dict of the response
                if isinstance(last_resp, Terminate):
                    break
                try:
                    parsed = next(loader)
                except StopIteration:
                    break
            if isinstance(last_resp, Terminate):
                break

        if not last_resp:
            return
        if isinstance(last_resp, Terminate):
            await self.handler.terminated()

        self._last_resp = last_resp

    async def _handle_parsed(self, part) -> Optional[Union[TModel, Terminate]]:
        """
        Handle a parsed part of the response from OpenAI.
        It parses the "parsed dictionary" as a type of `TModel` object and processes it with the handler.

        :param part: A dictionary containing the parsed part of the response
        :return: The parsed part of the response as an `TModel` object, `Terminate` to terminate the handling,
        or `None` if the part is not valid
        """
        try:
            parsed = self.handler.model()(**part)
        except (TypeError, ValueError):
            return

        ret = await self.handler.handle_partially_parsed(parsed)
        return ret if ret else parsed

    def get_last_response(self) -> Optional[Union[TModel, Terminate]]:
        """
        Get the last response from OpenAI.
        :return: The last response from OpenAI
        """
        return self._last_resp


async def process_struct_response(
        response: OAIResponse,
        handler: BaseHandler,
        output_serialization: OutputSerialization = "json"
) -> Tuple[Optional[Union[TModel, Terminate]], Dict[str, Any]]:
    """
    Process the structured response from OpenAI.
    This is useful when we want to parse a structured response from OpenAI in streaming mode. For example: our response
    contains reasoning, and content - but we want to stream only the content to the user.

    :param response: The response from OpenAI
    :param handler: The handler for the response. It should be a subclass of `BaseHandler`
    :param output_serialization: The output serialization of the response. It should be either "json" or "yaml"
    :return: A tuple of the last parsed response, and a dictionary containing the OpenAI response
    """

    handler = _ContentHandler(handler, output_serialization)
    _, result = await process_response(response, handler.handle_content, self=handler)
    if not handler.get_last_response():
        raise ValueError("Probably invalid response from OpenAI")

    return handler.get_last_response(), result
