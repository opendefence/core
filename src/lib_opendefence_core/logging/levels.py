"""Add log levels

Adapted from https://stackoverflow.com/a/35804945 and pointers therein
"""

from typing import Any, Optional
import logging
import warnings

from ..sentinel import Sentinel

#: When adding a new logging level, with :py:func:`add_logging_level`,
#: silently keep the old level in case of conflict.
KEEP = "keep"


#: When adding a new logging level, with :py:func:`add_logging_level`,
#: keep the old level in case of conflict, and issue a warning.
KEEP_WARN = "keep-warn"


#: When adding a new logging level, with :py:func:`add_logging_level`,
#: silently overwrite any existing level in case of conflict.
OVERWRITE = "overwrite"


#: When adding a new logging level, with :py:func:`add_logging_level`,
#: overwrite any existing level in case of conflict, and issue a
#: warning.
OVERWRITE_WARN = "overwrite-warn"


#: When adding a new logging level, with :py:func:`add_logging_level`,
#: raise an error in case of conflict.
RAISE = "raise"


def add_logging_level(  # pylint: disable=R0912,R0915,R0913,R0914
    level_name: str,
    level_num: int,
    method_name: Optional[str] = None,
    if_exists: str = KEEP_WARN,
    *,
    exc_info: bool = False,
    stack_info: bool = False,
) -> None:
    """
    Comprehensively add a new logging level to the :py:mod:`logging`
    module and the currently configured logging class.

    The `if_exists` parameter determines the behavior if the level
    name is already an attribute of the :py:mod:`logging` module or if
    the method name is already present, unless the attributes are
    configured to the exact values requested. Partial registration is
    considered a conflict. Even a complete registration will be
    overwritten if ``if_exists in (OVERWRITE, OVERWRITE_WARN)`` (without
    a warning of course).

    This function also accepts alternate default values for the keyword
    arguments ``exc_info`` and ``stack_info`` that are optional for
    every logging method. Setting alternate defaults allows levels for
    which exceptions or stacks are always logged.

    Parameters
    ----------
    level_name : str
        Becomes an attribute of the :py:mod:`logging` module with the
        value ``level_num``.
    level_num : int
        The numerical value of the new level.
    method_name : str
        The name of the convenience method for both :py:mod:`logging`
        itself and the class returned by
        :py:func:`logging.getLoggerClass` (usually just
        :py:class:`logging.Logger`). If ``method_name`` is not
        specified, ``level_name.lower()`` is used instead.
    if_exists : {KEEP, KEEP_WARN, OVERWRITE, OVERWRITE_WARN, RAISE}
        What to do if a level with `level_name` appears to already be
        registered in the :py:mod:`logging` module:

        :py:const:`KEEP`
            Silently keep the old level as-is.
        :py:const:`KEEP_WARN`
            Keep the old level around and issue a warning.
        :py:const:`OVERWRITE`
            Silently overwrite the old level.
        :py:const:`OVERWRITE_WARN`
            Overwrite the old level and issue a warning.
        :py:const:`RAISE`
            Raise an error.

        The default is :py:const:`KEEP_WARN`.
    exc_info : bool
        Default value for the ``exc_info`` parameter of the new method.
    stack_info : bool
        Default value for the ``stack_info`` parameter of the new
        method.

    Examples
    --------
    >>> add_logging_level('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    >>> add_logging_level('XTRACE', 2, exc_info=True)
    >>> logging.getLogger(__name__).setLevel(logging.XTRACE)
    >>> try:
    >>>     1 / 0
    >>> except:
    >>>     # This line will log the exception
    >>>     logging.getLogger(__name__).xtrace('that failed')
    >>>     # This one will not
    >>>     logging.xtrace('so did this', exc_info=False)

    The ``TRACE`` level can be added using :py:func:`add_trace_level`.

    Note
    ----
    Before adding new levels, please see the cautionary note here:
    https://docs.python.org/3/howto/logging.html#custom-levels.
    """

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def for_logger_adapter(self: Any, msg: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("exc_info", exc_info)
        kwargs.setdefault("stack_info", stack_info)
        kwargs.setdefault("stacklevel", 2)
        self.log(level_num, msg, *args, **kwargs)

    def for_logger_class(self: Any, msg: Any, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(level_num):
            kwargs.setdefault("exc_info", exc_info)
            kwargs.setdefault("stack_info", stack_info)
            kwargs.setdefault("stacklevel", 2)
            self._log(level_num, msg, args, **kwargs)  # pylint: disable=W0212

    def for_logging_module(*args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("exc_info", exc_info)
        kwargs.setdefault("stack_info", stack_info)
        kwargs.setdefault("stacklevel", 2)
        logging.log(level_num, *args, **kwargs)

    if not method_name:
        method_name = level_name.lower()
    if method_name == level_name:
        raise ValueError("Method name must differ from level name")

    # The number of items required for a full registration is 5
    items_found = 0
    # Items that are found complete but are not expected values
    items_conflict = 0

    def check_conflict(conflict: bool, message: str) -> bool:
        if conflict and if_exists == RAISE:
            raise AttributeError(message)
        return conflict

    def check_func_conflict(func: Any, name: str, original_name: str, is_func: bool, target: str) -> bool:
        conflict = not (
            callable(func)
            and getattr(func, "_original_name", None) == original_name
            and getattr(func, "_exc_info", None) == exc_info
            and getattr(func, "_stack_info", None) == stack_info
        )
        return check_conflict(
            conflict, "{} {!r} already defined in {}".format("Function" if is_func else "Method", name, target)
        )

    # Lock because logger class and level name are queried and set
    with logging._lock:  # type: ignore[attr-defined]  # pylint: disable=W0212
        registered_num = logging.getLevelName(level_name)
        logger_class = logging.getLoggerClass()
        logger_adapter = logging.LoggerAdapter

        if registered_num != "Level " + level_name:
            items_found += 1
            items_conflict += check_conflict(
                registered_num != level_num, "Level {!r} already registered " "in logging module".format(level_name)
            )

        current_level = getattr(logging, level_name, Sentinel)
        if current_level is not Sentinel:
            items_found += 1
            items_conflict += check_conflict(
                current_level != level_num, "Level {!r} already defined " "in logging module".format(level_name)
            )

        logging_func = getattr(logging, method_name, Sentinel)
        if logging_func is not Sentinel:
            items_found += 1
            items_conflict += check_func_conflict(
                logging_func, method_name, for_logging_module.__name__, True, "logging module"
            )

        logger_method = getattr(logger_class, method_name, Sentinel)
        if logger_method is not Sentinel:
            items_found += 1
            items_conflict += check_func_conflict(
                logger_method, method_name, for_logger_class.__name__, False, "logger class"
            )

        adapter_method = getattr(logger_adapter, method_name, Sentinel)
        if adapter_method is not Sentinel:
            items_found += 1
            items_conflict += check_func_conflict(
                adapter_method, method_name, for_logger_adapter.__name__, False, "logger adapter"
            )

        if items_found > 0:
            # items_found >= items_conflict always
            if (items_conflict or items_found < 5) and if_exists in (KEEP_WARN, OVERWRITE_WARN):
                action = "Keeping" if if_exists == KEEP_WARN else "Overwriting"
                if items_conflict:
                    problem = "has conflicting definition"
                    items = items_conflict
                else:
                    problem = "is partially configured"
                    items = items_found
                warnings.warn(
                    "Logging level {!r} {} already ({}/5 items): {}".format(level_name, problem, items, action)
                )

            if if_exists in (KEEP, KEEP_WARN):
                return

        # Make sure the method names are set to sensible values, but
        # preserve the names of the old methods for future verification.
        def label_func(func: Any) -> None:
            func._original_name = func.__name__  # pylint: disable=W0212
            func.__name__ = method_name
            func._exc_info = exc_info  # pylint: disable=W0212
            func._stack_info = stack_info  # pylint: disable=W0212

        label_func(for_logging_module)
        label_func(for_logger_class)
        label_func(for_logger_adapter)

        # Actually add the new level
        logging.addLevelName(level_num, level_name)
        setattr(logging, level_name, level_num)
        setattr(logging, method_name, for_logging_module)
        setattr(logger_class, method_name, for_logger_class)
        setattr(logger_adapter, method_name, for_logger_adapter)
