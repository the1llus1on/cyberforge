"""In-memory workspace history, independent of widgets and domain data."""

from enum import StrEnum


class AuthenticationState(StrEnum):
    """Presentation state only; identity and authorization belong to Phase 2."""

    GUEST = "guest"


class View(StrEnum):
    """Destinations independent of authentication or future user roles."""

    HOME = "home"
    CONSTRUCTOR = "constructor"
    ANALYTICS = "analytics"
    PROFILE = "profile"
    SETTINGS = "settings"


class NavigationState:
    """Track contexts without creating scenarios or changing saved material."""

    def __init__(self) -> None:
        self._history = [View.HOME]
        self._index = 0

    @property
    def current(self) -> View:
        return self._history[self._index]

    @property
    def can_go_back(self) -> bool:
        return self._index > 0

    @property
    def can_go_forward(self) -> bool:
        return self._index < len(self._history) - 1

    def navigate(self, view: View) -> None:
        if view == self.current:
            return
        self._history[self._index + 1 :] = [view]
        self._index += 1

    def back(self) -> None:
        if self.can_go_back:
            self._index -= 1

    def forward(self) -> None:
        if self.can_go_forward:
            self._index += 1
