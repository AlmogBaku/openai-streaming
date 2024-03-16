<a id="decorator"></a>

# decorator

<a id="decorator.OpenAIStreamingFunction"></a>

## OpenAIStreamingFunction Objects

```python
class OpenAIStreamingFunction(Protocol)
```

A Protocol that represents a function that can be used with OpenAI Streaming.

<a id="decorator.OpenAIStreamingFunction.openai_schema"></a>

#### openai\_schema

The OpenAI Schema for the function.

<a id="decorator.openai_streaming_function"></a>

#### openai\_streaming\_function

```python
def openai_streaming_function(func: F) -> OpenAIStreamingFunction
```

Decorator that creates an OpenAI Schema for your function, while support using Generators for Streaming.

To document your function (so the model will know how to use it), simply use docstring.
Using standard docstring styles will also allow you to document your argument's description

**Arguments**:

- `func`: The function to convert

**Returns**:

Your function with additional attribute `openai_schema`

<a id="utils"></a>

# utils

<a id="utils.stream_to_log"></a>

#### stream\_to\_log

```python
async def stream_to_log(
    response: Union[Iterator[OAIResponse], AsyncIterator[OAIResponse]]
) -> List[OAIResponse]
```

A utility function to convert a stream to a log.

**Arguments**:

- `response`: The response stream from OpenAI

**Returns**:

A list of the response stream

<a id="utils.print_stream_log"></a>

#### print\_stream\_log

```python
async def print_stream_log(log: List[OAIResponse])
```

A utility function to print the log of a stream nicely.

This is useful for debugging, when you first save the stream to an array and then use it.

**Arguments**:

- `log`: 

<a id="stream_processing"></a>

# stream\_processing

<a id="stream_processing.ContentFuncDef"></a>

## ContentFuncDef Objects

```python
class ContentFuncDef()
```

A class that represents a Content Function definition: function name, and argument name.

<a id="stream_processing.DiffPreprocessor"></a>

## DiffPreprocessor Objects

```python
class DiffPreprocessor()
```

Preprocessor that returns only the difference between the current dictionary and the previous one.
It is used to convert the parsed JSON stream to a dictionary of the changes, so we can stream the changes to the
function calls.

<a id="stream_processing.DiffPreprocessor.preprocess"></a>

#### preprocess

```python
def preprocess(key, current_dict)
```

Preprocesses the current dictionary by returning only the difference between the current dictionary and the

previous one.

**Arguments**:

- `key`: The key of the current dictionary, this is usually the function name
- `current_dict`: The current dictionary value to preprocess

**Returns**:

The difference between the current dictionary and the previous one

<a id="stream_processing.process_response"></a>

#### process\_response

```python
async def process_response(
        response: OAIResponse,
        content_func: Optional[Callable[[AsyncGenerator[str, None]],
                                        Awaitable[None]]] = None,
        funcs: Optional[List[Callable[[], Awaitable[None]]]] = None,
        self: Optional = None) -> Tuple[Set[str], Dict[str, Any]]
```

Processes an OpenAI response stream and returns a set of function names that were invoked, and a dictionary contains

the results of the functions (to be used as part of the message history for the next api request).

**Arguments**:

- `response`: The response stream from OpenAI
- `content_func`: The function to use for the assistant's text message
- `funcs`: The functions to use when called by the assistant
- `self`: An optional self argument to pass to the functions

**Raises**:

- `ValueError`: If the arguments are invalid
- `LookupError`: If the response does not contain a delta

**Returns**:

A tuple of the set of function names that were invoked and a dictionary of the results of the functions

<a id="fn_dispatcher"></a>

# fn\_dispatcher

<a id="fn_dispatcher.o_func"></a>

#### o\_func

```python
def o_func(func)
```

Returns the original function from a function that has been wrapped by a decorator (that preserves the original

function in the func attribute).

**Arguments**:

- `func`: 

<a id="fn_dispatcher.dispatch_yielded_functions_with_args"></a>

#### dispatch\_yielded\_functions\_with\_args

```python
async def dispatch_yielded_functions_with_args(
        gen: Callable[[], AsyncGenerator[Tuple[str, Dict], None]],
        funcs: Union[List[Callable], Dict[str, Callable]],
        dict_preprocessor: Optional[Callable[[str, Dict], Dict]],
        self: Optional = None) -> Set[str]
```

Dispatches function calls from a generator that yields function names and arguments to the functions.

**Arguments**:

- `gen`: The generator that yields function names and arguments
- `funcs`: The functions to dispatch to
- `dict_preprocessor`: A function that takes a function name and a dictionary of arguments and returns a new
dictionary of arguments
- `self`: An optional self argument to pass to the functions

**Returns**:

A set of function names that were invoked

<a id="struct.handler"></a>

# struct.handler

<a id="struct.handler.BaseHandler"></a>

## BaseHandler Objects

```python
class BaseHandler(Protocol[TModel])
```

The base handler for the structured response from OpenAI.

<a id="struct.handler.BaseHandler.model"></a>

#### model

```python
def model() -> Type[TModel]
```

The Pydantic Data Model that we parse

**Returns**:

type of the Pydantic model

<a id="struct.handler.BaseHandler.handle_partially_parsed"></a>

#### handle\_partially\_parsed

```python
async def handle_partially_parsed(data: TModel) -> Optional[Terminate]
```

Handle partially parsed model

**Arguments**:

- `data`: The partially parsed object

**Returns**:

None or Terminate if we want to terminate the parsing

<a id="struct.handler.BaseHandler.terminated"></a>

#### terminated

```python
async def terminated()
```

Called when the parsing was terminated

<a id="struct.handler.process_struct_response"></a>

#### process\_struct\_response

```python
async def process_struct_response(
    response: OAIResponse,
    handler: BaseHandler,
    output_serialization: OutputSerialization = "json"
) -> Tuple[Optional[Union[TModel, Terminate]], Dict[str, Any]]
```

Process the structured response from OpenAI.

This is useful when we want to parse a structured response from OpenAI in streaming mode. For example: our response
contains reasoning, and content - but we want to stream only the content to the user.

**Arguments**:

- `response`: The response from OpenAI
- `handler`: The handler for the response. It should be a subclass of `BaseHandler`
- `output_serialization`: The output serialization of the response. It should be either "json" or "yaml"

**Returns**:

A tuple of the last parsed response, and a dictionary containing the OpenAI response

<a id="struct.yaml_parser"></a>

# struct.yaml\_parser

<a id="struct.yaml_parser.YamlParser"></a>

## YamlParser Objects

```python
class YamlParser(Parser)
```

Parse partial YAML

