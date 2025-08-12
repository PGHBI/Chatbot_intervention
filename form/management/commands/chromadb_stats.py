from django.core.management.base import BaseCommand
from form.chromadb_manager import chromadb_manager
from form.models import InterventionRequest

class Command(BaseCommand):
    help = 'Show ChromaDB collection statistics'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('ChromaDB Collection Statistics')
        )
        self.stdout.write('='*50)
        
        if not chromadb_manager.is_available():
            self.stdout.write(
                self.style.ERROR('ChromaDB is not available. Please check your configuration.')
            )
            return
        
        # Get ChromaDB stats
        stats = chromadb_manager.get_collection_stats()
        
        if stats.get('available'):
            self.stdout.write(f'Total documents in collection: {stats["total"]}')
            self.stdout.write(f'Intervention documents: {stats["interventions"]}')
            
            # Get Django model stats
            django_count = InterventionRequest.objects.count()
            self.stdout.write(f'Interventions in Django: {django_count}')
            
            # Calculate sync status
            embedded_count = stats["interventions"]
            if embedded_count == django_count:
                self.stdout.write(
                    self.style.SUCCESS('✓ All interventions are embedded in ChromaDB')
                )
            elif embedded_count < django_count:
                missing = django_count - embedded_count
                self.stdout.write(
                    self.style.WARNING(f'⚠ {missing} interventions are missing from ChromaDB')
                )
                self.stdout.write('Run: python manage.py embed_existing_interventions')
            else:
                extra = embedded_count - django_count
                self.stdout.write(
                    self.style.WARNING(f'⚠ {extra} extra intervention documents in ChromaDB')
                )
            
            # Show criticality breakdown
            self.stdout.write('\nCriticality breakdown in Django:')
            for criticite, label in InterventionRequest.CRITICITE_CHOICES:
                count = InterventionRequest.objects.filter(criticite=criticite).count()
                self.stdout.write(f'  {label}: {count}')
                
        else:
            error = stats.get('error', 'Unknown error')
            self.stdout.write(
                self.style.ERROR(f'Error getting stats: {error}')
            )