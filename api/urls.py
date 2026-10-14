from django.urls import path

from . import views

urlpatterns = [
    path("salud", views.SaludView.as_view()),
    path("yo", views.YoView.as_view()),
    path("perfiles", views.PerfilesView.as_view()),
    path("perfiles/<str:id_perfil>", views.PerfilView.as_view()),
    path(
        "perfiles/<str:id_perfil>/consentimiento",
        views.ConsentimientoView.as_view(),
    ),
    path(
        "perfiles/<str:id_perfil>/configuracion-voz",
        views.ConfiguracionVozView.as_view(),
    ),
    path(
        "perfiles/<str:id_perfil>/interacciones",
        views.InteraccionesView.as_view(),
    ),
    path(
        "perfiles/<str:id_perfil>/interacciones/<str:id_interaccion>",
        views.InteraccionView.as_view(),
    ),
    path("perfiles/<str:id_perfil>/reportes", views.ReporteView.as_view()),
    path("pictogramas", views.PictogramasView.as_view()),
    path("pictogramas/<str:id_pictograma>", views.PictogramaView.as_view()),
    path("intenciones", views.IntencionesView.as_view()),
]
