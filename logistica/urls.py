from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('registrar/', views.registrar_material, name='registrar_material'),
    path('remover-item/<int:index>/', views.remover_item_sessao, name='remover_item_sessao'),
    path('painel-restrito-ufpa/', views.dashboard, name='dashboard'),
    path('painel-restrito-ufpa/exportar-csv/', views.exportar_csv, name='exportar_csv'),
]