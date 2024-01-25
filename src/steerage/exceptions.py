"""Base exceptions used throughout TURTLE-BASED projects"""


class NotFound(KeyError):
    """A record matching the criteria could not be found."""


class MultipleResultsFound(KeyError):
    """More than one record matching the criteria has been found."""


class AlreadyExists(Exception):
    """A record with the primary key (or other unique attribute) already exists."""
