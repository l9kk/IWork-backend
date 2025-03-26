from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.models.company import Company


@patch("app.services.integrations.stock_api.yf.Ticker")
def test_stock_data_endpoint(mock_ticker, client: TestClient, test_company: Company):
    """Test stock data integration endpoint"""
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.info = {
        "shortName": test_company.name,
        "currentPrice": 150.25,
        "previousClose": 148.75,
        "open": 149.50,
        "dayHigh": 152.00,
        "dayLow": 147.50,
        "volume": 1000000,
        "marketCap": 1500000000,
        "trailingPE": 25.5,
        "dividendYield": 0.015,
        "fiftyTwoWeekHigh": 175.00,
        "fiftyTwoWeekLow": 120.00,
        "currency": "USD"
    }
    mock_ticker.return_value = mock_ticker_instance

    response = client.get(f"/integrations/stock/{test_company.stock_symbol}")

    assert response.status_code == 200
    assert response.json()["symbol"] == test_company.stock_symbol
    assert response.json()["company_name"] == test_company.name
    assert response.json()["current_price"] == 150.25
    assert response.json()["currency"] == "USD"
    assert "formatted_price" in response.json()
    assert "price_change_percent" in response.json()
