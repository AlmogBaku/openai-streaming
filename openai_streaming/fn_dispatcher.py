from inspect import getfullargspec, signature, iscoroutinefunction
from typing import Callable, List, Dict, Tuple, Union, Optional, Set, AsyncGenerator, get_origin, get_args, Type
from asyncio import Queue, gather, create_task

from pydantic import ValidationError


async def _generator_from_queue(q: Queue) -> AsyncGenerator:
    """
    Converts a queue to a generator.
    :param q: The queue to convert
    :return: A generator that yields values from the queue
    """
    while True:
        value = await q.get()
        if value is None:  # Sentinel value to signal the end
            break
        yield value

    q.task_done()


def o_func(func):
    """
    Returns the original function from a function that has been wrapped by a decorator (that preserves the original
    function in the func attribute).
    :param func:
    :return:
    """
    if hasattr(func, 'func'):
        return o_func(func.func)
    if hasattr(func, '__func'):
        return o_func(func.__func)
    if hasattr(func, 'raw_function'):
        return o_func(func.raw_function)
    return func


async def _invoke_function_with_queues(func: Callable, queues: Dict, self: Optional = None) -> None:
    """
    Invokes a function with arguments from queues.
    :param func: The function to invoke
    :param queues: A dictionary of argument names with their values queues
    :param self: An optional self argument to pass to the function
    :return: void
    """
    args = {arg: _generator_from_queue(queues[arg]) for arg in getfullargspec(o_func(func)).args if arg in queues}
    if "self" in signature(func).parameters.keys() and self is not None:
        args['self'] = self

    await func(**args)


async def _read_stream(
        gen: Callable[[], AsyncGenerator[Tuple[str, Dict], None]],
        dict_preprocessor: Optional[Callable[[str, Dict], Dict]],
        args_queues: Dict[str, Dict[str, Queue]],
        args_types: Dict[str, Dict[str, Type]],
        yielded_functions: Queue[Optional[str]],
) -> None:
    """
    Reads from a generator and puts the values in the queues per function per argument.

    :param gen: A generator that yields function names and a dictionary of arguments
    :param dict_preprocessor: A function that takes a function name and a dictionary of arguments and returns a new
        dictionary of arguments
    :param args_queues: A dictionary of function names to dictionaries of argument names to queues of values
    :param args_types: A dictionary of function names to a dictionaries of argument names to their type
    :param yielded_functions: A queue of function names that were yielded
    :return: void
    """

    yielded_functions_set = set()
    async for func_name, args_dict in gen():
        if func_name not in yielded_functions_set:
            await yielded_functions.put(func_name)
            yielded_functions_set.add(func_name)

        if dict_preprocessor is not None:
            args_dict = dict_preprocessor(func_name, args_dict)
        args = args_dict.items()
        for arg_name, value in args:
            if func_name not in args_queues:
                raise ValueError(f"Function {func_name} was not registered")
            if arg_name not in args_queues[func_name]:
                raise ValueError(f"Argument {arg_name} was not registered for function {func_name}")
            if arg_name in args_types[func_name] and type(value) is not args_types[func_name][arg_name]:
                raise ValidationError(f"Got invalid value type for argument `{arg_name}`")
            await args_queues[func_name][arg_name].put(value)

    await yielded_functions.put(None)
    for func_name in args_queues:
        for arg_name in args_queues[func_name]:
            await args_queues[func_name][arg_name].put(None)


async def _dispatch_yielded_function_coroutines(
        q: Queue[Optional[str]],
        func_map: Dict[str, Callable],
        args_queues: Dict[str, Dict],
        self: Optional = None,
) -> Set[str]:
    """
    Dispatches function invocation threads from a queue of function names.
    This function is used to dynamically dispatch threads for functions that have been yielded from a generator.

    :param q: A queue of function names
    :param func_map: A dictionary of function names to their functions
    :param args_queues: A dictionary of function names to dictionaries of argument names to queues of values
    :param self: An optional self argument to pass to the functions
    :return: A set of function names that were invoked
    """

    invoked = set()
    tasks = []
    while True:
        func_name = await q.get()
        if func_name is None:
            break
        if func_name in invoked:
            continue

        tasks.append(create_task(_invoke_function_with_queues(func_map[func_name], args_queues[func_name], self)))
        invoked.add(func_name)

    await gather(*tasks)
    return invoked


async def dispatch_yielded_functions_with_args(
        gen: Callable[[], AsyncGenerator[Tuple[str, Dict], None]],
        funcs: Union[List[Callable], Dict[str, Callable]],
        dict_preprocessor: Optional[Callable[[str, Dict], Dict]],
        self: Optional = None
) -> Set[str]:
    """
    Dispatches function calls from a generator that yields function names and arguments to the functions.
    :param gen: The generator that yields function names and arguments
    :param funcs: The functions to dispatch to
    :param dict_preprocessor: A function that takes a function name and a dictionary of arguments and returns a new
        dictionary of arguments
    :param self: An optional self argument to pass to the functions
    :return: A set of function names that were invoked
    """

    if isinstance(funcs, dict):
        func_map = funcs
    else:
        func_map = {o_func(func).__name__: func for func in funcs}

    for func_name, func in func_map.items():
        if not iscoroutinefunction(o_func(func)):
            raise ValueError(f"Function {func_name} is not an async function")

    args_queues = {}
    args_types = {}
    for func_name in func_map:
        spec = getfullargspec(o_func(func_map[func_name]))
        if spec.args[0] == "self" and self is None:
            raise ValueError("self argument is required for functions that take self")
        idx = 1 if spec.args[0] == "self" else 0
        args_queues[func_name] = {arg: Queue() for arg in spec.args[idx:]}

        # create type maps for validations
        args_types[func_name] = {}
        for arg in spec.args[idx:]:
            if arg in spec.annotations:
                a = spec.annotations[arg]
                if get_origin(a) is get_origin(AsyncGenerator):
                    a = get_args(a)[0]
                args_types[func_name][arg] = a

    # Reading coroutine
    yielded_functions = Queue()
    stream_processing = _read_stream(gen, dict_preprocessor, args_queues, args_types, yielded_functions)

    # Dispatching thread per invoked function
    dispatch_invokes = _dispatch_yielded_function_coroutines(yielded_functions, func_map, args_queues, self)

    _, invoked = await gather(stream_processing, dispatch_invokes)
    return invoked
