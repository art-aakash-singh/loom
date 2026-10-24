class ChatError(Exception):
    """Base for domain errors the router maps to HTTP responses."""


class ConversationNotFound(ChatError):
    pass


class GenerationInProgress(ChatError):
    pass
