from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/finance", tags=["Finance & Currency"])

class ConvertResponse(BaseModel):
    amount: float
    from_currency: str
    to_currency: str
    converted_amount: float
    rate: float

@router.get("/convert", response_model=ConvertResponse, summary="Convert between fiat currencies (USD, EUR, RUB, etc.)")
async def convert_currency(
    amount: float = Query(1.0, ge=0.01, description="Amount to convert"),
    from_curr: str = Query("USD", description="Source currency code (USD, EUR, RUB, CNY, KZT)"),
    to_curr: str = Query("RUB", description="Target currency code (USD, EUR, RUB, CNY, KZT)")
):
    """
    Performs real-time currency conversion using open exchange rate feeds.
    """
    from_c = from_curr.strip().upper()
    to_c = to_curr.strip().upper()

    if from_c == to_c:
        return ConvertResponse(
            amount=amount,
            from_currency=from_c,
            to_currency=to_c,
            converted_amount=amount,
            rate=1.0
        )

    # Free open exchange rates from open.er-api.com
    url = f"https://open.er-api.com/v6/latest/{from_c}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                rate = rates.get(to_c)
                if rate:
                    converted = round(amount * rate, 2)
                    return ConvertResponse(
                        amount=amount,
                        from_currency=from_c,
                        to_currency=to_c,
                        converted_amount=converted,
                        rate=rate
                    )
                else:
                    raise HTTPException(status_code=400, detail=f"Target currency '{to_c}' not supported")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Currency conversion failed: {str(e)}")

    raise HTTPException(status_code=500, detail="Currency exchange feed unavailable")
