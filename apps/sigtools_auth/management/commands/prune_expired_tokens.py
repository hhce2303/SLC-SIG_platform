from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.sigtools_auth.models import PersonalAccessToken


class Command(BaseCommand):
    help = "Elimina tokens expirados de personal_access_tokens en sigtools_beta."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cuántos tokens se eliminarían sin borrarlos.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        expired_qs = PersonalAccessToken.objects.using("sigtools").filter(
            expires_at__lt=now,
        )

        count = expired_qs.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"[dry-run] {count} token(s) expirados encontrados. No se eliminaron.")
            )
            return

        deleted, _ = expired_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Eliminados {deleted} token(s) expirados.")
        )
