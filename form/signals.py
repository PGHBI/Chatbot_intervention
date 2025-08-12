from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import InterventionRequest, Machine, Filiale
from .chromadb_manager import chromadb_manager
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=InterventionRequest)
def intervention_saved(sender, instance, created, **kwargs):
    """
    Signal handler for when an intervention is saved (created or updated)
    """
    try:
        # Update counters for Machine and Filiale
        if created:
            # Increment counters for new interventions
            if instance.machine_obj:
                Machine.objects.filter(pk=instance.machine_obj.pk).update(
                    counter=models.F('counter') + 1
                )
                logger.info(f"Incremented counter for machine: {instance.machine_obj.name}")
            
            if instance.filiale_obj:
                Filiale.objects.filter(pk=instance.filiale_obj.pk).update(
                    counter=models.F('counter') + 1
                )
                logger.info(f"Incremented counter for filiale: {instance.filiale_obj.name}")
        
        # Handle ChromaDB embedding
        if created:
            # New intervention created
            success = chromadb_manager.embed_intervention(instance)
            if success:
                logger.info(f"New intervention {instance.reference} embedded in ChromaDB")
            else:
                logger.warning(f"Failed to embed new intervention {instance.reference}")
        else:
            # Existing intervention updated
            success = chromadb_manager.update_intervention(instance)
            if success:
                logger.info(f"Intervention {instance.reference} updated in ChromaDB")
            else:
                logger.warning(f"Failed to update intervention {instance.reference} in ChromaDB")
                
    except Exception as e:
        logger.error(f"Error in intervention_saved signal: {e}")

@receiver(post_delete, sender=InterventionRequest)
def intervention_deleted(sender, instance, **kwargs):
    """
    Signal handler for when an intervention is deleted
    """
    try:
        # Decrement counters for Machine and Filiale
        if instance.machine_obj:
            Machine.objects.filter(pk=instance.machine_obj.pk).update(
                counter=models.F('counter') - 1
            )
            logger.info(f"Decremented counter for machine: {instance.machine_obj.name}")
        
        if instance.filiale_obj:
            Filiale.objects.filter(pk=instance.filiale_obj.pk).update(
                counter=models.F('counter') - 1
            )
            logger.info(f"Decremented counter for filiale: {instance.filiale_obj.name}")
        
        # Handle ChromaDB deletion
        success = chromadb_manager.delete_intervention(instance)
        if success:
            logger.info(f"Intervention {instance.reference} deleted from ChromaDB")
        else:
            logger.warning(f"Failed to delete intervention {instance.reference} from ChromaDB")
            
    except Exception as e:
        logger.error(f"Error in intervention_deleted signal: {e}")

# Import models to avoid circular import
from django.db import models