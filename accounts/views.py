# accounts/views.py

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from .serializers import UserRegistrationSerializer

class UserCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [IsAdminUser]


def login_view(request):
  if request.user.is_authenticated:
    return redirect('orders:order_list')  # Перенаправление на страницу заказов, если пользователь уже вошел

  if request.method == 'POST':
    form = AuthenticationForm(request, data=request.POST)
    if form.is_valid():
      user = form.get_user()
      login(request, user)
      return redirect('orders:order_list')  # Перенаправление на страницу заказов после успешного входа
  else:
    form = AuthenticationForm()

  return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
  logout(request)
  return redirect('login')


@login_required
def dashboard(request):
  return render(
      request, 'accounts/dashboard.html', {'user': request.user}
  )