from django.core.management.base import BaseCommand
from django.conf import settings
import os
import glob
from form import pdf_extractor
from form.models import InterventionRequest

class Command(BaseCommand):
    help = 'Extract information from PDF files and create interventions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pdf-path',
            type=str,
            help='Path to a specific PDF file'
        )
        parser.add_argument(
            '--pdf-directory',
            type=str,
            help='Directory containing PDF files to process'
        )
        parser.add_argument(
            '--pattern',
            type=str,
            default='*.pdf',
            help='File pattern to match (default: *.pdf)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Extract information but don\'t create interventions'
        )

    def handle(self, *args, **options):
        pdf_path = options.get('pdf_path')
        pdf_directory = options.get('pdf_directory')
        pattern = options.get('pattern')
        dry_run = options.get('dry_run')

        if not pdf_path and not pdf_directory:
            self.stdout.write(
                self.style.ERROR('Please provide either --pdf-path or --pdf-directory')
            )
            return

        pdf_files = []
        
        if pdf_path:
            if os.path.exists(pdf_path):
                pdf_files = [pdf_path]
            else:
                self.stdout.write(
                    self.style.ERROR(f'PDF file not found: {pdf_path}')
                )
                return
        
        if pdf_directory:
            if os.path.exists(pdf_directory):
                search_pattern = os.path.join(pdf_directory, pattern)
                pdf_files.extend(glob.glob(search_pattern))
            else:
                self.stdout.write(
                    self.style.ERROR(f'Directory not found: {pdf_directory}')
                )
                return

        if not pdf_files:
            self.stdout.write(
                self.style.WARNING('No PDF files found')
            )
            return

        self.stdout.write(f'Found {len(pdf_files)} PDF file(s) to process')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No interventions will be created')
            )

        success_count = 0
        error_count = 0

        for pdf_file in pdf_files:
            self.stdout.write(f'\nProcessing: {pdf_file}')
            
            try:
                if dry_run:
                    # Extract information but don't create intervention
                    text = pdf_extractor.extract_text_from_pdf(pdf_file)
                    if text:
                        extracted_data = pdf_extractor.extract_information_with_ai(text)
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Extracted {len(extracted_data)} fields')
                        )
                        
                        # Show extracted data
                        for field, value in extracted_data.items():
                            self.stdout.write(f'  {field}: {value}')
                    else:
                        self.stdout.write(
                            self.style.ERROR('✗ Could not extract text')
                        )
                        error_count += 1
                        continue
                else:
                    # Create intervention
                    intervention, extracted_data = pdf_extractor.create_intervention_from_pdf(pdf_file)
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created intervention: {intervention.reference}')
                    )
                    self.stdout.write(f'  Machine: {intervention.machine}')
                    self.stdout.write(f'  Filiale: {intervention.filiale}')
                    self.stdout.write(f'  Extracted fields: {len(extracted_data)}')
                
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing {pdf_file}: {e}')
                )
                error_count += 1

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'Processing complete!')
        )
        self.stdout.write(f'Successfully processed: {success_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total files: {len(pdf_files)}')
        
        if not dry_run and success_count > 0:
            total_interventions = InterventionRequest.objects.count()
            self.stdout.write(f'Total interventions in database: {total_interventions}')