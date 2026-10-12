from django.db.models import Case, CharField, Count, Q, Value, When
from django.db.models.functions import Cast, Concat, LPad
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket
from .pagination import TicketPagination
from .permissions import TicketRolePermission
from .serializers import TicketSerializer, TicketUpdateSerializer


def matching_search(queryset, request):
    search = request.query_params.get("search", "").strip()
    if search:
        ticket_id = Cast("id", CharField())
        ticket_code = Concat(
            Value("TKT-"),
            Case(
                When(id__gte=10000, then=ticket_id),
                default=LPad(ticket_id, 4, Value("0")),
                output_field=CharField(),
            ),
            output_field=CharField(),
        )
        queryset = queryset.annotate(ticket_code=ticket_code).filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(ticket_code__icontains=search)
        )
    return queryset


class TicketListCreateView(generics.ListCreateAPIView):
    serializer_class = TicketSerializer
    pagination_class = TicketPagination
    permission_classes = [TicketRolePermission]

    def get_queryset(self):
        queryset = matching_search(Ticket.objects.all(), self.request)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            if status_filter not in Ticket.Status.values:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"status": "Invalid status."})
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        return Response(
            TicketSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )


class TicketUpdateView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [TicketRolePermission]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return TicketUpdateSerializer
        return TicketSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        return Response(TicketSerializer(ticket).data)

    def perform_destroy(self, instance):
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(TicketSerializer(instance).data, status=status.HTTP_200_OK)


class TicketStatsView(APIView):
    permission_classes = [TicketRolePermission]

    def get(self, request):
        counts = {
            row["status"]: row["count"]
            for row in matching_search(Ticket.objects.all(), request).values("status").annotate(count=Count("id"))
        }
        return Response({key: counts.get(key, 0) for key in Ticket.Status.values})
