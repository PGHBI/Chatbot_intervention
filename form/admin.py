from django.contrib import admin
from .models import InterventionRequest, DocumentIntervention, Machine, Filiale


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ['name', 'counter', 'date_creation', 'date_modification']
    list_filter = ['date_creation', 'date_modification']
    search_fields = ['name']
    readonly_fields = ['counter', 'date_creation', 'date_modification']
    ordering = ['name']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name',)
        }),
        ('Statistiques', {
            'fields': ('counter',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Filiale)
class FilialeAdmin(admin.ModelAdmin):
    list_display = ['name', 'counter', 'date_creation', 'date_modification']
    list_filter = ['date_creation', 'date_modification']
    search_fields = ['name']
    readonly_fields = ['counter', 'date_creation', 'date_modification']
    ordering = ['name']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name',)
        }),
        ('Statistiques', {
            'fields': ('counter',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(InterventionRequest)
class InterventionRequestAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'objet', 'contact', 'criticite', 'filiale', 
        'machine', 'date_intervention', 'date_creation'
    ]
    list_filter = ['criticite', 'filiale_obj', 'machine_obj', 'date_intervention', 'date_creation']
    search_fields = ['reference', 'objet', 'contact', 'machine', 'description', 'filiale']
    readonly_fields = ['reference', 'date_creation', 'date_modification', 'machine_obj', 'filiale_obj']
    
    fieldsets = (
        ('Référence et Date', {
            'fields': ('reference', 'date_intervention')
        }),
        ('Contact et Filiale', {
            'fields': ('contact', 'numero_telephone', 'filiale', 'filiale_obj', 'diffuseur')
        }),
        ('Intervention', {
            'fields': ('objet', 'description', 'machine', 'machine_obj', 'criticite')
        }),
        ('Équipe', {
            'fields': ('intervenants', 'responsables')
        }),
        ('Recommandations', {
            'fields': ('recommandations',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DocumentIntervention)
class DocumentInterventionAdmin(admin.ModelAdmin):
    list_display = ['nom_fichier', 'intervention', 'date_upload']
    list_filter = ['date_upload']
    search_fields = ['nom_fichier', 'intervention__reference', 'intervention__objet']