import os
import json
import difflib
from PyPDF2 import PdfReader
from form.models import Machine, Filiale, InterventionRequest
from form.models import Technician
from datetime import datetime
from openai import OpenAI
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
import re
import unicodedata
GITHUB_TOKEN = "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"
endpoint = "https://models.github.ai/inference"
clients = OpenAI(
    base_url=endpoint,
    api_key=GITHUB_TOKEN,
)
def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        return "\n".join([page.extract_text() or '' for page in reader.pages])
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def get_known_names(model):
    return list(model.objects.values_list("name", flat=True))


def normalize_name(name):
    name = name.lower()
    name = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('utf-8')  # remove accents
    name = re.sub(r'[\s\-]', '', name)  # remove spaces and dashes
    return name

def fuzzy_match(name, known_list):
    if not name:
        return ""
    
    normalized_input = normalize_name(name)
    normalized_knowns = [(normalize_name(k), k) for k in known_list]
    
    closest = difflib.get_close_matches(normalized_input, [nk[0] for nk in normalized_knowns], n=1, cutoff=0.6)
    
    if closest:
        # Return the original known name, not the normalized one
        for norm, orig in normalized_knowns:
            if norm == closest[0]:
                return orig
    return name  
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



def extract_information_with_ai(text):
    prompt = f"""
Tu es un assistant intelligent. À partir du texte d'un rapport d'intervention, extrait les données suivantes du texte dans un format JSON STRICTEMENT VALIDE:

- reference
- date_intervention (format YYYY-MM-DD)
- contact
- telephone
- filiale
- machine
- intervenants
- responsables
- criticite (faible, moyenne, haute, critique)
- diffuseur
- objet
- description
- recommandations

Texte :
\"\"\"
{text}
\"\"\"
    """

    try:
        response = clients.chat.completions.create(
            model="openai/gpt-4.1",  # or gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        message_content = response.choices[0].message.content
        
        
        if message_content.startswith("```"):
            message_content = message_content.strip("` \n")
            lines = message_content.splitlines()
            if lines[0].startswith("json"):
                lines = lines[1:]
            message_content = "\n".join(lines)

        print(f"⚠️ GPT Raw Output:\n{message_content}")

        try:
            data = json.loads(message_content)
        except json.JSONDecodeError:
            raise RuntimeError(f"Model response is not valid JSON:\n{message_content}")        

        # Fuzzy match known names
        data["machine"] = fuzzy_match(data.get("machine", ""), get_known_names(Machine))
        data["filiale"] = fuzzy_match(data.get("filiale", ""), get_known_names(Filiale))

        # Parse date
        if data.get("date_intervention"):
            data["date_intervention"] = datetime.strptime(data["date_intervention"], "%Y-%m-%d")

        return data
    except Exception as e:
        raise RuntimeError(f"AI extraction failed: {e}")


def create_intervention_from_pdf(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    data = extract_information_with_ai(text)

    intervention = InterventionRequest.objects.create(
        reference=data["reference"],
        date_intervention=data["date_intervention"],
        contact=data["contact"],
        numero_telephone=data.get("telephone", ""),
        filiale=data["filiale"],
        machine=data["machine"],
        intervenants=normalize_intervenants(data["intervenants"]),
        responsables=data["responsables"],
        criticite=data["criticite"] or "moyenne",
        diffuseur=data["diffuseur"],
        objet=data["objet"][:1000],
        description=data["description"],
        recommandations=data.get("recommandations", "")
    )

    return intervention, data
