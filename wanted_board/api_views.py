"""Read-only mobile API; website views and their responses stay separate."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import WantedPost
from .serializers import WantedPostSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def wanted_list(request):
    """Return stored open posts, newest first, without fetching external APIs."""
    posts = (
        WantedPost.objects.filter(status=WantedPost.Status.OPEN)
        .select_related("requester")
        .order_by("-created_at", "-pk")
    )
    serializer = WantedPostSerializer(posts, many=True)
    return Response(serializer.data)
