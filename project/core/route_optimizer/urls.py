from django.urls import path
from .views import optimize_route

urlpatterns = [
    path('optimize-route/', optimize_route),
]
