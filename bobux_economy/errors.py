class Failed(RuntimeError):
    """
    A base exception type for all errors in bobux economy. In most cases, this
    should not be used directly, but instead should be extended by more specific
    error types.
    """

    message: str
    http_status: int

    def __init__(self, message: str, http_status: int = 500):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


class InsufficientFunds(Failed):
    def __init__(self):
        super().__init__("Insufficient funds", 400)

class NegativeAmount(Failed):
    def __init__(self):
        super().__init__("Amount must not be negative", 400)


class NotConfigured(Failed):
    def __init__(self, message: str):
        super().__init__(message, 501)


class UserMissingPermissions(Failed):
    def __init__(self, message: str):
        super().__init__(message, 403)

class BotMissingPermissions(Failed):
    def __init__(self, message: str):
        super().__init__(message, 500)


class InvalidChannelType(Failed):
    def __init__(self, message: str):
        super().__init__(message, 400)


class MessageAlreadyInDestination(Failed):
    def __init__(self, message: str):
        super().__init__(message, 400)
