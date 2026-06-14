class EntityDoesNotExist(Exception):
    """Raised when entity was not found in database."""


class EntityAlreadyExists(Exception):
    """Raised when entity with a unique field already exists in database."""
