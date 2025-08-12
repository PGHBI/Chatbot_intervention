from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('nouvelle/', views.nouvelle_intervention, name='nouvelle_intervention'),
    path('intervention/<int:pk>/', views.detail_intervention, name='detail_intervention'),
    path('intervention/<int:pk>/modifier/', views.modifier_intervention, name='modifier_intervention'),
    path('intervention/<int:pk>/supprimer/', views.supprimer_intervention, name='supprimer_intervention'),
    path('intervention/<int:pk>/upload/', views.upload_document, name='upload_document'),
    path('rapport/pdf/', views.generate_pdf_report, name='generate_pdf_report'),
    path('intervention/<int:pk>/pdf/', views.generate_intervention_pdf, name='generate_intervention_pdf'),
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),
    path('api/extract-pdf/', views.extract_pdf_data, name='extract_pdf_data'),
    path('api/create-from-pdf/', views.create_intervention_from_pdf, name='create_intervention_from_pdf'),
    path('powerbi/', views.powerbi_dashboard, name='powerbi_dashboard'),
]
