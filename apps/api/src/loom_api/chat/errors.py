class ChatError(Exception):
    """Base for domain errors the router maps to HTTP responses."""


class ConversationNotFound(ChatError):
    pass


class MessageNotFound(ChatError):
    """The message does not exist in this conversation."""


class GenerationInProgress(ChatError):
    pass


class InvalidParent(ChatError):
    """A new user message must hang off an assistant message of the same conversation (or be
    a root)."""


class InvalidGenerationTarget(ChatError):
    """Only a user message can be answered (regenerated)."""
