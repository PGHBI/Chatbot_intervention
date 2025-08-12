from django.core.management.base import BaseCommand
from form.models import InterventionRequest
from form.chromadb_manager import chromadb_manager
from django.utils import timezone

class Command(BaseCommand):
    help = 'Embed all existing interventions into ChromaDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of interventions to process in each batch'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-embedding of all interventions'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS('Starting to embed existing interventions into ChromaDB...')
        )
        
        if not chromadb_manager.is_available():
            self.stdout.write(
                self.style.ERROR('ChromaDB is not available. Please check your configuration.')
            )
            return
        
        # Get all interventions
        interventions = InterventionRequest.objects.all().order_by('date_creation')
        total_count = interventions.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.WARNING('No interventions found to embed.')
            )
            return
        
        self.stdout.write(f'Found {total_count} interventions to process...')
        
        success_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = interventions[i:i + batch_size]
            
            self.stdout.write(f'Processing batch {i//batch_size + 1} ({len(batch)} interventions)...')
            
            for intervention in batch:
                try:
                    if force:
                        # Force update (will create if doesn't exist)
                        success = chromadb_manager.update_intervention(intervention)
                    else:
                        # Try to embed (will skip if already exists)
                        success = chromadb_manager.embed_intervention(intervention)
                    
                    if success:
                        success_count += 1
                        self.stdout.write(f'  ✓ {intervention.reference}')
                    else:
                        error_count += 1
                        self.stdout.write(f'  ✗ {intervention.reference} (failed)')
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(f'  ✗ {intervention.reference} (error: {e})')
            
            # Show progress
            processed = min(i + batch_size, total_count)
            self.stdout.write(f'Progress: {processed}/{total_count} interventions processed')
        
        # Final summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'Embedding completed!')
        )
        self.stdout.write(f'Successfully embedded: {success_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total processed: {success_count + error_count}')
        
        # Show collection stats
        stats = chromadb_manager.get_collection_stats()
        if stats.get('available'):
            self.stdout.write(f'\nChromaDB Collection Stats:')
            self.stdout.write(f'  Total documents: {stats["total"]}')
            self.stdout.write(f'  Interventions: {stats["interventions"]}')
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'\n{error_count} interventions failed to embed. Check logs for details.')
            )