# config_logistica/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings               # Importa as configurações do settings.py
from django.conf.urls.static import static     # Importa a função que libera as fotos de mídia

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('logistica.urls')), # Conecta as urls do seu app à raiz do site
]

# A CORREÇÃO ESTÁ AQUI: Mudamos de document-root para document_root
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)