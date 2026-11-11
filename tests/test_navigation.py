"""Workspace history must be bounded, deduplicated and branch correctly."""

from cyberforge.ui.navigation import NavigationState, View


def test_history_boundaries_and_duplicates() -> None:
    state = NavigationState()
    state.back()
    state.forward()
    assert state.current == View.GUEST
    assert not state.can_go_back
    assert not state.can_go_forward
    state.navigate(View.CONSTRUCTOR)
    state.navigate(View.CONSTRUCTOR)
    state.navigate(View.ANALYTICS)
    state.back()
    assert state.current == View.CONSTRUCTOR
    state.back()
    assert state.current == View.GUEST
    state.forward()
    assert state.current == View.CONSTRUCTOR


def test_navigation_after_back_discards_forward_history() -> None:
    state = NavigationState()
    state.navigate(View.CONSTRUCTOR)
    state.navigate(View.ANALYTICS)
    state.back()
    state.navigate(View.PROFILE)
    assert not state.can_go_forward
    state.forward()
    assert state.current == View.PROFILE
    state.back()
    assert state.current == View.CONSTRUCTOR
