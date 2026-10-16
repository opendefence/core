"""A class that can be used to create sentinel objects for cases where :py:obj:`None`
is not suitable for some reason."""


class SentinelType:  # pylint: disable=R0903
    """
    A class that can be used to create sentinel objects for cases where
    :py:obj:`None` is not suitable for some reason.

    This class's truth value is always :py:obj:`False`. It does not
    allow any additional attributes to be added.

    Simply creating an empty :py:class:`object` is fine in most cases.
    """

    __slots__ = ()

    def __bool__(self) -> bool:
        """
        Ensure that instances are always falsy.
        """
        return False


#: A sentinel object that can be used when :py:obj:`None` is not a
#: suitable option (e.g., when :py:obj:`None` has a special meaning).
#:
#: This object evaluates to boolean :py:obj:`False`.
Sentinel = SentinelType()
