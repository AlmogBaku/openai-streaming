from inspect import getfullargspec, signature
from typing import Callable, Generator, List, Dict, Tuple, Union, Optional, Set
from threading import Thread, Event
from queue import Queue


def _generator_from_queue(q: Queue) -> Generator:
    """
    Converts a queue to a generator.
    :param q: the queue to convert
    :return: a generator that yields values from the queue
    """
    while True:
        value = q.get()
        if value is None:  # Sentinel value to signal end
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
    return func


def _invoke_function_with_queues(func: Callable, queues: Dict, self: Optional = None) -> None:
    """
    Invokes a function with arguments from queues.
    :param func: the function to invoke
    :param queues: a dictionary of argument names to queues of values
    :param self: an optional self argument to pass to the function
    :return: void
    """
    args = {arg: _generator_from_queue(queues[arg]) for arg in getfullargspec(o_func(func)).args if arg in queues}
    if "self" in signature(func).parameters.keys() and self is not None:
        args['self'] = self
    func(**args)


def _read_stream(
        gen: Callable[[], Generator[Tuple[str, Dict], None, None]],
        dict_preprocessor: Optional[Callable[[str, Dict], Dict]],
        args_queues: Dict[str, Dict],
        yielded_functions: Queue[Optional[str]],
        finish_event: Event
) -> None:
    """
    Reads from a generator and puts the values in the queues per function per argument.

    :param gen: a generator that yields function names and arguments a dictionary
    :param dict_preprocessor: a function that takes a function name and a dictionary of arguments and returns a new
        dictionary of arguments
    :param args_queues: a dictionary of function names to dictionaries of argument names to queues of values
    :param yielded_functions: a queue of function names that were yielded
    :param finish_event: an event to signal when the reading is done
    :return: void
    """

    yielded_functions_set = set()
    for func_name, args_dict in gen():
        if func_name not in yielded_functions_set:
            yielded_functions.put(func_name)
            yielded_functions_set.add(func_name)

        if dict_preprocessor is not None:
            args_dict = dict_preprocessor(func_name, args_dict)
        args = args_dict.items()
        for arg_name, value in args:
            args_queues[func_name][arg_name].put(value)

    yielded_functions.put(None)
    for func_name in args_queues:
        for arg_name in args_queues[func_name]:
            args_queues[func_name][arg_name].put(None)

    finish_event.set()


def _dispatch_yielded_function_threads(
        q: Queue[Optional[str]],
        func_map: Dict[str, Callable],
        args_queues: Dict[str, Dict],
        invoked_q: Queue[Set[str]],
        self: Optional = None,
):
    """
    Dispatches function invocation threads from a queue of function names.
    This function is used to dynamically dispatch threads for functions that has been yielded from a generator.

    :param q: a queue of function names
    :param func_map: a dictionary of function names to functions
    :param args_queues: a dictionary of function names to dictionaries of argument names to queues of values
    :param invoked_q: a queue to put a set of function names that were invoked
    :param self: an optional self argument to pass to the functions
    :return: void
    """

    threads = {}
    while True:
        func_name = q.get()
        if func_name is None:
            break
        if func_name in threads:
            continue

        t = Thread(target=_invoke_function_with_queues, args=(func_map[func_name], args_queues[func_name], self))
        t.start()
        threads[func_name] = t

    q.task_done()
    for t in threads.values():
        t.join()

    invoked = set()
    for func_name in threads:
        invoked.add(func_name)
    invoked_q.put(invoked)
    invoked_q.task_done()


def dispatch_yielded_functions_with_args(
        gen: Callable[[], Generator[Tuple[str, Dict], None, None]],
        funcs: Union[List[Callable], Dict[str, Callable]],
        dict_preprocessor: Optional[Callable[[str, Dict], Dict]],
        self: Optional = None
) -> Set[str]:
    """
    Dispatches function calls from a generator that yields function names and arguments to the functions.
    :param gen: the generator that yields function names and arguments
    :param funcs: the functions to dispatch to
    :param dict_preprocessor: a function that takes a function name and a dictionary of arguments and returns a new
        dictionary of arguments
    :param self: an optional self argument to pass to the functions
    :return: a set of function names that were invoked
    """

    if isinstance(funcs, dict):
        func_map = funcs
    else:
        func_map = {o_func(func).__name__: func for func in funcs}

    args_queues = {}
    for func_name in func_map:
        spec = getfullargspec(o_func(func_map[func_name]))
        if spec.args[0] == "self" and self is None:
            raise ValueError("self argument is required for functions that take self")
        idx = 1 if spec.args[0] == "self" else 0
        args_queues[func_name] = {arg: Queue() for arg in spec.args[idx:]}

    # Reading thread
    finish_event = Event()
    yielded_functions = Queue()
    stream_processing_thread = Thread(
        target=_read_stream,
        args=(gen, dict_preprocessor, args_queues, yielded_functions, finish_event)
    )
    stream_processing_thread.start()

    # Dispatching thread per invoked function
    invoked_queue = Queue()
    dispatch_invokes_thread = Thread(
        target=_dispatch_yielded_function_threads,
        args=(yielded_functions, func_map, args_queues, invoked_queue, self),
    )
    dispatch_invokes_thread.start()

    # wait for the stream reading thread to finish
    finish_event.wait()

    # wait for the dispatching thread to finish
    invoked = invoked_queue.get()
    return invoked
