import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class RAGClient:
    """Client to communicate with the Flask RAG API"""
    
    def __init__(self, base_url="http://localhost:5001"):
        self.base_url = base_url
        self.submit_query_endpoint = f"{base_url}/submit_query"
    
    def get_response(self, user_message, user_id="default_user"):
        """
        Send a query to the RAG system and get a response
        
        Args:
            user_message (str): The user's message/query
            user_id (str): Unique identifier for the user (for conversation history)
            
        Returns:
            dict: Response from the RAG system
        """
        try:
            payload = {
                "query": user_message,
                "user_id": user_id
            }
            
            response = requests.post(
                self.submit_query_endpoint,
                json=payload,
                timeout=30  # 30 seconds timeout
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 504:
                return {
                    "response": "Désolé, le système met plus de temps que prévu à répondre. Veuillez réessayer.",
                    "context": []
                }
            else:
                logger.error(f"RAG API returned status code: {response.status_code}")
                return {
                    "response": "Une erreur s'est produite lors du traitement de votre demande.",
                    "context": []
                }
                
        except requests.exceptions.Timeout:
            logger.error("RAG API request timed out")
            return {
                "response": "Le système met trop de temps à répondre. Veuillez réessayer plus tard.",
                "context": []
            }
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to RAG API")
            return {
                "response": "Le service de chat n'est pas disponible actuellement. Veuillez réessayer plus tard.",
                "context": []
            }
        except Exception as e:
            logger.error(f"Unexpected error in RAG client: {str(e)}")
            return {
                "response": "Une erreur inattendue s'est produite. Veuillez réessayer.",
                "context": []
            }
    
    def is_available(self):
        """
        Check if the RAG service is available
        
        Returns:
            bool: True if service is available, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False