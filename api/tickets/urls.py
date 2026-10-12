from django.urls import path

from .views import TicketListCreateView, TicketStatsView, TicketUpdateView


urlpatterns = [
    path("tickets/stats", TicketStatsView.as_view(), name="ticket-stats"),
    path("tickets", TicketListCreateView.as_view(), name="ticket-list-create"),
    path("tickets/<int:pk>", TicketUpdateView.as_view(), name="ticket-update"),
]
