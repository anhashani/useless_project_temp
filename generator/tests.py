import json
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, Client
from django.urls import reverse
from generator.services import generate_excuse, CATEGORIES, TONES, CREATIVITY_LEVELS


class ExcuseGenTestCase(SimpleTestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('home')

    def test_get_homepage_renders_form(self):
        """Homepage should load successfully with all required form elements."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ExcuseGen')
        self.assertContains(response, 'situation')
        for category in CATEGORIES:
            self.assertContains(response, category)
        for tone in TONES:
            self.assertContains(response, tone)
        for level in CREATIVITY_LEVELS.keys():
            self.assertContains(response, level)

    def test_post_empty_situation_fails_validation(self):
        """Submitting an empty situation should return a validation error."""
        response = self.client.post(self.url, {
            'situation': '   ',
            'category': 'Work',
            'tone': 'Professional',
            'creativity': 'Normal',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please provide a situation')

    def test_post_invalid_category_fails_validation(self):
        """Submitting an unknown category should return an error."""
        response = self.client.post(self.url, {
            'situation': 'I missed the meeting',
            'category': 'UnknownCategory',
            'tone': 'Professional',
            'creativity': 'Normal',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid category')

    def test_post_invalid_tone_fails_validation(self):
        """Submitting an unknown tone should return an error."""
        response = self.client.post(self.url, {
            'situation': 'I missed the meeting',
            'category': 'Work',
            'tone': 'Rude',
            'creativity': 'Normal',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid tone')

    def test_post_invalid_creativity_fails_validation(self):
        """Submitting an unknown creativity level should return an error."""
        response = self.client.post(self.url, {
            'situation': 'I missed the meeting',
            'category': 'Work',
            'tone': 'Professional',
            'creativity': 'Extreme',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid creativity')

    def test_ajax_post_without_api_key_generates_fallback_excuse(self):
        """AJAX request without an API key configured gracefully generates a fallback excuse."""
        with patch('generator.services.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = ''
            response = self.client.post(
                self.url,
                json.dumps({
                    'situation': 'Stuck in traffic',
                    'category': 'Being Late',
                    'tone': 'Casual',
                    'creativity': 'Safe',
                }),
                content_type='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            self.assertTrue(len(data['excuse']) > 0)
            self.assertIn('stuck in traffic', data['excuse'].lower())

    @patch('openai.OpenAI')
    def test_successful_excuse_generation_via_responses_api(self, mock_openai_cls):
        """Mock OpenAI Responses API and verify output extraction."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "I ran into unforeseen delays on my route, but I am heading in now."
        mock_client.responses.create.return_value = mock_response

        with patch('generator.services.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'sk-mockkey'
            mock_settings.OPENAI_MODEL = 'gpt-4o-mini'

            success, excuse = generate_excuse(
                situation="Traffic jam on highway",
                category="Being Late",
                tone="Professional",
                creativity="Normal"
            )

            self.assertTrue(success)
            self.assertEqual(excuse, "I ran into unforeseen delays on my route, but I am heading in now.")
            # Verify Responses API was called
            mock_client.responses.create.assert_called_once()
            call_kwargs = mock_client.responses.create.call_args[1]
            self.assertEqual(call_kwargs['model'], 'gpt-4o-mini')
            self.assertIn('Being Late', call_kwargs['instructions'])
            self.assertIn('Professional', call_kwargs['instructions'])
            self.assertIn('Traffic jam on highway', call_kwargs['input'])

    @patch('openai.OpenAI')
    def test_openai_api_failure_handled_gracefully(self, mock_openai_cls):
        """API failures should be handled without raising unhandled exceptions or exposing keys."""
        from openai import APIConnectionError
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.responses.create.side_effect = APIConnectionError(request=MagicMock())

        with patch('generator.services.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'sk-secret-key-that-must-never-leak'
            mock_settings.OPENAI_MODEL = 'gpt-4o-mini'

            success, message = generate_excuse(
                situation="Missed dinner",
                category="Family",
                tone="Friendly",
                creativity="Safe"
            )

            self.assertFalse(success)
            self.assertIn("Unable to reach OpenAI servers", message)
            self.assertNotIn("sk-secret-key", message)

    def test_post_excessively_long_situation_fails_validation(self):
        """Situations over 500 characters should be rejected safely."""
        long_situation = "A" * 501
        success, message = generate_excuse(
            situation=long_situation,
            category="Work",
            tone="Professional",
            creativity="Normal"
        )
        self.assertFalse(success)
        self.assertIn("under 500 characters", message)

    @patch('openai.OpenAI')
    def test_generate_again_with_previous_excuse(self, mock_openai_cls):
        """Regenerating should include instructions about previous excuse to ensure freshness."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "I encountered an unexpected vehicle malfunction and am en route now."
        mock_client.responses.create.return_value = mock_response

        with patch('generator.services.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'sk-mockkey'
            mock_settings.OPENAI_MODEL = 'gpt-4o-mini'

            success, excuse = generate_excuse(
                situation="Tire puncture",
                category="Being Late",
                tone="Professional",
                creativity="Normal",
                previous_excuse="My tire went flat earlier."
            )

            self.assertTrue(success)
            call_kwargs = mock_client.responses.create.call_args[1]
            self.assertIn("My tire went flat earlier.", call_kwargs['input'])
            self.assertIn("distinctly different", call_kwargs['input'])

    @patch('openai.OpenAI')
    def test_improve_excuse_via_responses_api(self, mock_openai_cls):
        """Make Better should refine existing excuse using the Responses API."""
        from generator.services import improve_excuse
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "I apologize for the delay; unforeseen transit issues held me up, but I am arriving shortly."
        mock_client.responses.create.return_value = mock_response

        with patch('generator.services.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'sk-mockkey'
            mock_settings.OPENAI_MODEL = 'gpt-4o-mini'

            success, improved = improve_excuse(
                original_excuse="I am late because bus broke.",
                tone="Professional",
                category="Work"
            )

            self.assertTrue(success)
            self.assertEqual(improved, "I apologize for the delay; unforeseen transit issues held me up, but I am arriving shortly.")
            call_kwargs = mock_client.responses.create.call_args[1]
            self.assertIn("I am late because bus broke.", call_kwargs['input'])
            self.assertIn("Professional", call_kwargs['instructions'])

    def test_improve_excuse_without_text_fails(self):
        """Improving an empty excuse should return an informative error."""
        from generator.services import improve_excuse
        success, message = improve_excuse("")
        self.assertFalse(success)
        self.assertIn("No existing excuse provided", message)

    def test_csrf_protection_enforced(self):
        """POST requests without a valid CSRF token should be rejected with 403 Forbidden."""
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(self.url, {'situation': 'Running late'})
        self.assertEqual(response.status_code, 403)

    def test_oversized_payload_rejected(self):
        """Excessively large request bodies should be rejected with 400 Bad Request."""
        large_body = 'x' * 55000
        response = self.client.post(
            self.url,
            data=large_body,
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", response.json()['error'])

    def test_invalid_json_payload_handled(self):
        """Malformed JSON payload should return a clean 400 error."""
        response = self.client.post(
            self.url,
            data="not-valid-json{",
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid JSON", response.json()['error'])
