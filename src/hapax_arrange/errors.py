class HapaxArrangeError(Exception):
    pass


class UnsupportedMidiTypeError(HapaxArrangeError):
    pass


class NoMarkersError(HapaxArrangeError):
    pass


class ValidationError(HapaxArrangeError):
    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages
