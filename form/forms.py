from django import forms
from .models import InterventionRequest, DocumentIntervention, Machine, Filiale


class InterventionRequestForm(forms.ModelForm):
    """Formulaire pour créer une demande d'intervention"""
    
    # Champs pour l'autocomplétion
    machine_suggestions = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    filiale_suggestions = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    class Meta:
        model = InterventionRequest
        fields = [
            'date_intervention', 'contact', 'numero_telephone', 'filiale',
            'intervenants', 'responsables', 'machine', 'criticite', 'diffuseur',
            'objet', 'description', 'recommandations'
        ]
        
        widgets = {
            'date_intervention': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'type': 'datetime-local'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'placeholder': 'Nom du contact'
            }),
            'numero_telephone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'placeholder': '+33 1 23 45 67 89'
            }),
            'filiale': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'placeholder': 'Nom de la filiale',
                'list': 'filiale-suggestions',
                'autocomplete': 'off'
            }),
            'intervenants': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200 resize-none',
                'rows': 3,
                'placeholder': 'Liste des intervenants (un par ligne ou séparés par des virgules)'
            }),
            'responsables': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200 resize-none',
                'rows': 3,
                'placeholder': 'Liste des responsables (un par ligne ou séparés par des virgules)'
            }),
            'machine': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'placeholder': 'Nom ou référence de la machine',
                'list': 'machine-suggestions',
                'autocomplete': 'off'
            }),
            'criticite': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200'
            }),
            'diffuseur': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'placeholder': 'Nom de la personne qui a diffusé l\'intervention'
            }),
            'objet': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200',
                'placeholder': 'Objet de l\'intervention'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200 resize-none',
                'rows': 4,
                'placeholder': 'Description détaillée de l\'intervention à réaliser'
            }),
            'recommandations': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-slate-400 transition-all duration-200 resize-none',
                'rows': 4,
                'placeholder': 'Recommandations des intervenants (optionnel)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre certains champs obligatoires
        self.fields['date_intervention'].required = True
        self.fields['contact'].required = True
        self.fields['numero_telephone'].required = True
        self.fields['filiale'].required = True
        self.fields['intervenants'].required = True
        self.fields['responsables'].required = True
        self.fields['machine'].required = True
        self.fields['diffuseur'].required = True
        self.fields['objet'].required = True
        self.fields['description'].required = True


class DocumentInterventionForm(forms.ModelForm):
    """Formulaire pour uploader des documents"""
    
    class Meta:
        model = DocumentIntervention
        fields = ['fichier', 'nom_fichier']
        
        widgets = {
            'fichier': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.xls,.xlsx'
            }),
            'nom_fichier': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Nom du document'
            })
        }