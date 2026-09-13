from django.urls import path
from .views import excuse_generator_view

urlpatterns = [
    path('', excuse_generator_view, name='home'),
]
