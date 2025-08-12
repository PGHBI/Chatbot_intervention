from reportlab.lib import colors
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak , Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.http import HttpResponse
from django.utils import timezone
from .models import InterventionRequest,Technician

import io
import os
import re
import unicodedata
import difflib
from django.conf import settings
from pathlib import Path
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for (page_num, state) in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self.draw_page_number(page_num + 1, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_num, total_pages):
        self.setFont("Helvetica", 9)
        self.drawRightString(200*inch/25.4, 0.75*inch, f"Page {page_num} sur {total_pages}")


def generate_interventions_pdf(interventions, filters=None):
    """Génère un PDF avec la liste des interventions"""
    
    # Créer le buffer
    buffer = io.BytesIO()
    
    # Créer le document PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1d4ed8')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#374151')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=12,
        alignment=TA_LEFT
    )
    
    # Contenu du PDF
    story = []
    
    # Titre principal
    title = Paragraph("Rapport des Interventions", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Informations du rapport
    date_generation = timezone.now().strftime("%d/%m/%Y à %H:%M")
    info_text = f"<b>Date de génération :</b> {date_generation}<br/>"
    info_text += f"<b>Nombre d'interventions :</b> {interventions.count()}<br/>"
    
    if filters:
        info_text += "<b>Filtres appliqués :</b><br/>"
        if filters.get('search'):
            info_text += f"• Recherche : {filters['search']}<br/>"
        if filters.get('criticite') and filters['criticite'] != 'all':
            info_text += f"• Criticité : {dict(InterventionRequest.CRITICITE_CHOICES)[filters['criticite']]}<br/>"
        if filters.get('filiale') and filters['filiale'] != 'all':
            info_text += f"• Filiale : {filters['filiale']}<br/>"
    
    info_para = Paragraph(info_text, normal_style)
    story.append(info_para)
    story.append(Spacer(1, 30))
    
    # Statistiques
    stats_title = Paragraph("Statistiques par Criticité", subtitle_style)
    story.append(stats_title)
    
    # Calculer les statistiques
    total = interventions.count()
    faible = interventions.filter(criticite='faible').count()
    moyenne = interventions.filter(criticite='moyenne').count()
    haute = interventions.filter(criticite='haute').count()
    critique = interventions.filter(criticite='critique').count()
    
    # Tableau des statistiques
    stats_data = [
        ['Criticité', 'Nombre', 'Pourcentage'],
        ['Faible', str(faible), f"{(faible/total*100):.1f}%" if total > 0 else "0%"],
        ['Moyenne', str(moyenne), f"{(moyenne/total*100):.1f}%" if total > 0 else "0%"],
        ['Haute', str(haute), f"{(haute/total*100):.1f}%" if total > 0 else "0%"],
        ['Critique', str(critique), f"{(critique/total*100):.1f}%" if total > 0 else "0%"],
        ['Total', str(total), '100%']
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1*inch, 1.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 30))
    
    # Liste des interventions
    if interventions.exists():
        interventions_title = Paragraph("Liste des Interventions", subtitle_style)
        story.append(interventions_title)
        
        # En-têtes du tableau
        data = [['Référence', 'Objet', 'Filiale', 'Machine', 'Criticité', 'Date', 'Contact']]
        
        # Données des interventions
        for intervention in interventions:
            criticite_colors = {
                'faible': colors.green,
                'moyenne': colors.orange,
                'haute': colors.red,
                'critique': colors.darkred
            }
            
            row = [
                intervention.reference,
                intervention.objet[:30] + "..." if len(intervention.objet) > 30 else intervention.objet,
                intervention.filiale[:20] + "..." if len(intervention.filiale) > 20 else intervention.filiale,
                intervention.machine[:20] + "..." if len(intervention.machine) > 20 else intervention.machine,
                intervention.get_criticite_display(),
                intervention.date_intervention.strftime("%d/%m/%Y"),
                intervention.contact[:20] + "..." if len(intervention.contact) > 20 else intervention.contact
            ]
            data.append(row)
        
        # Créer le tableau
        table = Table(data, colWidths=[1*inch, 1.5*inch, 1*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch])
        
        # Style du tableau
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]
        
        # Colorer les criticités
        for i, intervention in enumerate(interventions, 1):
            if intervention.criticite == 'critique':
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#fee2e2')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#dc2626')))
            elif intervention.criticite == 'haute':
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#fed7aa')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#ea580c')))
            elif intervention.criticite == 'moyenne':
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#fef3c7')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#d97706')))
            elif intervention.criticite == 'faible':
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#dcfce7')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#16a34a')))
        
        table.setStyle(TableStyle(table_style))
        story.append(table)
    
    else:
        no_data = Paragraph("Aucune intervention trouvée avec les critères sélectionnés.", normal_style)
        story.append(no_data)
    
    # Construire le PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Récupérer le contenu du buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf
def get_logo_path():
    """Trouve le chemin du logo dans les dossiers static"""
    # Cherche dans tous les dossiers déclarés dans STATICFILES_DIRS
    for static_dir in settings.STATICFILES_DIRS:
        logo_path = Path(static_dir) / 'images' / 'poulina.png'
        if logo_path.exists():
            return logo_path
    
    # Fallback si non trouvé
    return None

def generate_detailed_intervention_pdf(intervention):
    """Génère un PDF de rapport d'intervention à partir d'une instance du modèle"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                          rightMargin=72, leftMargin=72, 
                          topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#001F5F'),
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=20
    )
    
    subheader_style = ParagraphStyle(
        'SubheaderStyle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#001F5F'),
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=10
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        spaceAfter=10
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        leftIndent=10,
        spaceAfter=5
    )
    
    story = []
    
    # Gestion du logo (votre modèle n'a pas de logo, donc placeholder)
    

    logo_path = get_logo_path()
    if logo_path:
        logo = Image(str(logo_path), width=94, height=39)
    else:
        logo = Paragraph("LOGO", styles['Normal'])
    # En-tête avec "Unité automatisme"
    unit_box = Table([
        [Paragraph("Unité automatisme", subheader_style)]
    ], colWidths=[154.6], rowHeights=[28])
    
    unit_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('LEFTPADDING', (0, 0), (-1, -1), 31),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    # Titre principal
    title_box = Table([
        [Paragraph("Rapport d'intervention", header_style)]
    ], colWidths=[341.2], rowHeights=[28])
    
    title_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('LEFTPADDING', (0, 0), (-1, -1), 96),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    # Construction de l'en-tête
    header_table = Table([
        [unit_box, '', ''],
        ['', title_box, ''],
        [logo, '', '']
    ], colWidths=[154.6, 20, 341.2], rowHeights=[28, 28, 39])
    
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Ligne de référence
    ref_text = f"Référence d'intervention : {intervention.reference}"
    story.append(Paragraph(ref_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Tableau d'informations principales (adapté à votre modèle)
    info_data = [
        ['Date', intervention.date_intervention.strftime("%d/%m/%Y %H:%M"), 
         'Contact', intervention.contact],
        ['Filiale', intervention.filiale, 
         'Tel', intervention.numero_telephone],
        ['Intervenant(s)', intervention.intervenants, 
         'Machine', intervention.machine],
        ['Responsable(s)', intervention.responsables, 
         'Criticité', intervention.get_criticite_display()],
        ['Diffusion', intervention.diffuseur, '', '']
    ]
    
    info_table = Table(info_data, colWidths=[89, 131, 92, 162])
    
    info_table.setStyle(TableStyle([

        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (2, 1), (2, 1), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (2, 2), (2, 2), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (0, 3), (0, 3), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (2, 3), (2, 3), colors.HexColor('#F0F0F0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Section Objet
    objet_table = Table([
        ['Objet', intervention.objet]
    ], colWidths=[119, 448])
    
    objet_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(objet_table)
    
    # Section Description
    desc_table = Table([
        ['Description', intervention.description]
    ], colWidths=[119, 448])
    
    desc_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F0F0F0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 5),
        ('LEFTPADDING', (1, 0), (1, 0), 23),
    ]))
    
    story.append(desc_table)
    story.append(Spacer(1, 20))
    
    # Section Recommandations
    reco_text = intervention.recommandations if intervention.recommandations else "Aucune recommandation"
    reco_table = Table([
        ['Recommandation', reco_text]
    ], colWidths=[119, 448])
    
    reco_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(reco_table)
    
    # Génération du PDF
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf
def normalize_intervenants(raw_intervenants):
    # Ensure we work with a list of names
    if isinstance(raw_intervenants, str):
        names = [name.strip() for name in raw_intervenants.split(',') if name.strip()]
    elif isinstance(raw_intervenants, list):
        names = [name.strip() for name in raw_intervenants if isinstance(name, str) and name.strip()]
    else:
        raise ValueError("Invalid intervenants format. Must be string or list.")

    def canonical_name(name):
        # Normalize and sort words alphabetically (to match Hassan Yassine = Yassine Hassan)
        name = name.lower()
        name = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('utf-8')  # Remove accents
        words = re.findall(r'\w+', name)
        return ''.join(sorted(words))

    cleaned_names = []
    known_names = list(Technician.objects.values_list("name", flat=True))
    known_canonicals = {canonical_name(k): k for k in known_names}

    for name in names:
        # Title case and sort parts for consistent display
        name_parts_sorted = ' '.join(sorted(name.title().split()))
        name_canonical = canonical_name(name_parts_sorted)

        # Try to match with known canonicals
        match = difflib.get_close_matches(name_canonical, list(known_canonicals.keys()), cutoff=0.85, n=1)

        if match:
            matched_canonical = match[0]
            cleaned_names.append(known_canonicals[matched_canonical])
        else:
            # Create new technician
            Technician.objects.create(name=name_parts_sorted)
            cleaned_names.append(name_parts_sorted)
            known_canonicals[name_canonical] = name_parts_sorted

    return ', '.join(cleaned_names)