from __future__ import annotations
import os
from collections.abc import Sequence
from urllib.parse import quote

from dotenv import load_dotenv
from google.maps import routing_v2
import httpx

from elrag.schemas.json.maps import RouteRequest
load_dotenv()

DEFAULT_PLACE_DETAIL_FIELDS = (
    "id",
    "displayName",
    "formattedAddress",
    "location",
    "googleMapsUri",
    "nationalPhoneNumber",
    "rating",
    "userRatingCount",
)
DEFAULT_TEXT_SEARCH_FIELDS = (
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.googleMapsUri",
)
DEFAULT_ROUTE_FIELDS = (
    "routes.distanceMeters",
    "routes.duration",
    "routes.staticDuration",
)




class GoogleMapsService:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
        places_base_url: str = "https://places.googleapis.com",
        routes_base_url: str = "https://routes.googleapis.com",
    ) -> None:
        self.api_key = api_key or os.environ.get("GMAPS_API_KEY")
        if not self.api_key:
            raise ValueError("GMAPS_API_KEY is not configured")

        self.places_base_url = places_base_url.rstrip("/")
        self.routes_base_url = routes_base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self.routes_client= routing_v2.RoutesClient()
        self._owns_client = client is None

    async def __aenter__(self) -> GoogleMapsService:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def autocomplete(
        self,
        input_text: str,
        *,
        session_token: str | None = None,
        language_code: str | None = None,
        region_code: str | None = None,
    ) -> dict:
        body = {"input": input_text}
        self._set_optional(
            body,
            sessionToken=session_token,
            languageCode=language_code,
            regionCode=region_code,
        )

        return await self._post_places("/v1/places:autocomplete", json=body)

    async def text_search(
        self,
        query: str,
        *,
        max_result_count: int = 10,
        language_code: str | None = None,
        region_code: str | None = None,
    ) -> dict:
        body = {
            "textQuery": query,
            "maxResultCount": max_result_count,
        }
        self._set_optional(
            body,
            languageCode=language_code,
            regionCode=region_code,
        )

        return await self._post_places(
            "/v1/places:searchText",
            json=body,
            field_mask=DEFAULT_TEXT_SEARCH_FIELDS,
        )

    async def place_detail(
        self,
        place_id: str,
        *,
        fields: Sequence[str] | None = None,
        language_code: str | None = None,
    ) -> dict:
        normalized_place_id = place_id.removeprefix("places/")
        path = f"/v1/places/{quote(normalized_place_id, safe='')}"
        params = {}
        self._set_optional(params, languageCode=language_code)

        return await self._get_places(
            path,
            params=params,
            field_mask=fields or DEFAULT_PLACE_DETAIL_FIELDS,
        )

    async def distance_time(
        self,
        origin: str,
        destination: str,
        *,
        travel_mode: str = "DRIVE",
        routing_preference: str = "TRAFFIC_AWARE",
    ) -> dict:
        body = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": travel_mode,
            "routingPreference": routing_preference,
        }

        return await self._post_routes(
            "/directions/v2:computeRoutes",
            json=body,
            field_mask=DEFAULT_ROUTE_FIELDS,
        )
        
    async def get_routes(self, route_request: RouteRequest) -> dict: 
        sdk_origin = self._build_waypoint(route_request.origin)
        sdk_destination = self._build_waypoint(route_request.destination)
        request = routing_v2.ComputeRoutesRequest(
            origin=sdk_origin,
            destination=sdk_destination,
            travel_mode=routing_v2.RouteTravelMode.DRIVE,
            routing_preference=routing_v2.RoutingPreference.TRAFFIC_AWARE,
        )

        metadata = [
            ("x-goog-fieldmask", "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline")
        ]

        response = self.routes_client.compute_routes(request=request, metadata=metadata)
        if not response.routes:
            raise Exception("No routes were found.")

        route_list = []
        for route in response.routes:
            route_dict = {
                "distance_meters": route.distance_meters,
                "duration_minutes": route.duration.seconds // 60,
                "polyline": route.polyline.encoded_polyline
            }
            route_list.append(route_dict)
        return {
            "status": "success",
            "total_routes_found": len(route_list),
            "data": route_list
        }



    async def _build_waypoint(self, coords: tuple[float, float]):
        return routing_v2.Waypoint(
            location=routing_v2.Location(
                lat_lng={"latitude": coords[0], "longitude": coords[1]}
            )
        )
    async def _get_places(
        self,
        path: str,
        *,
        params: dict | None = None,
        field_mask: Sequence[str] | None = None,
    ) -> dict:
        response = await self.client.get(
            f"{self.places_base_url}{path}",
            params=params,
            headers=self._headers(field_mask=field_mask),
        )
        response.raise_for_status()
        return response.json()

    async def _post_places(
        self,
        path: str,
        *,
        json: dict,
        field_mask: Sequence[str] | None = None,
    ) -> dict:
        response = await self.client.post(
            f"{self.places_base_url}{path}",
            json=json,
            headers=self._headers(field_mask=field_mask),
        )
        response.raise_for_status()
        return response.json()

    async def _post_routes(
        self,
        path: str,
        *,
        json: dict,
        field_mask: Sequence[str],
    ) -> dict:
        response = await self.client.post(
            f"{self.routes_base_url}{path}",
            json=json,
            headers=self._headers(field_mask=field_mask),
        )
        response.raise_for_status()
        return response.json()
    
    

    def _headers(self, *, field_mask: Sequence[str] | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }
        if field_mask:
            headers["X-Goog-FieldMask"] = ",".join(field_mask)
        return headers
    
    
    @staticmethod
    def _set_optional(target: dict, **values: str | None) -> None:
        for key, value in values.items():
            if value is not None:
                target[key] = value

