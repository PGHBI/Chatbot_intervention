from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .utils import normalize_intervenants
import logging
import tempfile
import os
import requests
from .models import InterventionRequest, DocumentIntervention, Machine, Filiale
from .forms import InterventionRequestForm, DocumentInterventionForm
from .utils import generate_interventions_pdf, generate_detailed_intervention_pdf
from .rag_client import RAGClient
from .chromadb_manager import chromadb_manager
from . import pdf_extractor
from django.conf import settings
from .powerbi_embed import powerbi_service
logger = logging.getLogger(__name__)

def dashboard(request):
    """Vue du tableau de bord"""
    # Statistiques
    total_interventions = InterventionRequest.objects.count()
    faible = InterventionRequest.objects.filter(criticite='faible').count()
    moyenne = InterventionRequest.objects.filter(criticite='moyenne').count()
    haute = InterventionRequest.objects.filter(criticite='haute').count()
    critique = InterventionRequest.objects.filter(criticite='critique').count()
    
    # Statistiques des machines et filiales
    total_machines = Machine.objects.count()
    total_filiales = Filiale.objects.count()
    
    # Filtres
    search_query = request.GET.get('search', '')
    criticite_filter = request.GET.get('criticite', 'all')
    filiale_filter = request.GET.get('filiale', 'all')
    machine_filter = request.GET.get('machine', 'all')
    
    # Requête de base
    interventions = InterventionRequest.objects.all()
    
    # Appliquer les filtres
    if search_query:
        interventions = interventions.filter(
            Q(reference__icontains=search_query) |
            Q(objet__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(contact__icontains=search_query) |
            Q(machine__icontains=search_query)
        )
    
    if criticite_filter != 'all':
        interventions = interventions.filter(criticite=criticite_filter)
    
    if filiale_filter != 'all':
        interventions = interventions.filter(filiale=filiale_filter)
    
    if machine_filter != 'all':
        interventions = interventions.filter(machine=machine_filter)
    
    # Obtenir les filiales et machines pour les filtres
    filiales = Filiale.objects.values_list('name', flat=True).distinct()
    machines = Machine.objects.values_list('name', flat=True).distinct()
    
    # Pagination
    paginator = Paginator(interventions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get ChromaDB stats for dashboard
    chromadb_stats = chromadb_manager.get_collection_stats()
    
    context = {
        'stats': {
            'total': total_interventions,
            'faible': faible,
            'moyenne': moyenne,
            'haute': haute,
            'critique': critique,
            'machines': total_machines,
            'filiales': total_filiales,
        },
        'page_obj': page_obj,
        'search_query': search_query,
        'criticite_filter': criticite_filter,
        'filiale_filter': filiale_filter,
        'machine_filter': machine_filter,
        'criticite_choices': InterventionRequest.CRITICITE_CHOICES,
        'filiales': filiales,
        'machines': machines,
        'chromadb_stats': chromadb_stats,
    }
    
    return render(request, 'form/dashboard.html', context)


def nouvelle_intervention(request):
    """Vue pour créer une nouvelle intervention"""
    if request.method == 'POST':
        form = InterventionRequestForm(request.POST)
        if form.is_valid():
            intervention = form.save(commit=False)

    # Normalize intervenants before saving
            if intervention.intervenants:
                intervention.intervenants = normalize_intervenants(intervention.intervenants)

            intervention.save()
            messages.success(request, f'Intervention {intervention.reference} créée avec succès!')
            
            # The intervention will be automatically embedded via Django signals
            # Check if embedding was successful
            if chromadb_manager.is_available():
                messages.info(request, 'Intervention ajoutée à la base de connaissances IA.')
            
            return redirect('dashboard')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = InterventionRequestForm()
    
    # Get existing machines and filiales for autocomplete
    machines = Machine.objects.values_list('name', flat=True).order_by('name')
    filiales = Filiale.objects.values_list('name', flat=True).order_by('name')
    
    context = {
        'form': form,
        'machines': list(machines),
        'filiales': list(filiales),
    }
    
    return render(request, 'form/nouvelle_intervention.html', context)


def modifier_intervention(request, pk):
    """Vue pour modifier une intervention"""
    intervention = get_object_or_404(InterventionRequest, pk=pk)
    
    if request.method == 'POST':
        form = InterventionRequestForm(request.POST, instance=intervention)
        if form.is_valid():
            intervention = form.save(commit=False)

            # Normalize intervenants before saving
            if intervention.intervenants:
                intervention.intervenants = normalize_intervenants(intervention.intervenants)

            intervention.save()
            messages.success(request, f'Intervention {intervention.reference} modifiée avec succès!')
            
            # The intervention will be automatically updated in ChromaDB via Django signals
            if chromadb_manager.is_available():
                messages.info(request, 'Base de connaissances IA mise à jour.')
            
            return redirect('detail_intervention', pk=pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = InterventionRequestForm(instance=intervention)
    
    # Get existing machines and filiales for autocomplete
    machines = Machine.objects.values_list('name', flat=True).order_by('name')
    filiales = Filiale.objects.values_list('name', flat=True).order_by('name')
    
    context = {
        'form': form,
        'intervention': intervention,
        'machines': list(machines),
        'filiales': list(filiales),
    }
    
    return render(request, 'form/modifier_intervention.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def chatbot_api(request):
    """API endpoint for chatbot interactions using RAG system"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id', 'default_user')
        machines = Machine.objects.all()
        filiales = Filiale.objects.all()

        for machine in machines:
            if machine.name.lower() in user_message.lower():
                machine.query_counter += 1
                machine.save()
                print(f"Matched and incremented: {machine.name}") 
        for filiale in filiales:
            if filiale.name.lower() in user_message.lower():
                filiale.query_counter += 1
                filiale.save()
                print(f"Matched and incremented: {filiale.name}")             
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty'
            })
        
        # Check if this is a request for similar interventions
        if any(keyword in user_message.lower() for keyword in ['similaire', 'historique', 'passé', 'précédent']):
            # Use ChromaDB to find similar interventions
            similar_results = chromadb_manager.search_similar_interventions(user_message, n_results=5)
            
            if similar_results['documents'] and similar_results['documents'][0]:
                # Format the similar interventions response
                response_text = "Voici les interventions similaires que j'ai trouvées :\n\n"
                
                for i, (doc, metadata, distance) in enumerate(zip(
                    similar_results['documents'][0],
                    similar_results['metadatas'][0],
                    similar_results['distances'][0]
                )):
                    if metadata.get('type') == 'intervention':
                        response_text += f"**{i+1}. {metadata.get('reference', 'N/A')}**\n"
                        response_text += f"Machine: {metadata.get('machine', 'N/A')}\n"

                        response_text += f"Criticité: {metadata.get('criticite', 'N/A')}\n"
                        response_text += f"Date: {metadata.get('date_intervention', 'N/A')[:10]}\n"
                        response_text += f"Similarité: {(1-distance)*100:.1f}%\n\n"
                
                return JsonResponse({
                    'success': True,
                    'response': response_text,
                    'actions': [],
                    'context': similar_results['metadatas'][0][:3] if similar_results['metadatas'] else []
                })
        
        # Check for machine or filiale statistics requests
        if any(keyword in user_message.lower() for keyword in ['machine', 'équipement', 'filiale', 'statistique']):
            if 'machine' in user_message.lower() or 'équipement' in user_message.lower():
                machines = Machine.objects.order_by('-counter')[:5]
                response_text = "📊 **Top 5 des machines avec le plus d'interventions :**\n\n"
                for i, machine in enumerate(machines, 1):
                    response_text += f"{i}. **{machine.name}** - {machine.counter} interventions\n"
                
                return JsonResponse({
                    'success': True,
                    'response': response_text,
                    'actions': [],
                    'context': []
                })
            
            elif 'filiale' in user_message.lower():
                filiales = Filiale.objects.order_by('-counter')[:5]
                response_text = "🏢 **Top 5 des filiales avec le plus d'interventions :**\n\n"
                for i, filiale in enumerate(filiales, 1):
                    response_text += f"{i}. **{filiale.name}** - {filiale.counter} interventions\n"
                
                return JsonResponse({
                    'success': True,
                    'response': response_text,
                    'actions': [],
                    'context': []
                })
        
        # Initialize RAG client for general queries
        rag_client = RAGClient()
        
        # Check if RAG service is available
        if not rag_client.is_available():
            # Fallback to simple responses if RAG is not available
            return get_fallback_response(user_message)
        
        # Get response from RAG system
        rag_response = rag_client.get_response(user_message, user_id)
        
        # Extract response text
        response_text = rag_response.get('response', 'Désolé, je n\'ai pas pu traiter votre demande.')
        context = rag_response.get('context', [])
        
        # Determine if we should include any UI actions based on the response
        actions = determine_ui_actions(user_message, response_text)
        
        return JsonResponse({
            'success': True,
            'response': response_text,
            'actions': actions,
            'context': context[:3] if context else []  # Limit context for frontend
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in chatbot API request")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON format'
        })
    except Exception as e:
        logger.error(f"Error in chatbot API: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Une erreur interne s\'est produite'
        })


def get_fallback_response(user_message):
    """Fallback responses when RAG system is not available"""
    user_message_lower = user_message.lower()
    
    fallback_responses = {
        'nouvelle intervention': {
            'text': 'Pour créer une nouvelle intervention, cliquez sur le bouton "Nouvelle intervention" dans la navigation ou utilisez le bouton bleu "+ Nouvelle intervention" sur le tableau de bord.',
            'actions': [{'type': 'redirect', 'url': '/nouvelle/'}]
        },
        'interventions critiques': {
            'text': 'Vous pouvez filtrer les interventions critiques en utilisant le filtre "Criticité" sur le tableau de bord et en sélectionnant "Critique".',
            'actions': [{'type': 'filter', 'field': 'criticite', 'value': 'critique'}]
        },
        'rapport pdf': {
            'text': 'Pour générer un rapport PDF, utilisez le bouton "Rapport PDF" rouge sur le tableau de bord. Vous pouvez également générer un PDF pour une intervention spécifique.',
            'actions': [{'type': 'highlight', 'selector': 'a[href*="generate_pdf_report"]'}]
        },
        'statistiques': {
            'text': f'Voici les statistiques actuelles : {InterventionRequest.objects.count()} interventions au total, dont {InterventionRequest.objects.filter(criticite="critique").count()} critiques.',
            'actions': []
        },
        'aide': {
            'text': 'Je peux vous aider avec :\n• Création d\'interventions\n• Génération de rapports\n• Filtrage et recherche\n• Navigation dans l\'interface\n• Questions techniques sur la maintenance\n\nQue souhaitez-vous savoir ?',
            'actions': []
        }
    }
    
    # Find matching response
    for key, response in fallback_responses.items():
        if key in user_message_lower:
            return JsonResponse({
                'success': True,
                'response': response['text'],
                'actions': response['actions']
            })
    
    # Default fallback
    return JsonResponse({
        'success': True,
        'response': 'Le service de chat intelligent n\'est pas disponible actuellement. Je peux vous aider avec les fonctions de base de l\'application. Que souhaitez-vous faire ?',
        'actions': []
    })


def determine_ui_actions(user_message, response_text):
    """Determine UI actions based on user message and response"""
    actions = []
    user_message_lower = user_message.lower()
    
    # Add UI actions based on keywords in user message
    if 'nouvelle intervention' in user_message_lower or 'créer intervention' in user_message_lower:
        actions.append({'type': 'redirect', 'url': '/nouvelle/'})
    
    elif 'critique' in user_message_lower and 'intervention' in user_message_lower:
        actions.append({'type': 'filter', 'field': 'criticite', 'value': 'critique'})
    
    elif 'pdf' in user_message_lower or 'rapport' in user_message_lower:
        actions.append({'type': 'highlight', 'selector': 'a[href*="generate_pdf_report"]'})
    
    return actions


def generate_pdf_report(request):
    """Génère un rapport PDF des interventions"""
    # Récupérer les mêmes filtres que le dashboard
    search_query = request.GET.get('search', '')
    criticite_filter = request.GET.get('criticite', 'all')
    filiale_filter = request.GET.get('filiale', 'all')
    machine_filter = request.GET.get('machine', 'all')
    
    # Appliquer les mêmes filtres
    interventions = InterventionRequest.objects.all()
    
    if search_query:
        interventions = interventions.filter(
            Q(reference__icontains=search_query) |
            Q(objet__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(contact__icontains=search_query) |
            Q(machine__icontains=search_query)
        )
    
    if criticite_filter != 'all':
        interventions = interventions.filter(criticite=criticite_filter)
    
    if filiale_filter != 'all':
        interventions = interventions.filter(filiale=filiale_filter)
    
    if machine_filter != 'all':
        interventions = interventions.filter(machine=machine_filter)
    
    # Préparer les informations de filtres pour le PDF
    filters = {
        'search': search_query,
        'criticite': criticite_filter,
        'filiale': filiale_filter,
        'machine': machine_filter
    }
    
    # Générer le PDF
    pdf_content = generate_interventions_pdf(interventions, filters)
    
    # Créer la réponse HTTP
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"rapport_interventions_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


def generate_intervention_pdf(request, pk):
    """Génère un PDF détaillé pour une intervention spécifique"""
    intervention = get_object_or_404(InterventionRequest, pk=pk)
    
    # Générer le PDF
    pdf_content = generate_detailed_intervention_pdf(intervention)
    
    # Créer la réponse HTTP
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"intervention_{intervention.reference}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


def detail_intervention(request, pk):
    """Vue de détail d'une intervention"""
    intervention = get_object_or_404(InterventionRequest, pk=pk)
    documents = intervention.documents.all()
    
    # Get similar interventions from ChromaDB
    similar_interventions = []
    if chromadb_manager.is_available():
        query_text = f"{intervention.objet} {intervention.description} {intervention.machine}"
        similar_results = chromadb_manager.search_similar_interventions(query_text, n_results=5)
        
        if similar_results['documents'] and similar_results['documents'][0]:
            for metadata, distance in zip(similar_results['metadatas'][0], similar_results['distances'][0]):
                if (metadata.get('type') == 'intervention' and 
                    metadata.get('reference') != intervention.reference and
                    distance < 0.7):  # Only show reasonably similar interventions
                    similar_interventions.append({
                        'reference': metadata.get('reference'),
                        'machine': metadata.get('machine'),
                        'criticite': metadata.get('criticite'),
                        'similarity': (1-distance)*100
                    })
    
    context = {
        'intervention': intervention,
        'documents': documents,
        'similar_interventions': similar_interventions[:3],  # Show top 3 similar
    }
    
    return render(request, 'form/detail_intervention.html', context)


def supprimer_intervention(request, pk):
    """Vue pour supprimer une intervention"""
    intervention = get_object_or_404(InterventionRequest, pk=pk)
    
    if request.method == 'POST':
        reference = intervention.reference
        intervention.delete()
        messages.success(request, f'Intervention {reference} supprimée avec succès!')
        
        # The intervention will be automatically removed from ChromaDB via Django signals
        if chromadb_manager.is_available():
            messages.info(request, 'Intervention supprimée de la base de connaissances IA.')
        
        return redirect('dashboard')
    
    return render(request, 'form/supprimer_intervention.html', {'intervention': intervention})


def upload_document(request, pk):
    """Vue pour uploader un document"""
    intervention = get_object_or_404(InterventionRequest, pk=pk)
    
    if request.method == 'POST':
        form = DocumentInterventionForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.intervention = intervention
            if not document.nom_fichier:
                document.nom_fichier = document.fichier.name
            document.save()
            
            # Try to extract information from PDF if it's a PDF file
            if document.fichier.name.lower().endswith('.pdf'):
                try:
                    pdf_path = document.fichier.path
                    text = pdf_extractor.extract_text_from_pdf(pdf_path)
                    if text:
                        extracted_data = pdf_extractor.extract_information_with_ai(text)
                        
                        # Update intervention with extracted data if fields are empty
                        updated_fields = []
                        for field, value in extracted_data.items():
                            if hasattr(intervention, field) and value:
                                current_value = getattr(intervention, field)
                                # Only update if current field is empty or has default value
                                if not current_value or current_value in ['', 'N/A', 'Non spécifié']:
                                    setattr(intervention, field, value)
                                    updated_fields.append(field)
                        
                        if updated_fields:
                            intervention.save()
                            logger.info(f"Updated intervention {intervention.reference} with PDF data: {updated_fields}")
                            
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': True, 
                                    'message': f'Document uploadé et {len(updated_fields)} champs mis à jour automatiquement!',
                                    'updated_fields': updated_fields
                                })
                            else:
                                messages.success(request, f'Document uploadé et {len(updated_fields)} champs mis à jour automatiquement!')
                        
                except Exception as e:
                    logger.error(f"Error extracting PDF data: {e}")
                    # Continue with normal upload even if extraction fails
            
            # Update the intervention in ChromaDB to include the new document
            if chromadb_manager.is_available():
                chromadb_manager.update_intervention(intervention)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Document uploadé avec succès!'})
            else:
                messages.success(request, 'Document uploadé avec succès!')
                return redirect('detail_intervention', pk=pk)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    
    return redirect('detail_intervention', pk=pk)


def extract_pdf_data(request):
    """API endpoint to extract data from uploaded PDF"""
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        try:
            pdf_file = request.FILES['pdf_file']
            
            # Save temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                for chunk in pdf_file.chunks():
                    tmp_file.write(chunk)
                tmp_path = tmp_file.name
            
            try:
                # Extract information
                text = pdf_extractor.extract_text_from_pdf(tmp_path)
                if text:
                    extracted_data = pdf_extractor.extract_information_with_ai(text)
                    
                    return JsonResponse({
                        'success': True,
                        'extracted_data': extracted_data,
                        'text_length': len(text)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Could not extract text from PDF'
                    })
            finally:
                # Clean up temporary file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Error in PDF extraction API: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'No PDF file provided'
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_intervention_from_pdf(request):
    """Create intervention directly from PDF upload"""
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        try:
            pdf_file = request.FILES['pdf_file']
            
            # Save temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                for chunk in pdf_file.chunks():
                    tmp_file.write(chunk)
                tmp_path = tmp_file.name
            
            try:
                # Create intervention from PDF
                intervention, extracted_data = pdf_extractor.create_intervention_from_pdf(tmp_path)
                
                messages.success(
                    request, 
                    f'Intervention {intervention.reference} créée automatiquement depuis le PDF! '
                    f'{len(extracted_data)} champs extraits.'
                )
                
                return JsonResponse({
                    'success': True,
                    'intervention_id': intervention.pk,
                    'reference': intervention.reference,
                    'extracted_fields': len(extracted_data),
                    'redirect_url': f'/intervention/{intervention.pk}/'
                })
                
            finally:
                # Clean up temporary file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Error creating intervention from PDF: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'No PDF file provided'
    })
from django.shortcuts import render
def powerbi_dashboard(request):
    """Vue du dashboard Power BI avec iframe"""
    # Get saved Power BI URL from session or settings if needed
    powerbi_url = request.session.get('powerbi_url', '')
    
    context = {
        'powerbi_url': powerbi_url,
    }
    
    return render(request, 'form/powerbi_dashboard.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def powerbi_refresh_data(request):
    """API endpoint to trigger data refresh in Power BI"""
    try:
        # This endpoint can be called when data changes
        # to notify Power BI to refresh its data
        
        # You can implement logic here to:
        # 1. Trigger dataset refresh in Power BI Service
        # 2. Update any cached data
        # 3. Send notifications
        
        return JsonResponse({
            'success': True,
            'message': 'Data refresh triggered successfully'
        })
        
    except Exception as e:
        logger.error(f"Error triggering Power BI refresh: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)