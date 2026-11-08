# Deskimoni v2 - Services
from .ai import DeskimonAiMixin
from .content import DeskimonContentMixin
from .voice import DeskimonVoiceMixin
from .worktime import DeskimonWorkTimeMixin
from .meetings import DeskimonMeetingBingoMixin
from .quicklaunch import DeskimonQuickLaunchMixin

__all__ = [
    "DeskimonAiMixin", "DeskimonContentMixin", "DeskimonVoiceMixin",
    "DeskimonWorkTimeMixin", "DeskimonMeetingBingoMixin", "DeskimonQuickLaunchMixin"
]
