# qr_app/management/commands/seed_demo.py
import secrets
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw

from qr_app.models import Company, Equipment, Membership, Role, User

DEMO_INSTITUTION = 'DEMO Hostel (demonstration data)'


def demo_png(label, colour):
    img = Image.new('RGB', (960, 640), colour)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 940, 620], outline='white', width=6)
    for i, line in enumerate(['DEMONSTRATION PHOTO', label, 'Not a real tank']):
        d.text((60, 220 + i * 60), line, fill='white', font_size=44)
    buf = BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def sample_pdf():
    """A minimal one-page PDF that states plainly it is not a real laboratory result."""
    lines = ['SAMPLE REPORT - NOT A REAL LABORATORY RESULT',
             'For DHARA demonstrations only. No sample was tested.',
             'Laboratory: Example Lab (fictional)']
    text = 'BT /F1 14 Tf 50 760 Td 18 TL ' + ' '.join(f'({l}) Tj T*' for l in lines) + ' ET'
    objs = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        f'<< /Length {len(text)} >>\nstream\n{text}\nendstream',
        '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    out, offsets = b'%PDF-1.4\n', []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f'{i} 0 obj\n{body}\nendobj\n'.encode()
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
    out += ''.join(f'{o:010d} 00000 n \n' for o in offsets).encode()
    out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return out


class Command(BaseCommand):
    help = 'Create a clearly labelled demo institution, two users and two tanks, plus demo upload files.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Password for both demo users (default: random, printed).')
        parser.add_argument('--files-dir', default='demo_files', help='Where to write demo photos and the sample PDF.')

    @transaction.atomic
    def handle(self, *args, **opts):
        password = opts['password'] or secrets.token_urlsafe(9)
        company, _ = Company.objects.get_or_create(name=DEMO_INSTITUTION)
        users = {}
        for email, role in (('warden@demo.dhara.test', Role.ADMIN), ('technician@demo.dhara.test', Role.TECHNICIAN)):
            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            user.set_password(password)
            user.save()
            Membership.objects.update_or_create(user=user, company=company, defaults={'role': role})
            users[role] = user
        for code, name, building, interval, report in (
                ('TANK-A', 'Tank A · overhead tank', 'Block A', 180, 180),
                ('TANK-B', 'Tank B · underground sump', 'Block B', 90, None)):
            Equipment.objects.get_or_create(company=company, tank_code=code, defaults=dict(
                name=name, building=building, maintenance_interval_days=interval, report_interval_days=report,
                responsible=users[Role.TECHNICIAN], location='Demo location (fictional)'))

        out = Path(opts['files_dir'])
        out.mkdir(parents=True, exist_ok=True)
        (out / 'DEMO-before.png').write_bytes(demo_png('BEFORE cleaning', '#6b4f2a'))
        (out / 'DEMO-after.png').write_bytes(demo_png('AFTER cleaning', '#1b5f8a'))
        (out / 'SAMPLE-lab-report-NOT-REAL.pdf').write_bytes(sample_pdf())

        self.stdout.write(self.style.SUCCESS(f'Demo institution: {company.name}  (/{company.slug}/dashboard/)'))
        self.stdout.write(f'  warden@demo.dhara.test      (Warden / Administrator)\n'
                          f'  technician@demo.dhara.test  (Technician)\n  password: {password}')
        self.stdout.write(f'Demo upload files written to {out.resolve()}')
