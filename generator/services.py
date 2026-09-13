import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

# Valid choices per specification
CATEGORIES = [
    'College',
    'Work',
    'Friends',
    'Family',
    'Event',
    'Being Late',
]

TONES = [
    'Formal',
    'Casual',
    'Friendly',
    'Funny',
    'Professional',
]

CREATIVITY_LEVELS = {
    'Safe': {
        'temperature': 0.4,
        'description': 'Plausible, low-risk, polite, everyday reasons (e.g. minor transit delay, subtle scheduling conflict).',
    },
    'Normal': {
        'temperature': 0.7,
        'description': 'Balanced, realistic, standard everyday explanation.',
    },
    'Creative': {
        'temperature': 0.95,
        'description': 'Inventive, witty, imaginative twist while remaining relatable and grounded.',
    },
    'Dramatic': {
        'temperature': 1.15,
        'description': 'High-energy, expressive, urgently articulated everyday chaos (e.g. domestic mishap, rogue pet) without severe harm.',
    },
}


def build_system_instructions(category: str, tone: str, creativity: str) -> str:
    """Build clear system instructions for the OpenAI Responses API."""
    return (
        "You are ExcuseGen, an AI assistant specialized in generating realistic, natural, and believable explanations or excuses for everyday situations.\n\n"
        "STRICT GUIDELINES:\n"
        "1. Length: Normally 1 to 3 sentences. Short, natural, and directly usable as a message/text/email.\n"
        "2. Format: Return ONLY the raw explanation message text. Do NOT prefix with 'Here is your excuse:', do NOT wrap in title headings, do NOT add introductory pleasantries or meta commentary.\n"
        f"3. Category context: {category}.\n"
        f"4. Tone: {tone}. Ensure vocabulary and sentence structure strictly match this tone.\n"
        f"5. Creativity level: {creativity} ({CREATIVITY_LEVELS.get(creativity, {}).get('description', '')}).\n"
        "6. Safety & Ethical Boundaries (CRITICAL):\n"
        "   - NEVER fabricate serious emergencies, deaths, hospitalizations, severe medical conditions, crimes, violence, accidents, or dangerous situations.\n"
        "   - Prefer harmless explanations, everyday inconveniences, subtle technical/logistical glitches, or accountable apologies where appropriate.\n"
        "7. Relevance: The excuse must directly address and explain the user's specific situation."
    )


def generate_excuse(situation: str, category: str, tone: str, creativity: str, previous_excuse: str = '') -> tuple[bool, str]:
    """
    Call the official OpenAI Responses API to generate an excuse.
    
    Returns:
        tuple[bool, str]: (success, excuse_text_or_error_message)
    """
    # 1. Validate inputs
    situation_clean = (situation or '').strip()
    if not situation_clean:
        return False, "Please provide a situation for your excuse."

    if len(situation_clean) > 500:
        return False, "The situation description is too long. Please keep it under 500 characters."

    if category not in CATEGORIES:
        return False, f"Invalid category selected. Please choose from: {', '.join(CATEGORIES)}."

    if tone not in TONES:
        return False, f"Invalid tone selected. Please choose from: {', '.join(TONES)}."

    if creativity not in CREATIVITY_LEVELS:
        return False, f"Invalid creativity level selected. Please choose from: {', '.join(CREATIVITY_LEVELS.keys())}."

    # 2. Check API Key
    api_key = getattr(settings, 'OPENAI_API_KEY', '').strip() or os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        # Provide smart fallback excuse tailored to situation, category, tone, and creativity
        return True, generate_fallback_excuse(situation_clean, category, tone, creativity, previous_excuse)

    # 3. Call OpenAI Responses API
    try:
        from openai import OpenAI, OpenAIError, AuthenticationError, APIConnectionError, RateLimitError
    except ImportError:
        logger.error("OpenAI Python SDK is not installed.")
        return False, "OpenAI SDK is not available. Please verify installation."

    model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini') or 'gpt-4o-mini'
    creativity_config = CREATIVITY_LEVELS.get(creativity, {'temperature': 0.7})
    temperature = creativity_config['temperature']

    instructions = build_system_instructions(category, tone, creativity)
    user_prompt = (
        f"Situation: {situation_clean}\n"
        f"Category: {category}\n"
        f"Tone: {tone}\n"
        f"Creativity: {creativity}\n"
    )
    if previous_excuse and previous_excuse.strip():
        user_prompt += (
            f"Previous explanation: '{previous_excuse.strip()}'.\n"
            "Generate a distinctly different, fresh explanation with an alternative angle and wording.\n"
        )
    user_prompt += "Generate the explanation now:"

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            instructions=instructions,
            input=user_prompt,
            temperature=temperature,
        )

        excuse = ""
        if hasattr(response, 'output_text') and response.output_text:
            excuse = response.output_text.strip()
        elif hasattr(response, 'output') and response.output:
            chunks = []
            for item in response.output:
                if hasattr(item, 'content') and item.content:
                    chunks.append(str(item.content))
                elif hasattr(item, 'text') and item.text:
                    chunks.append(str(item.text))
            excuse = " ".join(chunks).strip()

        # Clean any extraneous outer quotes
        if (excuse.startswith('"') and excuse.endswith('"')) or (excuse.startswith("'") and excuse.endswith("'")):
            excuse = excuse[1:-1].strip()

        if not excuse:
            return False, "Received an empty response from the AI model. Please try again."

        return True, excuse

    except AuthenticationError:
        logger.warning("OpenAI authentication error occurred.")
        return False, "Invalid OpenAI API key. Please check your OPENAI_API_KEY in .env."

    except RateLimitError:
        logger.warning("OpenAI rate limit error occurred.")
        return False, "OpenAI rate limit reached or insufficient quota. Please check your API account."

    except APIConnectionError:
        logger.warning("OpenAI connection error occurred.")
        return False, "Unable to reach OpenAI servers. Please check your network connection."

    except OpenAIError as oe:
        # Never log API key or sensitive data
        logger.error("OpenAI API error occurred: %s", type(oe).__name__)
        return False, "An error occurred with the AI service. Please try again later."

    except Exception as e:
        logger.error("Unexpected error during excuse generation: %s", type(e).__name__)
        return False, "An unexpected error occurred while generating the excuse. Please try again."


def improve_excuse(original_excuse: str, tone: str = 'Professional', category: str = 'Work') -> tuple[bool, str]:
    """
    Call the OpenAI Responses API to refine and improve the naturalness of an existing excuse.
    
    Returns:
        tuple[bool, str]: (success, improved_excuse_or_error_message)
    """
    excuse_clean = (original_excuse or '').strip()
    if not excuse_clean:
        return False, "No existing excuse provided to improve."

    if len(excuse_clean) > 1000:
        return False, "The excuse text is too long to process. Please keep it under 1000 characters."

    if tone not in TONES:
        tone = 'Professional'

    if category not in CATEGORIES:
        category = 'Work'

    api_key = getattr(settings, 'OPENAI_API_KEY', '').strip() or os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        return True, fallback_improve_excuse(excuse_clean, tone, category)

    try:
        from openai import OpenAI, OpenAIError, AuthenticationError, APIConnectionError, RateLimitError
    except ImportError:
        logger.error("OpenAI Python SDK is not installed.")
        return False, "OpenAI SDK is not available. Please verify installation."

    model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini') or 'gpt-4o-mini'

    instructions = (
        "You are ExcuseGen, an AI assistant specialized in refining explanations or excuses to sound more natural, realistic, and believable.\n\n"
        "STRICT GUIDELINES:\n"
        "1. Length: 1 to 3 sentences. Natural, conversational, and directly usable as a message.\n"
        "2. Format: Return ONLY the raw improved explanation message text. Do NOT prefix with labels or quotes.\n"
        f"3. Tone: {tone}. Enhance phrasing to sound genuinely natural while strictly preserving this tone.\n"
        f"4. Category context: {category}.\n"
        "5. Safety & Ethical Boundaries (CRITICAL):\n"
        "   - NEVER fabricate serious emergencies, deaths, hospitalizations, severe medical conditions, crimes, violence, or dangerous situations.\n"
        "   - Prefer harmless, realistic, and accountable wording.\n"
        "6. Improvement goal: Smooth out awkward phrasing, improve natural flow, and make it sound like an authentic human message."
    )

    user_prompt = (
        f"Existing explanation: {excuse_clean}\n"
        f"Context: Category={category}, Tone={tone}\n"
        "Refine and improve this explanation to make it sound even more natural and believable now:"
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            instructions=instructions,
            input=user_prompt,
            temperature=0.7,
        )

        improved = ""
        if hasattr(response, 'output_text') and response.output_text:
            improved = response.output_text.strip()
        elif hasattr(response, 'output') and response.output:
            chunks = []
            for item in response.output:
                if hasattr(item, 'content') and item.content:
                    chunks.append(str(item.content))
                elif hasattr(item, 'text') and item.text:
                    chunks.append(str(item.text))
            improved = " ".join(chunks).strip()

        if (improved.startswith('"') and improved.endswith('"')) or (improved.startswith("'") and improved.endswith("'")):
            improved = improved[1:-1].strip()

        if not improved:
            return False, "Received an empty response while improving the excuse. Please try again."

        return True, improved

    except AuthenticationError:
        logger.warning("OpenAI authentication error occurred during improvement.")
        return False, "Invalid OpenAI API key. Please check your OPENAI_API_KEY in .env."

    except RateLimitError:
        logger.warning("OpenAI rate limit error occurred during improvement.")
        return False, "OpenAI rate limit reached or insufficient quota. Please check your API account."

    except APIConnectionError:
        logger.warning("OpenAI connection error occurred during improvement.")
        return False, "Unable to reach OpenAI servers. Please check your network connection."

    except OpenAIError as oe:
        logger.error("OpenAI API error occurred during improvement: %s", type(oe).__name__)
        return False, "An error occurred with the AI service. Please try again later."

    except Exception as e:
        logger.error("Unexpected error during excuse improvement: %s", type(e).__name__)
        return False, "An unexpected error occurred while improving the excuse. Please try again."


def _clean_situation_phrase(situation: str) -> str:
    """Clean up situation string for natural phrasing integration."""
    s = situation.strip().rstrip('.')
    # If starting with uppercase and not an acronym or proper noun, lowercase for mid-sentence flow
    words = s.split()
    if words and len(words[0]) > 1 and words[0][0].isupper() and words[0][1:].islower() and words[0].lower() not in ('i', "i'm", "i've", "i'll"):
        words[0] = words[0].lower()
        return " ".join(words)
    return s


def generate_fallback_excuse(situation: str, category: str, tone: str, creativity: str, previous_excuse: str = '') -> str:
    """Generate high-quality context-tailored excuses when live OpenAI API key is not configured."""
    phrase = _clean_situation_phrase(situation)

    # Candidate banks per (tone, creativity)
    pool = []

    if tone == 'Formal':
        if creativity == 'Safe':
            pool = [
                f"I am writing to formally communicate an unavoidable delay regarding {phrase}. Please accept my apologies for the inconvenience, and I shall update you immediately upon resolving this.",
                f"Due to unexpected circumstances involving {phrase}, my schedule has been temporarily disrupted. I am taking prompt measures to ensure this matter is addressed appropriately.",
                f"Please accept my sincere apologies for the delay. An unforeseen logistical setback concerning {phrase} arose, but I am proceeding with priority.",
            ]
        elif creativity == 'Creative':
            pool = [
                f"An unanticipated complication regarding {phrase} required my immediate intervention this morning. I am managing the transition carefully and will rejoin our commitments shortly.",
                f"I regret to report an unexpected logistical bottleneck concerning {phrase}. Contingency steps are in motion to minimize any further disruption.",
                f"Regrettably, circumstances surrounding {phrase} necessitated an urgent procedural adjustment. I am concluding the matter and will provide an update promptly.",
            ]
        elif creativity == 'Dramatic':
            pool = [
                f"I urgently regret to inform you that a critical, unforeseen disruption concerning {phrase} has abruptly halted my progress. I am endeavoring to resolve the impasse with utmost diligence.",
                f"A sudden and unavoidable complication regarding {phrase} demanded my complete attention. I am taking every possible step to resume our schedule as quickly as feasible.",
                f"Please accept my deepest apologies for the sudden disruption caused by {phrase}. I am actively navigating the situation to resume operations without delay.",
            ]
        else: # Normal
            pool = [
                f"Please accept my sincere apologies. An unexpected development involving {phrase} has disrupted my timing, but I am actively resolving it now.",
                f"I am writing to apologize for the delay caused by {phrase}. All necessary precautions are being taken to return to schedule as promptly as possible.",
                f"Due to unforeseen constraints regarding {phrase}, I am temporarily held up. I anticipate resuming our scheduled commitments very shortly.",
            ]

    elif tone == 'Casual':
        if creativity == 'Safe':
            pool = [
                f"Hey, so sorry about that! Had a quick hiccup with {phrase}, but I'm on my way right now.",
                f"Running a few minutes behind because {phrase} held me up, but wrapping it up now!",
                f"Sorry for the delay! Just had to deal with {phrase} real quick, heading over now.",
            ]
        elif creativity == 'Creative':
            pool = [
                f"Hey, {phrase} decided to throw a wrench into my schedule today. Almost done untangling it and jumping back in!",
                f"Apologies for the timing—{phrase} completely hijacked my morning. Speeding through it now so we can catch up!",
                f"Running a bit behind thanks to a surprise plot twist with {phrase}, but I'm on it and moving fast!",
            ]
        elif creativity == 'Dramatic':
            pool = [
                f"You honestly won't believe the chaos right now—{phrase} turned everything upside down. Rushing over as fast as humanly possible!",
                f"Total madness today! {phrase} completely derailed my schedule, but I'm sprinting to get things back on track right now.",
                f"It has been a wild scramble ever since {phrase} happened, but I'm surviving and heading your way now!",
            ]
        else: # Normal
            pool = [
                f"So sorry for the hold-up! Dealing with {phrase} took a bit longer than planned, but I'm heading out now.",
                f"Hey, really sorry! Got delayed by {phrase}, but everything is sorted now and I'm on my way.",
                f"Apologies for the delay! {phrase} caught me off guard, but I'm wrapping things up right now.",
            ]

    elif tone == 'Friendly':
        if creativity == 'Safe':
            pool = [
                f"Hi! So sorry to keep you waiting—I had a minor setback with {phrase}. I'll be there as soon as I can!",
                f"Hello! Really sorry for the delay, {phrase} held me up slightly. Heading over now with apologies!",
                f"Hi there! Quick apology for the timing, {phrase} took a little extra time to resolve. On my way shortly!",
            ]
        elif creativity == 'Creative':
            pool = [
                f"Hi! So sorry for the timing—{phrase} threw a little surprise into my morning, but I'm on my way and excited to catch up!",
                f"Hello! Apologies for the hold-up, {phrase} made things interesting today. Wrapping it up now and heading straight to you!",
                f"Hey! Truly sorry for the wait—{phrase} had other ideas for my schedule, but I'm almost there!",
            ]
        elif creativity == 'Dramatic':
            pool = [
                f"Oh no, I'm so terribly sorry! Complete whirlwind this morning with {phrase}. Doing everything I can to get to you right away!",
                f"Hi! What an absolute roller coaster today with {phrase}! I'm rushing over as fast as I can, so sorry for the worry!",
                f"Hello! So sorry for the panic—{phrase} threw my entire morning into overdrive, but I'm en route now!",
            ]
        else: # Normal
            pool = [
                f"Hey there! Apologies for the hold-up, {phrase} caught me off guard. Everything is under control now and I'm heading your way!",
                f"Hi! So sorry about the delay today—got caught up with {phrase}, but I'm finishing up and on my way now.",
                f"Hello! Really sorry for keeping you waiting. {phrase} needed quick attention, but I'm heading over right now!",
            ]

    elif tone == 'Funny':
        if creativity == 'Safe':
            pool = [
                f"If anyone asks, {phrase} is 100% to blame for my timing today. Moving at maximum speed now!",
                f"I swear I had every intention of being prompt until {phrase} intervened. On my way before anything else happens!",
                f"Technically on schedule in another dimension, but in this one {phrase} slowed me down. Speeding over now!",
            ]
        elif creativity == 'Creative':
            pool = [
                f"The universe decided {phrase} was today's mandatory side quest. Quest completed, speeding over now!",
                f"I promise I didn't plan for {phrase} to sabotage my day, but here we are. On my way before gravity gives out next!",
                f"Currently filing a formal complaint against {phrase} for disrupting my schedule. Heading over now at Olympic velocity!",
            ]
        elif creativity == 'Dramatic':
            pool = [
                f"Nature, fate, and {phrase} teamed up against me today in an epic plot. I have survived and am en route!",
                f"A series of unfortunate events starring {phrase} unfolded, but I have prevailed. Expect me shortly in triumphant glory!",
                f"Against all laws of physics and scheduling, {phrase} occurred. I am now defying traffic laws to reach you!",
            ]
        else: # Normal
            pool = [
                f"My sincere apologies—{phrase} threw an unexpected wrench into my master plan. Moving as fast as humanly possible now!",
                f"Not all heroes wear capes; some just manage to escape {phrase} and make it on time. Heading over now!",
                f"Today was going entirely too smoothly until {phrase} showed up. Crisis managed, on my way!",
            ]

    else: # Professional (default)
        if creativity == 'Safe':
            pool = [
                f"Please accept my apologies for the delay. An unexpected issue regarding {phrase} required immediate resolution, and I am proceeding now.",
                f"I am writing to apologize for the delay. I experienced an unforeseen constraint with {phrase}, but matters are resolved and I am en route.",
                f"Apologies for the brief delay. An urgent matter regarding {phrase} needed attention, but I am now available and proceeding.",
            ]
        elif creativity == 'Creative':
            pool = [
                f"An unexpected logistical constraint related to {phrase} temporarily delayed my schedule. Measures are in place and I am resuming normal timing now.",
                f"Please accept my apologies for the timing. An unforeseen scheduling overlap concerning {phrase} arose, but I have adjusted priorities and am ready to proceed.",
                f"I apologize for the disruption. A sudden issue involving {phrase} required immediate remediation, which is now complete. I am on my way.",
            ]
        elif creativity == 'Dramatic':
            pool = [
                f"I apologize for the urgent disruption caused by {phrase}. Immediate corrective action was required, and I am now en route to ensure our commitments are met.",
                f"An unforeseen, critical complication concerning {phrase} demanded emergency intervention this morning. I have resolved the issue and am proceeding with top priority.",
                f"Please accept my apologies for the unexpected delay. I had to manage an urgent situation regarding {phrase}, but am now dedicated to our scheduled agenda.",
            ]
        else: # Normal
            pool = [
                f"Please accept my apologies for the delay. An unexpected development involving {phrase} required my immediate attention, but I have resolved it and am proceeding now.",
                f"I am writing to apologize for the delay caused by {phrase}. I have taken care of the issue and anticipate being available shortly.",
                f"Apologies for the inconvenience regarding our schedule. A sudden delay with {phrase} held me up, but I am en route now.",
            ]

    # Filter out previous excuse to ensure freshness on "Generate Again"
    candidates = [c for c in pool if c.strip() != (previous_excuse or '').strip()]
    if not candidates:
        candidates = pool

    import random
    return random.choice(candidates)


def fallback_improve_excuse(original_excuse: str, tone: str, category: str) -> str:
    """Refine and improve an existing excuse to be distinctly more natural and polished."""
    import re
    import random

    text = original_excuse.strip()
    topic = ""
    # Extract topic from phrases like "concerning late to submit assignment", "involving traffic", etc.
    m = re.search(r'(?:concerning|regarding|involving|about|due to|caused by|with)\s+([^,\.]+?)(?:\s+(?:has|required|demanded|temporarily|arose|took|held|needed|is)|\.|\,|$)', text, re.IGNORECASE)
    if m:
        topic = m.group(1).strip()
        # Clean up leading lowercase or awkward phrases
        topic = _clean_situation_phrase(topic)

    pool = []

    if tone == 'Formal':
        if topic:
            pool = [
                f"Please accept my sincere apologies. An unavoidable complication concerning {topic} temporarily disrupted my timeline, but I have resolved the issue and am proceeding with priority.",
                f"I am writing to respectfully apologize for the delay regarding {topic}. Circumstances beyond my control required immediate attention, but I am now on track and will follow up shortly.",
                f"Due to an unforeseen setback involving {topic}, I have experienced an unavoidable delay. I sincerely apologize for the inconvenience and am taking every measure to conclude this matter promptly.",
            ]
        else:
            pool = [
                "Please accept my sincere apologies for the unexpected delay. An unforeseen complication arose that required my immediate attention, but I have resolved the issue and am proceeding promptly.",
                "I am writing to respectfully apologize for the disruption to our schedule. Unavoidable circumstances temporarily set back my timeline, but I am on track now and will follow up shortly.",
                "Due to an unforeseen setback, I experienced an unavoidable delay. I sincerely apologize for the inconvenience and am taking every measure to conclude this matter promptly.",
            ]

    elif tone == 'Casual':
        if topic:
            pool = [
                f"Hey, so sorry about that! Had to deal with a sudden hiccup with {topic}, but everything is sorted out now and I'm on my way.",
                f"Really sorry for the hold-up! {topic} took longer than expected to resolve, but I'm wrapping things up right now.",
                f"Apologies for the delay! Got caught up dealing with {topic}, but heading over as fast as I can now.",
            ]
        else:
            pool = [
                "Hey, so sorry for the delay! Had to handle a quick unexpected situation, but I'm completely sorted and on my way now.",
                "Really sorry about that! A sudden hiccup held me up, but I'm wrapping it up right now and heading straight over.",
                "Apologies for the hold-up! Got caught off guard by a quick delay, but I'm en route right now.",
            ]

    elif tone == 'Friendly':
        if topic:
            pool = [
                f"Hi! So sorry to keep you waiting—an unexpected complication with {topic} came up, but everything is under control and I'm on my way!",
                f"Hello! Truly sorry for the hold-up. {topic} caught me off guard today, but I'm finishing up now and excited to catch up shortly!",
                f"Hey there! Quick apology for the wait—{topic} threw a little curveball into my schedule, but I'm almost there now!",
            ]
        else:
            pool = [
                "Hi! So sorry to keep you waiting—an unexpected complication came up, but everything is under control and I'm on my way!",
                "Hello! Truly sorry for the hold-up today. Things got a little hectic for a moment, but I'm moving as fast as I can now!",
                "Hey there! Quick apology for the wait—a surprise disruption threw off my schedule, but I'm almost there now!",
            ]

    elif tone == 'Funny':
        if topic:
            pool = [
                f"I have officially negotiated with today's chaos regarding {topic} and won. Sprinting over now before the universe invents another side quest!",
                f"Nature and {topic} teamed up against me today in an epic plot, but I have prevailed and am on my way!",
                f"Against all laws of physics, {topic} occurred. Crisis successfully averted, heading over now at record speed!",
            ]
        else:
            pool = [
                "I have officially negotiated with today's chaos and won. Sprinting over now before the universe invents another side quest!",
                "Nature teamed up against me today in an epic plot, but I have prevailed and am on my way!",
                "Against all laws of physics and scheduling, a wild delay occurred. Crisis successfully averted, heading over now at record speed!",
            ]

    else: # Professional
        if topic:
            pool = [
                f"Please accept my apologies for the delay. An unexpected development regarding {topic} required my immediate attention, but matters are now resolved and I am proceeding.",
                f"I apologize for the setback in our schedule regarding {topic}. Corrective action was taken immediately, and I anticipate being available shortly.",
                f"Apologies for the brief delay. An unforeseen logistical priority involving {topic} needed resolution, but I am now on track and proceeding.",
            ]
        else:
            pool = [
                "Please accept my apologies for the delay. An unforeseen priority required my immediate resolution, but matters are resolved and I am proceeding now.",
                "I apologize for the setback in our schedule today. I have resolved the issue that caused the delay and anticipate being fully available shortly.",
                "Apologies for the brief delay. An urgent matter needed resolution, but I am now on track and proceeding.",
            ]

    # Ensure the improved excuse is noticeably different from the original text
    candidates = [c for c in pool if c.strip() != text]
    if not candidates:
        candidates = pool

    return random.choice(candidates)
