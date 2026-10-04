import base64
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.overtime.tests.helpers import PASSWORD, build_referential

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class AgentPhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def test_detail_shows_identity_without_photo_actions(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("agents:detail", args=[self.world["agent"].pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fiche agent")
        self.assertContains(response, self.world["agent"].nom_complet)
        self.assertContains(response, "Hiérarchie du service")
        self.assertContains(response, "Secrétariat général")
        self.assertNotContains(response, "Enregistrer la photo")

    def test_chef_sees_the_sheet_without_the_upload_form(self):
        self.client.login(username="chef", password=PASSWORD)
        response = self.client.get(reverse("agents:detail", args=[self.world["agent"].pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Enregistrer la photo")

    def test_photo_is_private_and_scoped(self):
        self.client.login(username="rh", password=PASSWORD)
        upload = SimpleUploadedFile("portrait.png", PNG, content_type="image/png")
        response = self.client.post(
            reverse("agents:photo_update", args=[self.world["agent"].pk]),
            {"photo": upload},
        )
        self.assertRedirects(response, reverse("agents:detail", args=[self.world["agent"].pk]))
        self.world["agent"].refresh_from_db()
        self.assertTrue(self.world["agent"].photo.name)

        photo_url = reverse("agents:photo", args=[self.world["agent"].pk])
        served = self.client.get(photo_url)
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/png")
        self.assertEqual(served["X-Content-Type-Options"], "nosniff")

        self.client.login(username="chef", password=PASSWORD)
        self.assertEqual(self.client.get(photo_url).status_code, 200)
        hidden = reverse("agents:photo", args=[self.world["other"].pk])
        self.assertEqual(self.client.get(hidden).status_code, 404)

        self.client.logout()
        self.assertRedirects(self.client.get(photo_url), f"{reverse('login')}?next={photo_url}")

    def test_invalid_file_is_refused(self):
        self.client.login(username="rh", password=PASSWORD)
        upload = SimpleUploadedFile("note.txt", b"pas une image", content_type="text/plain")
        response = self.client.post(
            reverse("agents:photo_update", args=[self.world["agent"].pk]),
            {"photo": upload},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.world["agent"].refresh_from_db()
        self.assertFalse(self.world["agent"].photo)
