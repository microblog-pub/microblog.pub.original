from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.customization import _CUSTOM_ROUTES
from app.customization import get_custom_router
from app.customization import register_html_page
from app.main import app


def test_html_route(client: TestClient) -> None:
    test_path = "/test_registered_html"
    mock_file_contents = '<h1 class="test">This is test file content</h1>'

    # Test that we can register a HTML page
    register_html_page(
        test_path, title="my mock html page", html_file="test.txt", show_in_navbar=True
    )

    # And that it gets added correctly as a route in the app
    app.include_router(get_custom_router())
    assert test_path in _CUSTOM_ROUTES

    # confirm that the route also leads to the file being returned successfully.
    m = MagicMock(read_text=MagicMock(return_value=mock_file_contents))
    _CUSTOM_ROUTES[test_path].html_file = m

    response = client.get(test_path)
    assert response.status_code == 200
    assert mock_file_contents in response.text
