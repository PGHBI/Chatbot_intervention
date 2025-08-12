import logging
from chromadb import PersistentClient
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import uuid
from datetime import datetime
from django.conf import settings
import os

logger = logging.getLogger(__name__)

class ChromaDBManager:
    """Manager class for ChromaDB operations"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.model = None
        self.initialize_chromadb()
    
    def initialize_chromadb(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Initialize ChromaDB client
            chroma_path = getattr(settings, 'CHROMADB_PATH', '../chroma_data')
            self.client = PersistentClient(
                path="../chroma_data",
                settings=Settings(anonymized_telemetry=False),
            )
            
            # Get or create the collection
            try:
                self.collection = self.client.get_collection("pdf_knowledge_base")
                logger.info("Connected to existing ChromaDB collection")
            except Exception:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name="pdf_knowledge_base",
                    metadata={"description": "Knowledge base for maintenance interventions"}
                )
                logger.info("Created new ChromaDB collection")
            
            # Initialize the embedding model
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("ChromaDB Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None
            self.model = None
    
    def is_available(self):
        """Check if ChromaDB is available"""
        return all([self.client, self.collection, self.model])
    
    def embed_intervention(self, intervention):
        """
        Embed a new intervention into ChromaDB
        
        Args:
            intervention: InterventionRequest instance
        """
        if not self.is_available():
            logger.error("ChromaDB not available for embedding")
            return False
        
        try:
            # Create comprehensive text representation of the intervention
            intervention_text = self._create_intervention_text(intervention)
            
            # Generate embedding
            embedding = self.model.encode(intervention_text).tolist()
            
            # Create metadata
            metadata = {
                "source": f"Intervention_{intervention.reference}",
                "type": "intervention",
                "reference": intervention.reference,
                "criticite": intervention.criticite,
                "machine": intervention.machine,
                "filiale": intervention.filiale,
                "contact": intervention.contact,
                "date_intervention": intervention.date_intervention.isoformat(),
                "date_creation": intervention.date_creation.isoformat(),
                "year": intervention.date_intervention.year,
                "month": intervention.date_intervention.month,
                "has_recommendations": bool(intervention.recommandations),
            }
            
            # Generate unique ID for this intervention
            doc_id = f"intervention_{intervention.reference}_{intervention.pk}"
            
            # Add to ChromaDB
            self.collection.add(
                embeddings=[embedding],
                documents=[intervention_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Successfully embedded intervention {intervention.reference} into ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to embed intervention {intervention.reference}: {e}")
            return False
    
    def update_intervention(self, intervention):
        """
        Update an existing intervention in ChromaDB
        
        Args:
            intervention: InterventionRequest instance
        """
        if not self.is_available():
            logger.error("ChromaDB not available for updating")
            return False
        
        try:
            doc_id = f"intervention_{intervention.reference}_{intervention.pk}"
            
            # Check if document exists
            try:
                existing = self.collection.get(ids=[doc_id])
                if not existing['ids']:
                    # Document doesn't exist, create it
                    return self.embed_intervention(intervention)
            except Exception:
                # Document doesn't exist, create it
                return self.embed_intervention(intervention)
            
            # Update existing document
            intervention_text = self._create_intervention_text(intervention)
            embedding = self.model.encode(intervention_text).tolist()
            
            metadata = {
                "source": f"Intervention_{intervention.reference}",
                "type": "intervention",
                "reference": intervention.reference,
                "criticite": intervention.criticite,
                "machine": intervention.machine,
                "filiale": intervention.filiale,
                "contact": intervention.contact,
                "date_intervention": intervention.date_intervention.isoformat(),
                "date_creation": intervention.date_creation.isoformat(),
                "date_modification": intervention.date_modification.isoformat(),
                "year": intervention.date_intervention.year,
                "month": intervention.date_intervention.month,
                "has_recommendations": bool(intervention.recommandations),
                "updated": True,
            }
            
            # Update in ChromaDB
            self.collection.update(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[intervention_text],
                metadatas=[metadata]
            )
            
            logger.info(f"Successfully updated intervention {intervention.reference} in ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update intervention {intervention.reference}: {e}")
            return False
    
    def delete_intervention(self, intervention):
        """
        Delete an intervention from ChromaDB
        
        Args:
            intervention: InterventionRequest instance
        """
        if not self.is_available():
            logger.error("ChromaDB not available for deletion")
            return False
        
        try:
            doc_id = f"intervention_{intervention.reference}_{intervention.pk}"
            
            # Delete from ChromaDB
            self.collection.delete(ids=[doc_id])
            
            logger.info(f"Successfully deleted intervention {intervention.reference} from ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete intervention {intervention.reference}: {e}")
            return False
    
    def _create_intervention_text(self, intervention):
        """
        Create a comprehensive text representation of the intervention for embedding
        
        Args:
            intervention: InterventionRequest instance
            
        Returns:
            str: Formatted text representation
        """
        # Create structured text that includes all relevant information
        text_parts = [
            f"INTERVENTION {intervention.reference}",
            f"Objet: {intervention.objet}",
            f"Description: {intervention.description}",
            f"Machine: {intervention.machine}",
            f"Filiale: {intervention.filiale}",
            f"Criticité: {intervention.get_criticite_display()}",
            f"Contact: {intervention.contact}",
            f"Téléphone: {intervention.numero_telephone}",
            f"Intervenants: {intervention.intervenants}",
            f"Responsables: {intervention.responsables}",
            f"Diffusé par: {intervention.diffuseur}",
            f"Date d'intervention: {intervention.date_intervention.strftime('%d/%m/%Y %H:%M')}",
        ]
        
        # Add recommendations if available
        if intervention.recommandations:
            text_parts.append(f"Recommandations: {intervention.recommandations}")
        
        # Add document information if available
        documents = intervention.documents.all()
        if documents.exists():
            doc_names = [doc.nom_fichier for doc in documents]
            text_parts.append(f"Documents joints: {', '.join(doc_names)}")
        
        return "\n".join(text_parts)
    
    def search_similar_interventions(self, query, n_results=5):
        """
        Search for similar interventions based on a query
        
        Args:
            query (str): Search query
            n_results (int): Number of results to return
            
        Returns:
            dict: Search results
        """
        if not self.is_available():
            logger.error("ChromaDB not available for search")
            return {"documents": [], "metadatas": [], "distances": []}
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode(query).tolist()
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
                where={"type": "intervention"}  # Only search interventions
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search interventions: {e}")
            return {"documents": [], "metadatas": [], "distances": []}
    
    def get_collection_stats(self):
        """Get statistics about the ChromaDB collection"""
        if not self.is_available():
            return {"total": 0, "interventions": 0, "error": "ChromaDB not available"}
        
        try:
            # Get total count
            total_count = self.collection.count()
            
            # Get intervention count
            intervention_results = self.collection.get(
                where={"type": "intervention"},
                include=["metadatas"]
            )
            intervention_count = len(intervention_results['ids']) if intervention_results['ids'] else 0
            
            return {
                "total": total_count,
                "interventions": intervention_count,
                "available": True
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"total": 0, "interventions": 0, "error": str(e)}

# Global instance
chromadb_manager = ChromaDBManager()