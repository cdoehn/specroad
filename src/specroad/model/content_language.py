"""Declared view metadata; language and direction are independent inputs."""
from dataclasses import dataclass
from .errors import ModelError
from .language_tags import parse_language_tag


@dataclass(frozen=True)
class ContentLanguage:
    language: str | None = None
    text_direction: str = "auto"

    def __post_init__(self):
        if self.language is not None:
            parse_language_tag(self.language)
        if type(self.text_direction) is not str or self.text_direction not in {"ltr", "rtl", "auto"}:
            raise ModelError("invalid_text_direction", pointer="/text_direction")

    def as_dict(self):
        # Original case is retained. auto is a rendering hint, not detection.
        return {"language": self.language, "text_direction": self.text_direction,
                "source": "declaration", "language_detected": False, "direction_detected": False}
