# reports/views.py

from django.shortcuts import get_object_or_404, render
from rest_framework import viewsets, filters, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import SAFE_METHODS
from reports.models import LostItems, FoundItem, Claim
from .serializer import LostItemSerializer, FoundItemSerializer, ClaimSerializer, UserSerializer
from reports.utils import match_lost_item
from django.contrib.auth.models import User
from django.db.models import Q
from prometheus_client import Counter, Histogram

# Tracks total claims created
LOSTFOUND_CLAIMS_TOTAL = Counter(
    'lostfound_claims_created_total',
    'Total number of claims submitted'
)

# Tracks approved vs rejected claims under one metric using labels
LOSTFOUND_CLAIM_RESOLUTIONS = Counter(
    'lostfound_claim_resolutions_total',
    'Total count of claim completions by resolution state',
    ['resolution']
)

# Tracks how long the matching algorithm takes to execute
LOSTFOUND_MATCHING_DURATION = Histogram(
    'lostfound_matching_algorithm_duration_seconds',
    'Time spent running the item matching algorithm'
)


# -------------------------------
# Permissions
# -------------------------------
class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission: Only owner of object can edit/delete it.
    Read-only for others.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


# -------------------------------
# Lost Items
# -------------------------------
class LostItemsViewset(viewsets.ModelViewSet):
    queryset = LostItems.objects.all()
    serializer_class = LostItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location', 'description']
    ordering_fields = ['name', 'date_lost', 'location']

    def perform_create(self, serializer):
        # Automatically attach the logged-in user
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def matches(self, request, pk=None):
        """
        GET /api/lost-items/<id>/matches/
        Returns a list of found items with match scores.
        """
        lost_item = self.get_object()
        found_items = FoundItem.objects.all()
        with LOSTFOUND_MATCHING_DURATION.time():
            matches = match_lost_item(lost_item, found_items)
        return Response(matches)


# -------------------------------
# Found Items
# -------------------------------
class FoundItemViewset(viewsets.ModelViewSet):
    queryset = FoundItem.objects.all()
    serializer_class = FoundItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location', 'description']
    ordering_fields = ['name', 'date_found', 'location']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# -------------------------------
# Claims
# -------------------------------
class ClaimViewSet(viewsets.ModelViewSet):
    """
    Handles claims from lost item owners for found items.
    Only authenticated users can create/view claims.
    Status field is read-only (default: Pending)
    """
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Public dashboard → show ALL claims
        return Claim.objects.all()

    def perform_create(self, serializer):
        try:
            lost_item_id = self.request.data.get("lost_item")
            found_item_id = self.request.data.get("found_item")
            user = self.request.user

            lost_item = get_object_or_404(LostItems, id=lost_item_id)
            found_item = get_object_or_404(FoundItem, id=found_item_id)

            # Optional: prevent claiming own item
            if found_item.user == self.request.user:
                raise serializers.ValidationError("You cannot claim your own lost item.")

            # 🚫 Prevent duplicate claim unless it was rejected
            existing_claim = Claim.objects.filter(
                lost_item=lost_item,
                found_item=found_item,
                lost_item__user=user  # user who owns the lost item
            ).exclude(status="Rejected").first()

            if existing_claim:
                raise serializers.ValidationError(
                    "You already claimed this item. Wait until it is approved or rejected."
            )

            serializer.save(lost_item=lost_item, found_item=found_item)
            LOSTFOUND_CLAIMS_TOTAL.inc()

        except Exception as e:
            print("Claim creation error:", e)
            raise

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        claim = self.get_object()
        # Only the found item owner can approve
        if claim.found_item.user != request.user:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        claim.status = "Approved"
        claim.save()
        LOSTFOUND_CLAIM_RESOLUTIONS.labels(resolution="Approved").inc()
        return Response({"status": "Claim approved"})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        claim = self.get_object()
        if claim.found_item.user != request.user:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        claim.status = "Rejected"
        claim.save()
        LOSTFOUND_CLAIM_RESOLUTIONS.labels(resolution="Rejected").inc()
        return Response({"status": "Claim rejected"})

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]  # Anyone can signup

def lost_detail(request, id):
    print("DEBUG: lost_detail called with id=", id)
    lost_item = get_object_or_404(LostItems, id=id)
    print("DEBUG: lost_item in view:", lost_item)
    return render(request, "lost_detail.html", {"lost_item": lost_item})
