import pika
import json
from mistralai.client import MistralClient
from mistralai import Mistral
from chromadb import PersistentClient
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import requests
import os
from openai import OpenAI
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
import redis
import logging
# from form.models import Machine
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis client
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    redis_client.ping()
    logger.info("Redis connection successful")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

# Initialize ChromaDB and SentenceTransformer
try:
    client = PersistentClient(
        path="../chroma_data",
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection("pdf_knowledge_base")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("ChromaDB and SentenceTransformer initialized successfully")
except Exception as e:
    logger.error(f"Error initializing ChromaDB or SentenceTransformer: {e}")
    raise

# Initialize RabbitMQ connection
try:
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()
    
    channel.queue_declare(queue="query_queue")
    channel.queue_declare(queue="response_queue")
    logger.info("RabbitMQ connection established successfully")
except Exception as e:
    logger.error(f"Error connecting to RabbitMQ: {e}")
    raise

#######################################################################################################
# GitHub Models Configuration
GITHUB_TOKEN = "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"

endpoint = "https://models.github.ai/inference"
model_name = "core42/jais-30b-chat"

modele = "openai/gpt-4.1"
clients = OpenAI(
    base_url=endpoint,
    api_key=GITHUB_TOKEN,
)

def generate_response(user_query, context_text, history=None):
    """
    Generate a response using the OpenAI API with context and conversation history
    
    Args:
        user_query (str): The user's question
        context_text (str): Relevant context from the knowledge base
        history (list): Previous conversation history
        
    Returns:
        str: Generated response
    """
    if history is None:
        history = []

    # Build the message list starting with the system message and context
    messages = [
        {
            "role": "system",
            "content": "Vous êtes un assistant utile qui fournit des réponses concises basées sur le contexte fourni."
        },
        {
            "role": "user",
            "content": f"""Vous êtes un assistant spécialisé en maintenance industrielle et résolution de problèmes techniques.

CONTEXTE DISPONIBLE :
{context_text}

REQUÊTE UTILISATEUR :
{user_query}

INSTRUCTIONS :
1. **Analyse de la requête** :
   - Si l'utilisateur décrit un problème spécifique, recherchez d'abord des interventions similaires dans les données historiques
   - Si l'utilisateur demande l'historique d'une machine/équipement, listez les interventions passées de manière chronologique
  
2. **Réponse structurée** :
   - Pour un nouveau problème : Fournissez des recommandations basées sur les cas similaires trouvés
   - Pour l'historique : Présentez les interventions passées avec dates, types d'intervention et résultats
   - Si aucune donnée similaire n'existe, utilisez vos connaissances techniques générales

3. **Format de réponse** :
   - Commencez par un résumé de votre analyse
   - Listez les recommandations/historique de manière structurée
   - Incluez les références aux interventions passées quand pertinent
   - Terminez par des questions de clarification si nécessaire
   - Classez les recommandations par probabilité de succès basée sur l'historique

4. **Critères de qualité** :
   - Réponses concises mais complètes (maximum 300 mots)
   - Priorisez les solutions éprouvées
   - Mentionnez les niveaux de risque si applicable
   - Demandez des précisions si la requête est ambiguë

Si la requête ne concerne pas la maintenance ou les équipements techniques, répondez brièvement et redirigez vers votre domaine d'expertise.

RÉPONSE :"""
        }
    ]

    # Append previous conversation history (limit to last 10 messages to avoid token limits)
    recent_history = history[-10:] if len(history) > 10 else history
    for msg in recent_history:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            messages.append({"role": "assistant", "content": msg["content"]})

    try:
        response = clients.chat.completions.create(
            model=modele,  
            messages=messages,
            max_tokens=500,  # Limit response length
            temperature=0.7,  # Balanced creativity
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error with OpenAI API: {e}")
        return "Désolé, je ne peux pas générer une réponse pour le moment. Veuillez réessayer plus tard."

def process_query(ch, method, properties, body):
    """
    Process incoming queries from RabbitMQ
    
    Args:
        ch: Channel
        method: Method
        properties: Properties
        body: Message body containing the query
    """
    try:
        request_data = json.loads(body)
        user_query = request_data.get("query")
        

        user_id = request_data.get("user_id", "default_user")
        
        logger.info(f"Processing query from user {user_id}: {user_query[:100]}...")
        
        # Generate query embedding
        query_embedding = model.encode(user_query).tolist()
        
        # Get conversation history from Redis
        history = []
        if redis_client:
            history_key = f"chat_history:{user_id}"
            history_json = redis_client.get(history_key)
            history = json.loads(history_json) if history_json else []
        
        # Add current user message to history
        history.append({"role": "user", "content": user_query})
        
        # Query the knowledge base
        results = collection.query(
            query_embedding, 
            include=["documents", "metadatas", "distances"], 
            n_results=10
        )

        response_data = {"response": "No relevant documents found", "context": []}

        if "documents" in results and results["documents"]:
            # Process and rank the results
            top_matches = sorted(
                [
                    {
                        "text": doc,
                        "source": meta.get("source", "Document inconnu"),
                        "page": meta.get("page"),
                        "year": meta.get("year"),
                        "similarity": dist,
                    }
                    for doc, meta, dist in zip(
                        results["documents"][0],
                        results["metadatas"][0],
                        results["distances"][0],
                    )
                ],
                key=lambda x: x["similarity"],
            )[:5]  # Get only the top 5 matches

            # Prepare context text
            context_text = "\n\n".join([match["text"] for match in top_matches])
            
            # Generate response using the AI model
            response = generate_response(user_query, context_text, history)
            
            # Append assistant response to history
            history.append({"role": "assistant", "content": response})

            # Store updated history back in Redis with expiration (1 hour)
            if redis_client:
                history_key = f"chat_history:{user_id}"
                redis_client.setex(history_key, 3600, json.dumps(history))
            
            # Prepare response data
            response_data = {
                "response": response,
                "context": [
                    {
                        "source": match["source"],
                        "page": match["page"],
                        "year": match["year"],
                        "similarity": round(match["similarity"], 3)
                    }
                    for match in top_matches
                ],
            }
            
            logger.info(f"Generated response for user {user_id} with {len(top_matches)} context sources")
        else:
            logger.warning(f"No relevant documents found for query: {user_query[:100]}...")
            # Still add to history and generate a general response
            general_response = generate_response(user_query, "Aucun document spécifique trouvé dans la base de connaissances.", history)
            history.append({"role": "assistant", "content": general_response})
            
            if redis_client:
                history_key = f"chat_history:{user_id}"
                redis_client.setex(history_key, 3600, json.dumps(history))
            
            response_data = {
                "response": general_response,
                "context": []
            }

        # Send response back via RabbitMQ
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(response_data),
        )
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        error_response = {"response": "Erreur de format de requête", "context": []}
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(error_response),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        error_response = {"response": "Une erreur s'est produite lors du traitement de votre demande", "context": []}
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(error_response),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    """Main function to start the worker"""
    try:
        # Set up the consumer
        channel.basic_consume(queue="query_queue", on_message_callback=process_query)
        
        logger.info("🚀 RAG Worker is waiting for messages in query_queue. To exit, press CTRL+C")
        print("🚀 RAG Worker is waiting for messages in query_queue. To exit, press CTRL+C")
        
        # Start consuming messages
        channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        print("\n👋 Worker stopped by user")
        channel.stop_consuming()
        connection.close()
    except Exception as e:
        logger.error(f"Error in main worker loop: {e}")
        print(f"❌ Error in main worker loop: {e}")
    finally:
        if connection.is_open:
            connection.close()
            logger.info("RabbitMQ connection closed")

if __name__ == "__main__":
    main()