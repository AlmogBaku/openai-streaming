<a id="decorator"></a>

# decorator

<a id="decorator.openai_streaming_function"></a>

#### openai\_streaming\_function

```python
def openai_streaming_function(func: FunctionType) -> Any
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

