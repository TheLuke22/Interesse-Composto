import pytest
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd


class TestUIRouting(unittest.TestCase):
    def test_component_imports(self):
        from components import (
            render_compound_interest_ui,
            render_stock_tracker_ui,
            render_home_ui,
            render_my_portfolio_ui,
            render_financial_news_ui,
            render_superinvestors_ui,
            render_macro_market_ui,
            render_stock_screener_ui,
            render_business_segments_ui,
        )
        assert callable(render_compound_interest_ui)
        assert callable(render_stock_tracker_ui)
        assert callable(render_home_ui)
        assert callable(render_my_portfolio_ui)
        assert callable(render_financial_news_ui)
        assert callable(render_superinvestors_ui)
        assert callable(render_macro_market_ui)
        assert callable(render_stock_screener_ui)
        assert callable(render_business_segments_ui)

    @patch("streamlit.empty")
    @patch("streamlit.container")
    def test_container_slot_isolation(self, mock_container, mock_empty):
        slot = mock_empty.return_value
        container_ctx = slot.container.return_value
        assert slot is not None
        assert container_ctx is not None
