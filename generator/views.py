import json
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from .services import (
    CATEGORIES,
    TONES,
    CREATIVITY_LEVELS,
    generate_excuse,
    improve_excuse,
)


def excuse_generator_view(request: HttpRequest) -> HttpResponse:
    """Handle excuse generator page display and excuse generation/improvement requests."""
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
        or request.content_type == 'application/json'
    )

    # Defaults
    initial_context = {
        'categories': CATEGORIES,
        'tones': TONES,
        'creativity_levels': list(CREATIVITY_LEVELS.keys()),
        'situation': '',
        'selected_category': 'Work',
        'selected_tone': 'Professional',
        'selected_creativity': 'Normal',
        'excuse': '',
        'error': '',
    }

    if request.method == 'GET':
        return render(request, 'index.html', initial_context)

    if request.method == 'POST':
        action = 'generate'
        situation = ''
        category = 'Work'
        tone = 'Professional'
        creativity = 'Normal'
        previous_excuse = ''
        if len(request.body) > 50000:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Request payload is too large.'}, status=400)
            return render(request, 'index.html', {**initial_context, 'error': 'Request payload is too large.'})

        if request.content_type == 'application/json':
            try:
                body = json.loads(request.body.decode('utf-8'))
                action = body.get('action', 'generate')
                situation = body.get('situation', '')
                category = body.get('category', 'Work')
                tone = body.get('tone', 'Professional')
                creativity = body.get('creativity', 'Normal')
                previous_excuse = body.get('previous_excuse', '')
                target_excuse = body.get('excuse', '')
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'success': False, 'error': 'Invalid JSON data received.'}, status=400)
        else:
            action = request.POST.get('action', 'generate')
            situation = request.POST.get('situation', '')
            category = request.POST.get('category', 'Work')
            tone = request.POST.get('tone', 'Professional')
            creativity = request.POST.get('creativity', 'Normal')
            previous_excuse = request.POST.get('previous_excuse', '')
            target_excuse = request.POST.get('excuse', '')

        # Dispatch based on action
        if action == 'improve':
            success, result_message = improve_excuse(
                original_excuse=target_excuse,
                tone=tone,
                category=category,
            )
        else:
            success, result_message = generate_excuse(
                situation=situation,
                category=category,
                tone=tone,
                creativity=creativity,
                previous_excuse=previous_excuse,
            )

        if is_ajax:
            return JsonResponse({
                'success': success,
                'excuse': result_message if success else '',
                'error': '' if success else result_message,
                'situation': situation,
                'category': category,
                'tone': tone,
                'creativity': creativity,
                'action': action,
            })

        # Regular HTML form POST fallback
        context = {
            'categories': CATEGORIES,
            'tones': TONES,
            'creativity_levels': list(CREATIVITY_LEVELS.keys()),
            'situation': situation,
            'selected_category': category,
            'selected_tone': tone,
            'selected_creativity': creativity,
            'excuse': result_message if success else '',
            'error': '' if success else result_message,
        }
        return render(request, 'index.html', context)

    return HttpResponse(status=405)
