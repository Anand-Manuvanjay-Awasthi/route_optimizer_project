from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .utils.serializers import RouteRequestSerializer
from .services.routing_service import geocode_place, get_route, sample_route_coords
from .services.fuel_service import find_stops_along_route


@api_view(["POST"])
def optimize_route(request):
    serializer = RouteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    start_name = serializer.validated_data["start"]
    end_name = serializer.validated_data["end"]

    try:
        start_coords, start_label = geocode_place(start_name)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Geocoding failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

    try:
        end_coords, end_label = geocode_place(end_name)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Geocoding failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

    try:
        route_coords, distance_miles = get_route(start_coords, end_coords)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception as e:
        return Response({"error": f"Routing failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

    try:
        sampled = sample_route_coords(route_coords, max_points=50)
        fuel_stops, estimated_cost = find_stops_along_route(sampled, distance_miles)
    except Exception as e:
        return Response({"error": f"Fuel stop processing failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        "start": start_label,
        "end": end_label,
        "distance_miles": distance_miles,
        "estimated_total_cost": estimated_cost,
        "fuel_stops": fuel_stops,
        "route_coordinates": route_coords,
    })
