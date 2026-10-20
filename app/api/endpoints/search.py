from fastapi import APIRouter
from app.schemas.flight import FlightSearchParams
from app.services.flight_service import FlightService

router = APIRouter()

@router.post("/flight/search")
async def search_flights(flight_req: FlightSearchParams):
    svc = FlightService()
    return await svc.search_flights(flight_req)

@router.post("/location/search")
async def search_locations(keyword: str, limit: int = 10, subtype: list[str] | None = None):
    svc = FlightService()
    return await svc.search_locations(keyword, limit, subtype)

# flight offers price
@router.post("/flight/confirm_price")
async def flight_confirm_price(flight_req):
    svc = FlightService()
    return await svc.price_or_confirm(flight_req)

# flight create orders
@router.post("/flight/booking")
async def create_flight_booking(flight_req):
    svc= FlightService()
    return await svc.create_order(flight_req)

# flight order management
@router.get("/flight/order/{order_id}")
async def get_flight_order(order_id: str):
    svc = FlightService()
    return await svc.get_order(order_id)

# seat map display

