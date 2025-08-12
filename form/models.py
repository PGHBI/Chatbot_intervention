from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid


class Machine(models.Model):
    """Modèle pour les machines"""
    name = models.CharField(max_length=200, unique=True, verbose_name="Nom de la machine")
    counter = models.PositiveIntegerField(default=0, verbose_name="Nombre d'interventions")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    query_counter = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.counter} interventions)"


class Filiale(models.Model):
    """Modèle pour les filiales"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de la filiale")
    counter = models.PositiveIntegerField(default=0, verbose_name="Nombre d'interventions")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    query_counter = models.IntegerField(default=0)
    class Meta:
        verbose_name = "Filiale"
        verbose_name_plural = "Filiales"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.counter} interventions)"


class InterventionRequest(models.Model):
    """Modèle pour les demandes d'intervention"""
    
    CRITICITE_CHOICES = [
        ('faible', 'Faible'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
        ('critique', 'Critique'),
    ]
    
    # Référence unique de l'intervention
    reference = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Référence de l'intervention",
        help_text="Référence unique générée automatiquement"
    )
    
    # Date de l'intervention
    date_intervention = models.DateTimeField(verbose_name="Date de l'intervention")
    
    # Contact et téléphone
    contact = models.CharField(max_length=100, verbose_name="Contact")
    numero_telephone = models.CharField(max_length=20, verbose_name="Numéro de téléphone",default='')
    
    # Relations avec Machine et Filiale
    machine_obj = models.ForeignKey(
        Machine, 
        on_delete=models.CASCADE, 
        related_name='interventions',
        verbose_name="Machine (objet)",
        null=True,
        blank=True
    )
    filiale_obj = models.ForeignKey(
        Filiale, 
        on_delete=models.CASCADE, 
        related_name='interventions',
        verbose_name="Filiale (objet)",
        null=True,
        blank=True
    )
    
    # Champs texte pour compatibilité (seront synchronisés avec les objets)
    filiale = models.CharField(max_length=100, verbose_name="Filiale")
    machine = models.CharField(max_length=200, verbose_name="Machine")
    
    # Intervenants et responsables
    intervenants = models.TextField(verbose_name="Intervenant(s)")
    responsables = models.TextField(verbose_name="Responsable(s)")
    
    # Criticité de l'intervention
    criticite = models.CharField(
        max_length=10, 
        choices=CRITICITE_CHOICES, 
        default='moyenne',
        verbose_name="Criticité de l'intervention"
    )
    
    # Qui a diffusé l'intervention
    diffuseur = models.CharField(max_length=100, verbose_name="Diffusé par")
    
    # Objet de l'intervention
    objet = models.CharField(max_length=1000, verbose_name="Objet de l'intervention")
    
    # Description de l'intervention
    description = models.TextField(verbose_name="Description de l'intervention")
    
    # Recommandations des intervenants
    recommandations = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Recommandations des intervenants"
    )
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
    class Meta:
        verbose_name = "Demande d'intervention"
        verbose_name_plural = "Demandes d'intervention"
        ordering = ['-date_creation']
    
    def save(self, *args, **kwargs):
        if not self.reference:
            # Générer une référence unique
            self.reference = f"INT-{uuid.uuid4().hex[:8].upper()}"
        
        # Synchroniser les objets Machine et Filiale avec les champs texte
        if self.machine:
            machine_obj, created = Machine.objects.get_or_create(
                name=self.machine,
                defaults={'counter': 0}
            )
            self.machine_obj = machine_obj
        
        if self.filiale:
            filiale_obj, created = Filiale.objects.get_or_create(
                name=self.filiale,
                defaults={'counter': 0}
            )
            self.filiale_obj = filiale_obj
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference} - {self.objet}"
class Technician(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class DocumentIntervention(models.Model):
    """Modèle pour les documents liés aux interventions"""
    
    intervention = models.ForeignKey(
        InterventionRequest, 
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Intervention"
    )
    fichier = models.FileField(
        upload_to='interventions/documents/',
        verbose_name="Fichier joint"
    )
    nom_fichier = models.CharField(max_length=255, verbose_name="Nom du fichier")
    date_upload = models.DateTimeField(auto_now_add=True, verbose_name="Date d'upload")
    
    class Meta:
        verbose_name = "Document d'intervention"
        verbose_name_plural = "Documents d'intervention"
    
    def __str__(self):
        return f"{self.nom_fichier} - {self.intervention.reference}"