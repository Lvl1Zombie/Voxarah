"""
Voxarah — Character Coaching Database
8 categories, 32 characters. Each character defines:
  - Acoustic benchmarks (pitch tendency, rhythm, energy, etc.)
  - Technique descriptors used for feedback
  - Common mistakes to flag
  - Pro tips specific to the archetype
  - Reference description (what a pro recording sounds like)
"""

from typing import Dict, List


# ─────────────────────────────────────────────────────────────────────────────
# CHARACTER DATABASE
# Each character entry:
#   description     : one-line role summary
#   vocal_qualities : list of what defines this voice
#   benchmarks      : acoustic targets (same keys as analyzer output)
#   common_mistakes : what beginners do wrong
#   pro_tips        : specific coaching advice
#   reference_desc  : what the ideal reference recording sounds like
#   difficulty      : Beginner / Intermediate / Advanced
#   example_pros    : real voice actors known for this archetype
# ─────────────────────────────────────────────────────────────────────────────

CHARACTER_DB: Dict[str, Dict] = {

    # ══════════════════════════════════════════════════════════════
    # FANTASY
    # ══════════════════════════════════════════════════════════════

    "🧙 Wizard": {
        "category": "Fantasy",
        "description": "Ancient, wise, deliberate. Commands gravity without raising volume.",
        "difficulty": "Intermediate",
        "example_pros": ["Ian McKellen (Gandalf)", "Jim Dale", "Tim Curry"],
        "vocal_qualities": [
            "Slower, measured cadence — wisdom is never rushed",
            "Resonant chest voice with slight gravelly undertone",
            "Deliberate pauses before key revelations",
            "Slight upward lilt at end of cryptic statements",
            "Volume drops (not rises) for emphasis — soft = powerful",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (90, 130),
            "pause_ratio":        (0.25, 0.45),
            "energy_consistency": (0.28, 0.38),
            "dynamic_range_db":   (13, 23),
            "max_long_pause_sec": 3.0,
            "clarity_floor_db":  -36,
        },
        "common_mistakes": [
            "Speaking too fast — wizards never rush",
            "Raising volume for emphasis instead of lowering it",
            "Forgetting the 'ancient weight' — voice should feel old, tired, knowing",
            "Over-doing a 'fake old man' voice instead of genuine gravitas",
        ],
        "pro_tips": [
            "Imagine every word costs you magical energy — spend it wisely.",
            "The pause BEFORE the answer is as important as the answer itself.",
            "Let your jaw drop slightly more than normal — opens the resonance chamber.",
            "Think 'gravel wrapped in velvet' — rough texture, smooth delivery.",
            "Breathe from the diaphragm and let the exhale carry the words out slowly.",
        ],
        "reference_desc": "A pro wizard voice has long, weighted pauses before key words. Energy is low and consistent — it never spikes. The pace is 90–120 WPM. Resonance is in the chest, not the throat.",
        "score_weights": {"pause_ratio": 0.30, "speech_rate": 0.25, "consistency": 0.25, "clarity": 0.20},
    },

    "⚔️ Knight": {
        "category": "Fantasy",
        "description": "Noble, disciplined, formal. Duty before self. Clipped consonants.",
        "difficulty": "Beginner",
        "example_pros": ["Sean Bean", "Liam Neeson", "Patrick Stewart"],
        "vocal_qualities": [
            "Upright, formal diction — no contractions when in character",
            "Moderate pace — confident, never hurried",
            "Chest voice, mid-range pitch",
            "Hard consonants, especially T, D, K sounds",
            "Even energy — emotions are controlled, rarely shown",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (120, 155),
            "pause_ratio":        (0.15, 0.28),
            "energy_consistency": (0.30, 0.38),
            "dynamic_range_db":   (12, 20),
            "max_long_pause_sec": 1.5,
            "clarity_floor_db":  -34,
        },
        "common_mistakes": [
            "Sounding too casual — a knight is always 'on duty'",
            "Swallowing consonants — precision matters",
            "Over-emoting — knights suppress feeling, they don't display it",
        ],
        "pro_tips": [
            "Stand up straight while recording — your posture IS your vocal posture.",
            "Think of each sentence as an order or a vow — delivered with finality.",
            "No uptalk. Every sentence lands flat or drops at the end.",
            "Clip your T's and D's sharper than you normally would.",
        ],
        "reference_desc": "Consistent mid-range energy, crisp consonants, very low stutter/hesitation count. Pace is measured. No emotional spikes.",
        "score_weights": {"consistency": 0.35, "pause_ratio": 0.20, "clarity": 0.25, "stutters": 0.20},
    },

    "🧝 Elf": {
        "category": "Fantasy",
        "description": "Ethereal, precise, slightly detached. Musical speech patterns.",
        "difficulty": "Advanced",
        "example_pros": ["Orlando Bloom", "Cate Blanchett", "Hugo Weaving"],
        "vocal_qualities": [
            "Higher placement — voice sits in the mask/sinuses, not chest",
            "Very clean diction — elves don't mumble",
            "Slightly elongated vowels — lyrical quality",
            "Minimal filler sounds — silence is preferred to 'um'",
            "Cool emotional temperature — moved but never rattled",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (110, 145),
            "pause_ratio":        (0.20, 0.38),
            "energy_consistency": (0.31, 0.39),
            "dynamic_range_db":   (10, 18),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -32,
        },
        "common_mistakes": [
            "Dropping into chest voice — stays too human-sounding",
            "Rushing — elves have lived 3,000 years, they're not in a hurry",
            "Unclear consonants — elven speech is crystal clear",
            "Too much emotion — elves are restrained to the point of seeming alien",
        ],
        "pro_tips": [
            "Raise your soft palate as if you just smelled something pleasant — opens nasal resonance.",
            "Elongate every vowel by about 20% longer than feels natural.",
            "Record standing, chin slightly elevated.",
            "Think of speech as music — there's a subtle melody in every sentence.",
        ],
        "reference_desc": "Very high clarity score, near-zero unclear sections. Energy consistency above 85%. Pace deliberate but not slow. Almost no stutter flags.",
        "score_weights": {"clarity": 0.35, "consistency": 0.30, "pause_ratio": 0.20, "stutters": 0.15},
    },

    "🐉 Dragon": {
        "category": "Fantasy",
        "description": "Ancient predator. Vast power held casually. Contemptuous amusement.",
        "difficulty": "Advanced",
        "example_pros": ["Benedict Cumberbatch (Smaug)", "Frank Welker", "Keith David"],
        "vocal_qualities": [
            "Extremely low, resonant chest/sub-chest placement",
            "Very slow — a dragon has nothing to prove",
            "Wide dynamic range — whispers feel more dangerous than shouts",
            "Rolled or slightly hissed sibilants (S sounds)",
            "Pauses that feel like a predator choosing whether to strike",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (70, 110),
            "pause_ratio":        (0.30, 0.55),
            "energy_consistency": (0.20, 0.33),
            "dynamic_range_db":   (23, 40),
            "max_long_pause_sec": 4.0,
            "clarity_floor_db":  -38,
        },
        "common_mistakes": [
            "Speaking too fast — ruins the sense of ancient power",
            "Staying at one volume — variation is what makes dragons terrifying",
            "Straining for low notes — if it hurts, you're forcing it",
            "Forgetting the contempt — dragons find humans amusing, not threatening",
        ],
        "pro_tips": [
            "Record after humming deeply for 30 seconds — warms up chest resonance.",
            "Let your jaw hang loose — constriction is the enemy of dragon voice.",
            "Drop your chin slightly toward your chest for more sub-bass resonance.",
            "Play with a slight elongation of S sounds — 'yesss' not 'yes'.",
            "A dragon never sounds urgent. Every pause says 'I could end you whenever I choose.'",
        ],
        "reference_desc": "Very low pace (70–110 WPM), high pause ratio, very high dynamic range. The voice should have audible sub-bass resonance. Wide swings between soft and loud.",
        "score_weights": {"pause_ratio": 0.30, "dynamic_range": 0.25, "speech_rate": 0.25, "clarity": 0.20},
    },

    "👑 Dark Lord": {
        "category": "Fantasy",
        "description": "Cold, absolute power. Every word is a verdict. No desperation, no shouting.",
        "difficulty": "Advanced",
        "example_pros": ["James Earl Jones", "Tim Curry", "Tony Jay"],
        "vocal_qualities": [
            "Low, cold, controlled — never shouts, never begs",
            "Clipped, final consonants — sentences end like cell doors slamming",
            "Very slow when angry, slightly faster when amused",
            "Zero filler words — silence is preferred",
            "The voice of someone who has already won",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (80, 125),
            "pause_ratio":        (0.28, 0.48),
            "energy_consistency": (0.29, 0.38),
            "dynamic_range_db":   (15, 28),
            "max_long_pause_sec": 3.5,
            "clarity_floor_db":  -34,
        },
        "common_mistakes": [
            "Shouting for menace — the scariest villains are quiet",
            "Sounding frustrated — a dark lord is never rattled",
            "Speeding up — urgency implies weakness",
            "Upward inflection at sentence ends — everything is a statement, never a question",
        ],
        "pro_tips": [
            "The dark lord has already won — play from that position of total security.",
            "Your lowest note, spoken clearly, is more menacing than any shout.",
            "End every sentence with a slight downward pitch drop — finality.",
            "Practice saying 'no' in as many terrifying ways as possible.",
        ],
        "reference_desc": "Low, even energy. Very low stutter count. Pace slow and deliberate. Almost no upward inflection. Wide but controlled dynamic range.",
        "score_weights": {"consistency": 0.30, "pause_ratio": 0.25, "stutters": 0.25, "clarity": 0.20},
    },

    # ══════════════════════════════════════════════════════════════
    # SCI-FI
    # ══════════════════════════════════════════════════════════════

    "🤖 Robot / AI": {
        "category": "Sci-Fi",
        "description": "Precise, logical, affectless — or unsettlingly close to human.",
        "difficulty": "Intermediate",
        "example_pros": ["GLaDOS (Ellen McLain)", "HAL 9000 (Douglas Rain)", "Alan Tudyk (K-2SO)"],
        "vocal_qualities": [
            "Extremely even cadence — no natural speech rhythm variation",
            "Flat emotional affect with occasional jarring precision",
            "Very high clarity — every phoneme enunciated",
            "Unnatural pause placement — pauses mid-sentence, not at punctuation",
            "Zero filler words — a robot doesn't say 'um'",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (115, 150),
            "pause_ratio":        (0.18, 0.35),
            "energy_consistency": (0.34, 0.40),
            "dynamic_range_db":   (8, 15),
            "max_long_pause_sec": 1.8,
            "clarity_floor_db":  -30,
        },
        "common_mistakes": [
            "Natural speech rhythm — too human, breaks the illusion",
            "Emotional inflection on the wrong words",
            "Unclear consonants — robots are precise",
            "Rushing — processing takes time",
        ],
        "pro_tips": [
            "Place pauses where a human WOULDN'T — mid-clause, after an adjective.",
            "Pick one word per sentence to deliver with slightly more volume — simulate data emphasis.",
            "Imagine you are reading from a screen that updates one word at a time.",
            "For sinister AI: keep energy perfectly flat until one sudden word that's slightly too loud.",
        ],
        "reference_desc": "Near-perfect energy consistency (88%+). Very high clarity. Dynamic range narrow. Zero stutters. Pauses placed unnaturally.",
        "score_weights": {"consistency": 0.40, "clarity": 0.30, "stutters": 0.20, "pause_ratio": 0.10},
    },

    "👽 Alien": {
        "category": "Sci-Fi",
        "description": "Non-human thought patterns made audible. Curiosity mixed with otherness.",
        "difficulty": "Advanced",
        "example_pros": ["Alan Rickman (Metatron)", "Doug Jones", "Dee Bradley Baker"],
        "vocal_qualities": [
            "Unusual cadence — rhythm patterns that don't match English speech",
            "Occasional clicks, glottal sounds, or elongated vowels",
            "Wide dynamic variation — concepts that excite the alien get louder",
            "Pauses that suggest translation or processing",
            "High clarity on individual words, but sentence flow is 'wrong'",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (85, 145),
            "pause_ratio":        (0.22, 0.45),
            "energy_consistency": (0.13, 0.28),
            "dynamic_range_db":   (20, 35),
            "max_long_pause_sec": 3.0,
            "clarity_floor_db":  -35,
        },
        "common_mistakes": [
            "Sounding too human — the whole point is otherness",
            "Consistent rhythm — aliens should feel unpredictable",
            "Playing 'funny alien' vs genuinely alien thought processes",
        ],
        "pro_tips": [
            "Write out your script, then deliberately stress the WRONG syllables.",
            "Add a beat of silence before words the alien finds fascinating.",
            "Let your energy spike suddenly on random nouns — like they're fascinating discoveries.",
            "Physicalize it — tilt your head to one side while recording.",
        ],
        "reference_desc": "Irregular energy pattern. High dynamic range. Varied pause placement. Low consistency score is EXPECTED and good for this character.",
        "score_weights": {"dynamic_range": 0.30, "pause_ratio": 0.25, "clarity": 0.25, "consistency": 0.20},
    },

    "🦾 Cyborg": {
        "category": "Sci-Fi",
        "description": "Human emotion fighting through mechanical precision. Internal conflict made audible.",
        "difficulty": "Intermediate",
        "example_pros": ["Arnold Schwarzenegger (T-800)", "Peter Weller (RoboCop)", "Brent Spiner (Data)"],
        "vocal_qualities": [
            "Alternates between flat robotic delivery and sudden emotional breaks",
            "Slightly slower than natural speech — processing delay",
            "Hard stops between thoughts — no blending sentences",
            "Occasional delivery 'glitches' — a word repeated mechanically, then corrected",
            "Emotional words delivered flatter than expected",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (110, 145),
            "pause_ratio":        (0.18, 0.32),
            "energy_consistency": (0.20, 0.31),
            "dynamic_range_db":   (15, 28),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -33,
        },
        "common_mistakes": [
            "Staying fully robotic — the humanity must fight through occasionally",
            "Over-doing the robot affect until it becomes parody",
            "Inconsistent internal logic — pick a ratio of human:machine and stick to it",
        ],
        "pro_tips": [
            "Decide your human/machine ratio before recording: 30/70? 60/40?",
            "The emotional breaks should feel involuntary — like a system error.",
            "Hard stops (full silence) between sentences simulate processing.",
            "One or two words per paragraph delivered with full human emotion — then back to flat.",
        ],
        "reference_desc": "Mid-range consistency — not as flat as pure Robot, not as variable as human. Moderate dynamic range. Occasional energy spikes where emotion breaks through.",
        "score_weights": {"consistency": 0.25, "dynamic_range": 0.30, "clarity": 0.25, "pause_ratio": 0.20},
    },

    "🚀 Space Commander": {
        "category": "Sci-Fi",
        "description": "Authority, composure under pressure. Kirk, Picard, Shepard energy.",
        "difficulty": "Beginner",
        "example_pros": ["Patrick Stewart", "Jennifer Hale", "Keith David"],
        "vocal_qualities": [
            "Commanding mid-to-low range — not deep, just certain",
            "Moderate pace — brisk but never rushed",
            "Very clean delivery — no hesitation in a crisis",
            "Emphasis on verbs and commands",
            "Calm under pressure — energy stays even even in action",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (135, 165),
            "pause_ratio":        (0.12, 0.24),
            "energy_consistency": (0.29, 0.37),
            "dynamic_range_db":   (13, 23),
            "max_long_pause_sec": 1.2,
            "clarity_floor_db":  -33,
        },
        "common_mistakes": [
            "Sounding nervous or uncertain — a commander never telegraphs doubt",
            "Too many pauses — in a crisis, hesitation costs lives",
            "Upward inflection on orders — commands go DOWN, not up",
        ],
        "pro_tips": [
            "Speak as if your crew's lives depend on being understood clearly.",
            "Every order ends with a period, not a question mark.",
            "Slight forward lean while recording — physicalize the command posture.",
            "Stress the ACTION word in every sentence: 'FIRE the engines', not 'Fire the ENGINES'.",
        ],
        "reference_desc": "High clarity, moderate-to-high consistency. Low pause ratio — commands are crisp. All sentence endings drop in pitch.",
        "score_weights": {"clarity": 0.30, "consistency": 0.30, "stutters": 0.20, "pause_ratio": 0.20},
    },

    # ══════════════════════════════════════════════════════════════
    # VILLAIN
    # ══════════════════════════════════════════════════════════════

    "😈 Classic Villain": {
        "category": "Villain",
        "description": "Theatrical, self-aware evil. Relishes the role. Dramatic pauses.",
        "difficulty": "Beginner",
        "example_pros": ["Tim Curry", "Alan Rickman", "Jeremy Irons"],
        "vocal_qualities": [
            "Rich, theatrical delivery — villains love the sound of their own voice",
            "Deliberate pacing with dramatic pauses",
            "Slight smile in the voice — enjoying every word",
            "Elongated vowels on key evil words",
            "Controlled but wide dynamic range — builds to crescendos",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (95, 135),
            "pause_ratio":        (0.22, 0.40),
            "energy_consistency": (0.18, 0.30),
            "dynamic_range_db":   (20, 33),
            "max_long_pause_sec": 3.0,
            "clarity_floor_db":  -34,
        },
        "common_mistakes": [
            "Being generically angry instead of deliciously evil",
            "No dynamic build — flat delivery kills the theatricality",
            "Forgetting the enjoyment — a classic villain is having FUN",
        ],
        "pro_tips": [
            "Smile while delivering villain lines — it changes your vowels in subtle, perfect ways.",
            "Find one word per speech to luxuriate in — drag it out, love it.",
            "The villain KNOWS they're going to win. Play from confidence, not desperation.",
            "Watch Alan Rickman in anything for master classes in deliberate pacing.",
        ],
        "reference_desc": "Wide dynamic range. Deliberate pace. Dramatic pause before the best lines. Energy builds and releases in waves. Theatrical but controlled.",
        "score_weights": {"dynamic_range": 0.30, "pause_ratio": 0.25, "consistency": 0.20, "clarity": 0.25},
    },

    "😤 Menacing Villain": {
        "category": "Villain",
        "description": "Cold, dangerous, unpredictable. Makes silence feel threatening.",
        "difficulty": "Advanced",
        "example_pros": ["Anthony Hopkins (Hannibal)", "Javier Bardem (Anton Chigurh)", "Mark Hamill (Joker)"],
        "vocal_qualities": [
            "Quiet is the weapon — stays low until suddenly very loud",
            "Unnervingly calm — the danger is in the stillness",
            "Very deliberate word selection, each word chosen like a knife",
            "Long pauses that feel like threats",
            "Sudden volume spikes that snap the listener to attention",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (80, 120),
            "pause_ratio":        (0.30, 0.52),
            "energy_consistency": (0.23, 0.33),
            "dynamic_range_db":   (23, 38),
            "max_long_pause_sec": 4.0,
            "clarity_floor_db":  -36,
        },
        "common_mistakes": [
            "Playing loud instead of quiet — menace lives in restraint",
            "Telegraphing the danger — a menacing villain sounds almost normal until they don't",
            "Rushing — urgency destroys menace entirely",
        ],
        "pro_tips": [
            "The most threatening thing you can do is sound completely reasonable.",
            "Save your one loud moment for maximum effect — earn it.",
            "Breathe slowly and audibly — let the mic catch your controlled breath.",
            "Imagine you are explaining something to someone who has made a terrible mistake.",
        ],
        "reference_desc": "Very high pause ratio. Wide dynamic range with mostly quiet delivery and rare loud spikes. Pace very slow. Consistency moderate — the variation is part of the threat.",
        "score_weights": {"pause_ratio": 0.35, "dynamic_range": 0.30, "speech_rate": 0.20, "clarity": 0.15},
    },

    "🕸️ Manipulative Villain": {
        "category": "Villain",
        "description": "Charming, persuasive, warm on the surface. Danger hidden in honey.",
        "difficulty": "Advanced",
        "example_pros": ["Tom Hiddleston (Loki)", "Kevin Spacey", "Cate Blanchett"],
        "vocal_qualities": [
            "Warm, friendly tone — this is the dangerous part",
            "Smooth, flowing delivery — no harsh edges",
            "Strategic pauses that feel like genuine thoughtfulness",
            "Slightly faster than average — confidence, not desperation",
            "Voice that makes you want to trust it",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (135, 170),
            "pause_ratio":        (0.12, 0.25),
            "energy_consistency": (0.28, 0.36),
            "dynamic_range_db":   (12, 22),
            "max_long_pause_sec": 1.5,
            "clarity_floor_db":  -32,
        },
        "common_mistakes": [
            "Sounding too villainous — the manipulation only works if they trust you first",
            "Too much pause — this character moves at the speed of persuasion",
            "Flat affect — warmth is the entire tool",
        ],
        "pro_tips": [
            "Think: 'I genuinely want to help you. It happens to also serve my purposes.'",
            "Smile warmly. Your voice should sound like someone who gives great hugs.",
            "The dangerous words should sound the MOST reasonable of all.",
            "Study how good salespeople talk — the manipulative villain is selling something.",
        ],
        "reference_desc": "High consistency, warm energy, faster pace, low pause ratio. Sounds almost indistinguishable from a hero's voice on acoustic analysis alone.",
        "score_weights": {"consistency": 0.35, "clarity": 0.25, "pause_ratio": 0.20, "stutters": 0.20},
    },

    "🤪 Unhinged Villain": {
        "category": "Villain",
        "description": "Chaotic, unpredictable, gleefully dangerous. Logic is optional.",
        "difficulty": "Advanced",
        "example_pros": ["Mark Hamill (Joker)", "Heath Ledger", "Jim Carrey (The Mask)"],
        "vocal_qualities": [
            "Wildly variable energy — loud, soft, fast, slow with no warning",
            "Sudden laughter or tonal breaks mid-sentence",
            "Rhetorical questions delivered as genuine curiosity",
            "Occasional unsettling calm amid the chaos",
            "Voice that sounds like it's about to do something unexpected",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (90, 200),  # enormous range — varies wildly
            "pause_ratio":        (0.10, 0.40),
            "energy_consistency": (0.00, 0.18),  # LOW consistency is CORRECT
            "dynamic_range_db":   (28, 45),
            "max_long_pause_sec": 4.0,
            "clarity_floor_db":  -36,
        },
        "common_mistakes": [
            "Being consistently loud — that's just angry, not unhinged",
            "Predictable rhythm — the chaos must feel genuinely random",
            "Forgetting the sudden calm moments — they're the most unsettling",
        ],
        "pro_tips": [
            "Record each sentence as if you just thought of it for the first time.",
            "Mid-sentence tone shifts are your superpower — start serious, end giggling.",
            "The unhinged villain asks 'why' in situations where no sane person would.",
            "Low consistency score in analysis is a FEATURE for this character, not a bug.",
        ],
        "reference_desc": "Very high dynamic range. Low consistency — this is intentional. Wide pace variation. Unpredictable energy pattern. High contrast between loud and soft moments.",
        "score_weights": {"dynamic_range": 0.40, "pause_ratio": 0.20, "clarity": 0.20, "consistency": 0.20},
    },

    # ══════════════════════════════════════════════════════════════
    # HERO
    # ══════════════════════════════════════════════════════════════

    "🦸 Classic Hero": {
        "category": "Hero",
        "description": "Confident, warm, decisive. The voice people run toward in a crisis.",
        "difficulty": "Beginner",
        "example_pros": ["Chris Evans (Cap)", "Dwayne Johnson", "Gal Gadot"],
        "vocal_qualities": [
            "Warm mid-range — not too deep, approachable and strong",
            "Moderate-to-brisk pace — decisive, not rushed",
            "Clear emphasis on action words and names",
            "Energy that rises slightly when calling others to action",
            "Conviction on every line — no vocal fry or trailing off",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (135, 170),
            "pause_ratio":        (0.12, 0.22),
            "energy_consistency": (0.26, 0.35),
            "dynamic_range_db":   (15, 25),
            "max_long_pause_sec": 1.2,
            "clarity_floor_db":  -33,
        },
        "common_mistakes": [
            "Sounding flat or uncertain — a hero's voice never wavers",
            "Too low and gravelly — that's a dark hero, not a classic one",
            "Over-emoting — earnest is the goal, not melodramatic",
        ],
        "pro_tips": [
            "Think of someone you genuinely admire and speak as them.",
            "Your voice should make people feel safer just hearing it.",
            "Slight forward lean, chest open — the body position matters.",
            "End sentences with conviction — no trailing off, ever.",
        ],
        "reference_desc": "High clarity, moderate consistency, warm energy. Pace brisk and purposeful. Low pause ratio — heroes don't hesitate long.",
        "score_weights": {"clarity": 0.30, "consistency": 0.30, "stutters": 0.20, "pause_ratio": 0.20},
    },

    "😔 Reluctant Hero": {
        "category": "Hero",
        "description": "Burdened, tired, dragged into greatness. Heart of gold, weight of the world.",
        "difficulty": "Intermediate",
        "example_pros": ["Tobey Maguire (Spider-Man)", "Elijah Wood (Frodo)", "Hugh Jackman (Logan)"],
        "vocal_qualities": [
            "Slightly slower, heavier delivery — the burden is audible",
            "Occasional breath sighs before answering",
            "Warm but worn — like a good person having a very bad year",
            "Conviction arrives LATE in sentences — starts unsure, ends resolved",
            "Genuine emotional texture — this character actually hurts",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (110, 148),
            "pause_ratio":        (0.20, 0.35),
            "energy_consistency": (0.20, 0.31),
            "dynamic_range_db":   (15, 28),
            "max_long_pause_sec": 2.5,
            "clarity_floor_db":  -35,
        },
        "common_mistakes": [
            "Sounding whiny instead of weary — there's a crucial difference",
            "No moments of genuine resolve — the heroism must arrive",
            "Staying at one emotional level — this character has a journey within each speech",
        ],
        "pro_tips": [
            "Think of the last time you did something hard because it was right, not because it was easy.",
            "The reluctant hero sighs. Let real sighs happen before important lines.",
            "Start sentences quiet and unresolved. Let conviction build mid-line.",
            "There's a moment in every reluctant hero speech where they decide. Find that moment.",
        ],
        "reference_desc": "Moderate consistency — emotional variation is authentic. Moderate pace. Some long pauses (thinking/deciding). Dynamic range moderate-to-wide.",
        "score_weights": {"dynamic_range": 0.25, "pause_ratio": 0.25, "consistency": 0.25, "clarity": 0.25},
    },

    "🖤 Anti-Hero": {
        "category": "Hero",
        "description": "Morally grey, sharp-edged, doesn't ask for your approval.",
        "difficulty": "Intermediate",
        "example_pros": ["Ryan Reynolds (Deadpool)", "Robert Downey Jr. (early Tony Stark)", "Keanu Reeves (John Wick)"],
        "vocal_qualities": [
            "Dry, flat affect with occasional unexpected warmth",
            "Sardonic undertone — this character finds everyone slightly ridiculous",
            "Clipped sentences — doesn't waste words",
            "Low energy that spikes unpredictably",
            "The voice of someone who has seen too much and cares just enough",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (125, 165),
            "pause_ratio":        (0.15, 0.28),
            "energy_consistency": (0.20, 0.31),
            "dynamic_range_db":   (18, 30),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -34,
        },
        "common_mistakes": [
            "Playing cool so hard it becomes boring — there must be something underneath",
            "No warmth anywhere — even anti-heroes have a thing they care about",
            "Over-explaining — this character doesn't justify themselves",
        ],
        "pro_tips": [
            "The anti-hero is the smartest person in the room and is tired of it.",
            "One unexpected moment of genuine warmth per scene does more work than anything else.",
            "Speak as if you'd rather not be having this conversation, but here you are.",
            "Dry humor lives in flat delivery of absurd content — let the words do the work.",
        ],
        "reference_desc": "Mid-range everything — not the extremes of hero or villain. Dry affect with occasional energy spikes. Some sardonic pause placement.",
        "score_weights": {"consistency": 0.25, "dynamic_range": 0.30, "clarity": 0.25, "pause_ratio": 0.20},
    },

    # ══════════════════════════════════════════════════════════════
    # CREATURE
    # ══════════════════════════════════════════════════════════════

    "👹 Monster": {
        "category": "Creature",
        "description": "Raw threat, barely contained. Primal, guttural, terrifyingly present.",
        "difficulty": "Intermediate",
        "example_pros": ["Frank Welker", "Fred Tatasciore", "Steve Blum"],
        "vocal_qualities": [
            "Deep, rough, guttural chest-to-throat placement",
            "Short, aggressive sentences — monsters don't give speeches",
            "Wide dynamic range — from growling quiet to sudden roars",
            "Consonants are crushed and smeared — sloppy but powerful",
            "Breath sounds are part of the performance — panting, snarling",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (80, 130),
            "pause_ratio":        (0.20, 0.42),
            "energy_consistency": (0.10, 0.26),
            "dynamic_range_db":   (25, 42),
            "max_long_pause_sec": 3.0,
            "clarity_floor_db":  -40,
        },
        "common_mistakes": [
            "Over-enunciating — monsters aren't concerned with being understood",
            "Staying at one volume — variation is what makes it feel alive",
            "Forgetting physicality — a monster voice requires a monster body posture",
        ],
        "pro_tips": [
            "Crouch slightly while recording — physicalize the creature.",
            "Breathe through your mouth audibly — let the mic catch animal breath.",
            "Drop your jaw as low as physically comfortable before each take.",
            "Unclear sections in analysis are FINE — monsters aren't meant to be clear.",
        ],
        "reference_desc": "Very high dynamic range. Low-to-moderate clarity is acceptable. Wide energy variation. Some low-clarity sections are correct for this character.",
        "score_weights": {"dynamic_range": 0.40, "pause_ratio": 0.25, "speech_rate": 0.20, "clarity": 0.15},
    },

    "🐗 Beast": {
        "category": "Creature",
        "description": "Powerful but not purely hostile. Animal intelligence, animal dignity.",
        "difficulty": "Intermediate",
        "example_pros": ["Paige O'Hara (Beast)", "Ron Perlman", "Michael Clarke Duncan"],
        "vocal_qualities": [
            "Deep, textured, with animal breath quality",
            "Slow when calm, fast when threatened",
            "Doesn't care about human social niceties in delivery",
            "Raw emotional honesty — beasts don't hide feelings",
            "Occasional growl-tones on consonants",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (95, 145),
            "pause_ratio":        (0.22, 0.40),
            "energy_consistency": (0.15, 0.29),
            "dynamic_range_db":   (20, 35),
            "max_long_pause_sec": 3.5,
            "clarity_floor_db":  -37,
        },
        "common_mistakes": [
            "Playing beast as just 'angry person' — there must be animal qualities",
            "Inconsistent animal texture — commit fully or not at all",
        ],
        "pro_tips": [
            "Let your emotions be huge and unfiltered — the beast has no self-censorship.",
            "Growl-tone: tighten the back of your throat slightly on key consonants.",
            "Breathe more audibly than you think is right — then add 20% more.",
        ],
        "reference_desc": "Wide dynamic range. Moderate-to-low clarity acceptable. High energy variation. Authentic emotional peaks and troughs.",
        "score_weights": {"dynamic_range": 0.35, "pause_ratio": 0.25, "consistency": 0.20, "clarity": 0.20},
    },

    "👺 Goblin": {
        "category": "Creature",
        "description": "Scheming, skittery, self-serving. High energy, high pitch, nervous tics.",
        "difficulty": "Beginner",
        "example_pros": ["Andy Serkis (Gollum)", "Tom Kenny", "Billy West"],
        "vocal_qualities": [
            "Higher placement — forward in the mouth/nasal area",
            "Fast and nervous — goblins are always in motion",
            "Lots of consonant emphasis — spitting, hissing, clicking",
            "Variable rhythm — goblins think in bursts",
            "Occasional giggle, cackle, or whimper",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (155, 200),
            "pause_ratio":        (0.08, 0.20),
            "energy_consistency": (0.08, 0.23),
            "dynamic_range_db":   (23, 38),
            "max_long_pause_sec": 0.8,
            "clarity_floor_db":  -36,
        },
        "common_mistakes": [
            "Too slow — goblins have ants in their pants",
            "Too deep — move it forward and higher in the mouth",
            "Not enough consonant spitting — lean into the sibilants",
        ],
        "pro_tips": [
            "Raise your soft palate AND slightly pinch the back of your throat.",
            "Talk faster than feels right, then add 20% more speed.",
            "Physicalize it: hunch over the mic, get small and scheming.",
            "Goblins interrupt themselves — start a thought, abandon it, start another.",
        ],
        "reference_desc": "Fast pace, low pause ratio, high dynamic range, low consistency. High energy variation. Some sibilant-heavy delivery patterns.",
        "score_weights": {"speech_rate": 0.30, "dynamic_range": 0.30, "pause_ratio": 0.20, "consistency": 0.20},
    },

    "🌌 Ancient Being": {
        "category": "Creature",
        "description": "Older than language. Reality is a suggestion. Speaks in geological time.",
        "difficulty": "Advanced",
        "example_pros": ["Tilda Swinton", "Cate Blanchett", "Ralph Fiennes"],
        "vocal_qualities": [
            "Extremely slow — time means nothing to this being",
            "Every word carries the weight of eons",
            "Minimal movement in pitch — vast calm",
            "Pauses that feel like continental drift",
            "Low, resonant, slightly other — like wind through stone",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (55, 90),
            "pause_ratio":        (0.40, 0.65),
            "energy_consistency": (0.30, 0.39),
            "dynamic_range_db":   (10, 20),
            "max_long_pause_sec": 6.0,
            "clarity_floor_db":  -36,
        },
        "common_mistakes": [
            "Speaking at human speed — this being has no urgency",
            "Emotional inflection — this being is beyond that",
            "Not trusting the silence — the pause IS the performance",
        ],
        "pro_tips": [
            "Record at half the speed that feels natural. Then slow down more.",
            "Imagine you have spoken ten words this millennium — choose carefully.",
            "The silence between your words should feel heavier than the words themselves.",
            "Breathe very slowly and deliberately before each take.",
        ],
        "reference_desc": "Extremely slow pace (55–90 WPM). Very high pause ratio. Near-perfect consistency. Very long individual pauses. Narrow dynamic range.",
        "score_weights": {"pause_ratio": 0.35, "speech_rate": 0.30, "consistency": 0.25, "clarity": 0.10},
    },

    # ══════════════════════════════════════════════════════════════
    # HISTORICAL
    # ══════════════════════════════════════════════════════════════

    "🏚️ Medieval Peasant": {
        "category": "Historical",
        "description": "Rough-edged, superstitious, earthy. Hard life visible in every word.",
        "difficulty": "Beginner",
        "example_pros": ["John Cleese (Monty Python)", "Terry Jones", "Graham Chapman"],
        "vocal_qualities": [
            "Rough, unpolished — no elocution lessons for this one",
            "Regional accent texture (Northern English / rural as baseline)",
            "Lots of dropped H's, swallowed vowels",
            "Nervous when addressing authority, bold with equals",
            "High pitch under stress, low and muttering normally",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (120, 160),
            "pause_ratio":        (0.12, 0.28),
            "energy_consistency": (0.13, 0.26),
            "dynamic_range_db":   (18, 33),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -38,
        },
        "common_mistakes": [
            "Too posh — this character has never seen the inside of a school",
            "Consistent energy — peasants are reactive, not composed",
        ],
        "pro_tips": [
            "Let your jaw relax completely — open vowels and dropped consonants.",
            "Think about what frightens this character (plague, lord, winter) and let that anxiety in.",
            "Rough is right — don't clean up the consonants.",
        ],
        "reference_desc": "Rough clarity, high energy variation, reactive dynamics. Some unclear sections are expected and correct.",
        "score_weights": {"dynamic_range": 0.30, "consistency": 0.20, "pause_ratio": 0.25, "clarity": 0.25},
    },

    "🎩 Victorian Noble": {
        "category": "Historical",
        "description": "Measured, superior, impeccably enunciated. Class is a weapon.",
        "difficulty": "Intermediate",
        "example_pros": ["Hugh Laurie", "Emma Thompson", "Jeremy Irons"],
        "vocal_qualities": [
            "Received Pronunciation — crisp, elevated British vowels",
            "Perfectly controlled — emotions are managed, not expressed",
            "Slightly slower than modern speech — gravitas matters",
            "Nasal quality — speaking from a position of elevation",
            "Loaded pauses — silence used as condescension",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (115, 148),
            "pause_ratio":        (0.18, 0.32),
            "energy_consistency": (0.31, 0.39),
            "dynamic_range_db":   (10, 18),
            "max_long_pause_sec": 2.5,
            "clarity_floor_db":  -30,
        },
        "common_mistakes": [
            "Not crisp enough — every T and D must be a small event",
            "Too much emotion showing — Victorians were emotional but never showed it",
            "American vowels sneaking in — watch your A sounds",
        ],
        "pro_tips": [
            "Imagine a marble in your mouth — it raises your vowels correctly.",
            "Every sentence ends as if you've just said the final word on the matter.",
            "Silence is dismissal — use pause to indicate you find the topic beneath you.",
            "The word 'quite' can mean anything from rage to approval — explore it.",
        ],
        "reference_desc": "Very high clarity. High consistency. Narrow dynamic range — emotions tightly controlled. Very deliberate consonants.",
        "score_weights": {"clarity": 0.35, "consistency": 0.35, "dynamic_range": 0.15, "pause_ratio": 0.15},
    },

    "🏛️ Roman General": {
        "category": "Historical",
        "description": "Absolute authority, earned through blood and campaign. Short, total commands.",
        "difficulty": "Intermediate",
        "example_pros": ["Russell Crowe (Gladiator)", "Richard Harris", "Oliver Reed"],
        "vocal_qualities": [
            "Deep, resonant, trained for open-air projection",
            "Commands are short and final — three words maximum per order",
            "No softening language — direct to the point of brutality",
            "Slightly slower than natural — gravitas over speed",
            "Impatience under the surface — this person's time is precious",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (110, 145),
            "pause_ratio":        (0.15, 0.28),
            "energy_consistency": (0.29, 0.37),
            "dynamic_range_db":   (15, 28),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -32,
        },
        "common_mistakes": [
            "Too many words — a general commands, not explains",
            "Upward inflection — this general doesn't ask, they tell",
            "Emotional wavering — troops need a rock, not a person",
        ],
        "pro_tips": [
            "Reduce every speech to its shortest possible form. Then cut 20% more.",
            "Every sentence is a command or a fact — no opinions, no feelings.",
            "Stand while recording. Feet shoulder-width. Chin level.",
            "Impatience is the secret flavor — this person has a war to win.",
        ],
        "reference_desc": "High clarity, high consistency. Short, final sentences. Low pause ratio within sentences. Low-pitched, projected delivery.",
        "score_weights": {"clarity": 0.30, "consistency": 0.30, "stutters": 0.25, "pause_ratio": 0.15},
    },

    # ══════════════════════════════════════════════════════════════
    # MODERN
    # ══════════════════════════════════════════════════════════════

    "📺 News Anchor": {
        "category": "Modern",
        "description": "Authoritative, neutral, trustworthy. The voice of official truth.",
        "difficulty": "Beginner",
        "example_pros": ["Walter Cronkite", "Anderson Cooper", "Soledad O'Brien"],
        "vocal_qualities": [
            "Mid-range, neutral American accent as baseline",
            "Perfectly even pace — no rushing, no dragging",
            "Every word is equally important — no emphasis spikes",
            "Minimal pausing except for sentence breaks",
            "Zero personality bleeding through — neutral is the goal",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (145, 175),
            "pause_ratio":        (0.10, 0.20),
            "energy_consistency": (0.34, 0.40),
            "dynamic_range_db":   (8, 14),
            "max_long_pause_sec": 1.2,
            "clarity_floor_db":  -28,
        },
        "common_mistakes": [
            "Personality — this is not the place for it",
            "Uneven energy — if one word is louder, something is wrong",
            "Any unclear sections — broadcast clarity is non-negotiable",
        ],
        "pro_tips": [
            "Record this one standing, with the script at eye level — posture = clarity.",
            "Your goal: sound like someone your grandparents would trust with the news.",
            "Stress pattern is subject-verb. Everything else is equally neutral.",
            "Listen back and flag any word that sounds more important than another — level it.",
        ],
        "reference_desc": "Near-perfect consistency. Highest clarity requirement of all characters. Very low dynamic range — everything is even. Zero stutters acceptable.",
        "score_weights": {"consistency": 0.40, "clarity": 0.35, "stutters": 0.15, "pause_ratio": 0.10},
    },

    "🔍 Detective": {
        "category": "Modern",
        "description": "Sharp, observational, thinking aloud. The voice that assembles truth.",
        "difficulty": "Intermediate",
        "example_pros": ["Benedict Cumberbatch (Sherlock)", "Humphrey Bogart", "Viola Davis"],
        "vocal_qualities": [
            "Slightly faster than average — mind always running ahead",
            "Emphasis on observational words: 'interesting', 'notice', 'exactly'",
            "Strategic pauses that imply thinking, not hesitation",
            "Dry, economical — doesn't say what doesn't need saying",
            "Occasional ironic warmth — the detective finds humans fascinating",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (140, 178),
            "pause_ratio":        (0.14, 0.26),
            "energy_consistency": (0.24, 0.34),
            "dynamic_range_db":   (15, 25),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -33,
        },
        "common_mistakes": [
            "Sounding unsure — a detective's conclusions are always delivered as facts",
            "Too emotional — observation requires distance",
            "Not enough variation — the voice should move with the thought process",
        ],
        "pro_tips": [
            "Pause before the KEY deduction — that's the money moment.",
            "Stress verbs of observation: 'notice', 'see', 'realize', 'observe'.",
            "The detective is always slightly ahead of the conversation — pace accordingly.",
            "Dry amusement is the detective's social lubricant — use it sparingly.",
        ],
        "reference_desc": "Brisk pace. Moderate dynamic range. Strategic pause placement (thinking pauses). High clarity. Moderate energy variation.",
        "score_weights": {"clarity": 0.30, "pause_ratio": 0.25, "consistency": 0.25, "stutters": 0.20},
    },

    "🪖 Drill Sergeant": {
        "category": "Modern",
        "description": "Controlled explosion. Maximum volume, maximum precision. Every word a bullet.",
        "difficulty": "Beginner",
        "example_pros": ["R. Lee Ermey", "Louis Gossett Jr.", "Samuel L. Jackson"],
        "vocal_qualities": [
            "Loud, projected, no holding back",
            "Every word sharp and fully articulated even at volume",
            "Machine-gun pace during reprimands, deadly slow when threatening",
            "Zero tolerance for imprecision — this character corrects themselves immediately",
            "Rhetorical questions delivered as accusations",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (140, 195),
            "pause_ratio":        (0.05, 0.16),
            "energy_consistency": (0.23, 0.34),
            "dynamic_range_db":   (20, 35),
            "max_long_pause_sec": 1.0,
            "clarity_floor_db":  -28,
        },
        "common_mistakes": [
            "Losing clarity at high volume — every word must still land",
            "Inconsistent energy — real drill sergeants never drop the authority",
            "Sounding angry instead of in-control — this character is using volume as a TOOL",
        ],
        "pro_tips": [
            "Project to the back of the room — your voice should carry 100 feet.",
            "Consonants are your weapon: T, P, K should snap like rifle bolts.",
            "The deadly slow moments are more terrifying than the fast loud ones.",
            "This is one character where physical stance completely determines vocal quality — stand at attention.",
        ],
        "reference_desc": "High volume baseline, high clarity even at loud levels, fast pace, wide dynamic range with peaks. Very low pause ratio during active delivery.",
        "score_weights": {"clarity": 0.35, "dynamic_range": 0.25, "consistency": 0.25, "stutters": 0.15},
    },

    "🩺 Doctor": {
        "category": "Modern",
        "description": "Calm authority, clinical precision, genuine care underneath.",
        "difficulty": "Beginner",
        "example_pros": ["Hugh Laurie (House)", "Sandra Oh", "George Clooney (ER)"],
        "vocal_qualities": [
            "Measured, authoritative but not cold",
            "Specific vocabulary delivered with complete confidence",
            "Strategic use of pause to let difficult information land",
            "Warm undertone — the care is real, the professionalism is a frame for it",
            "Brisk when the situation demands, slow when delivering news",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (125, 158),
            "pause_ratio":        (0.15, 0.28),
            "energy_consistency": (0.29, 0.37),
            "dynamic_range_db":   (12, 20),
            "max_long_pause_sec": 2.5,
            "clarity_floor_db":  -31,
        },
        "common_mistakes": [
            "Too cold — a good doctor has warmth underneath the professionalism",
            "Unclear diction — medical terms must land precisely",
            "No pause for gravity — the pause after bad news is a kindness",
        ],
        "pro_tips": [
            "You know what the patient doesn't know yet — pace accordingly.",
            "Medical jargon sounds authoritative when said without hesitation.",
            "The pause before 'I'm afraid...' is one of the most important pauses in any script.",
            "Warmth lives in your vowels — let them open slightly when expressing care.",
        ],
        "reference_desc": "High clarity. High consistency. Moderate pace. Strategic pauses for gravity. Narrow-to-moderate dynamic range.",
        "score_weights": {"clarity": 0.35, "consistency": 0.30, "pause_ratio": 0.20, "stutters": 0.15},
    },

    # ══════════════════════════════════════════════════════════════
    # COMEDIC
    # ══════════════════════════════════════════════════════════════

    "🤡 Bumbling Fool": {
        "category": "Comedic",
        "description": "Enthusiastic incompetence. Confident wrong answers. Lovably chaotic.",
        "difficulty": "Beginner",
        "example_pros": ["John Ratzenberger", "Dom DeLuise", "Jim Varney"],
        "vocal_qualities": [
            "Fast, enthusiastic, trips over own words",
            "High energy, upward inflection on everything",
            "Self-interruptions and corrections that make things worse",
            "Breathless quality — always rushing to share bad ideas",
            "Laugh or chuckle built into delivery",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (155, 210),
            "pause_ratio":        (0.06, 0.16),
            "energy_consistency": (0.08, 0.23),
            "dynamic_range_db":   (20, 35),
            "max_long_pause_sec": 0.8,
            "clarity_floor_db":  -36,
        },
        "common_mistakes": [
            "Being too composed — the fool is genuinely flustered",
            "Not enough self-interruption — the comedy lives in the tripping over words",
            "Deliberate stumbles feel fake — the chaos must feel involuntary",
        ],
        "pro_tips": [
            "Stumble on purpose but make it feel accidental — that's the craft.",
            "Breathe too much — the fool is always slightly out of breath.",
            "High energy IS the character — you cannot overdo the enthusiasm.",
            "Stutter flags in analysis may actually be in-character moments — review before cutting.",
        ],
        "reference_desc": "Fast pace, low pause ratio, high dynamic variation, low consistency. Some stutter/trip-over moments are correct for this character.",
        "score_weights": {"speech_rate": 0.25, "dynamic_range": 0.30, "pause_ratio": 0.25, "consistency": 0.20},
    },

    "😏 Sarcastic Sidekick": {
        "category": "Comedic",
        "description": "The voice of reason nobody asked for. Dry, done, devastatingly accurate.",
        "difficulty": "Intermediate",
        "example_pros": ["Anya Taylor-Joy", "Danny DeVito", "Aubrey Plaza"],
        "vocal_qualities": [
            "Flat affect that implies volumes",
            "Slightly slower than average — each word chosen to wound or illuminate",
            "Elongated vowels on the sarcastic words",
            "Occasional deep sigh before answering",
            "Warmth at the very end — they do care, despite everything",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (110, 148),
            "pause_ratio":        (0.16, 0.30),
            "energy_consistency": (0.23, 0.33),
            "dynamic_range_db":   (13, 23),
            "max_long_pause_sec": 2.0,
            "clarity_floor_db":  -33,
        },
        "common_mistakes": [
            "Announcing the sarcasm — if you have to signal it, you've lost it",
            "No warmth at all — then it's just mean, not funny",
            "Too fast — the sidekick LIVES in the pause before the punchline",
        ],
        "pro_tips": [
            "Deadpan is a superpower. The less you perform the joke, the funnier it lands.",
            "The pause BEFORE the sarcastic answer is where the comedy lives.",
            "One genuine moment of warmth per scene makes everything else funnier by contrast.",
            "Elongate the vowel in the key sarcastic word — 'Oh, how FASCINATING.'",
        ],
        "reference_desc": "Moderate pace. Strategic pauses (before punchlines). Moderate dynamic range. Flat affect with occasional warmth spikes.",
        "score_weights": {"pause_ratio": 0.30, "consistency": 0.25, "clarity": 0.25, "dynamic_range": 0.20},
    },

    "🧐 Pompous Noble": {
        "category": "Comedic",
        "description": "Magnificently self-important. Every word is a gift to an undeserving world.",
        "difficulty": "Beginner",
        "example_pros": ["Hugh Laurie (Wooster)", "Rowan Atkinson (Blackadder)", "Stephen Fry (Jeeves)"],
        "vocal_qualities": [
            "Elevated, over-articulated RP accent",
            "Dramatic pauses for self-importance, not meaning",
            "Occasional harrumphing and clearing of throat",
            "Over-emphasis on adjectives about oneself",
            "The voice of someone who has never doubted themselves for a second",
        ],
        "benchmarks": {
            "speech_rate_wpm":    (105, 140),
            "pause_ratio":        (0.22, 0.40),
            "energy_consistency": (0.23, 0.33),
            "dynamic_range_db":   (15, 28),
            "max_long_pause_sec": 3.0,
            "clarity_floor_db":  -30,
        },
        "common_mistakes": [
            "Not pompous ENOUGH — fully commit to the self-importance",
            "Not enough pause — the pompous noble believes their words deserve to echo",
            "Too fast — this person believes their thoughts are profound and must be savored",
        ],
        "pro_tips": [
            "Chin up — literally. It changes everything about the vocal placement.",
            "Pause after your best sentences as if waiting for applause.",
            "The comedy is in the sincerity — this character is NOT in on the joke.",
            "Over-articulate every consonant — this is a person who was taught elocution by professionals.",
        ],
        "reference_desc": "High clarity, over-articulated consonants. Moderate-to-slow pace. Strategic pauses (self-importance, not meaning). Some dramatic energy variation.",
        "score_weights": {"clarity": 0.30, "pause_ratio": 0.30, "consistency": 0.20, "dynamic_range": 0.20},
    },
}


# ── Category Index ────────────────────────────────────────────────────────────

CATEGORIES = {
    "Fantasy":    ["🧙 Wizard", "⚔️ Knight", "🧝 Elf", "🐉 Dragon", "👑 Dark Lord"],
    "Sci-Fi":     ["🤖 Robot / AI", "👽 Alien", "🦾 Cyborg", "🚀 Space Commander"],
    "Villain":    ["😈 Classic Villain", "😤 Menacing Villain", "🕸️ Manipulative Villain", "🤪 Unhinged Villain"],
    "Hero":       ["🦸 Classic Hero", "😔 Reluctant Hero", "🖤 Anti-Hero"],
    "Creature":   ["👹 Monster", "🐗 Beast", "👺 Goblin", "🌌 Ancient Being"],
    "Historical": ["🏚️ Medieval Peasant", "🎩 Victorian Noble", "🏛️ Roman General"],
    "Modern":     ["📺 News Anchor", "🔍 Detective", "🪖 Drill Sergeant", "🩺 Doctor"],
    "Comedic":    ["🤡 Bumbling Fool", "😏 Sarcastic Sidekick", "🧐 Pompous Noble"],
}

CATEGORY_EMOJIS = {
    "Fantasy": "🏰", "Sci-Fi": "🚀", "Villain": "😈",
    "Hero": "🦸", "Creature": "👹", "Historical": "🏛️",
    "Modern": "🎙️", "Comedic": "😂",
}


def get_character(name: str) -> Dict:
    return CHARACTER_DB.get(name, {})


def get_category_characters(category: str) -> List[str]:
    return CATEGORIES.get(category, [])


def get_all_categories() -> List[str]:
    return list(CATEGORIES.keys())


# ── Character Scoring ─────────────────────────────────────────────────────────

def score_character(results: dict, character_name: str) -> Dict:
    """
    Score a recording against a character archetype.
    Returns scores, feedback, tips, reference description.
    """
    import math

    char = CHARACTER_DB.get(character_name)
    if not char:
        return {"error": f"Character '{character_name}' not found"}

    benchmarks = char["benchmarks"]
    samples    = results["samples"]
    sr         = results["sample_rate"]
    duration   = results["duration"]
    stats      = results["stats"]
    silence_r  = results["silence_regions"]

    scores   = {}
    feedback = []

    def db_to_lin(db): return math.pow(10, db / 20.0)
    def rms_chunk(s): return math.sqrt(sum(x*x for x in s) / len(s)) if s else 0.0
    def range_score(v, lo, hi):
        """Bell-curve: 100 at midpoint, 60 at edges, drops outside."""
        mid = (lo + hi) / 2.0
        hw  = (hi - lo) / 2.0 + 1e-12
        z   = (v - mid) / hw
        return max(0, min(100, int(100 * math.exp(-0.5108 * z * z))))

    # ── Pause Ratio ──────────────────────────────────────────────
    total_sil  = sum(r['end'] - r['start'] for r in silence_r)
    pause_ratio = total_sil / max(1.0, duration)
    lo, hi = benchmarks["pause_ratio"]
    scores["pause_ratio"] = range_score(pause_ratio, lo, hi)
    if scores["pause_ratio"] < 70:
        if pause_ratio < lo:
            feedback.append(("⏸ Pacing", f"Not enough silence for {character_name}. "
                f"You're at {pause_ratio*100:.0f}% pause ratio — target is {lo*100:.0f}–{hi*100:.0f}%. "
                f"Slow down and let moments breathe."))
        else:
            feedback.append(("⏸ Pacing", f"Too much silence for {character_name}. "
                f"You're at {pause_ratio*100:.0f}% — target is {lo*100:.0f}–{hi*100:.0f}%. "
                f"Tighten the delivery."))

    # ── Speech Rate (estimated) ───────────────────────────────────
    speech_time = duration - total_sil
    # Rough WPM: ~1.8 syllables per second average for English
    est_wpm = (speech_time * 1.8 * 0.75)  # syllables → words rough conversion
    # Cap at a reasonable range for estimation
    lo_wpm, hi_wpm = benchmarks["speech_rate_wpm"]
    scores["speech_rate"] = range_score(est_wpm, lo_wpm, hi_wpm)

    # ── Energy Consistency ────────────────────────────────────────
    frame_size = int(sr * 0.1)
    thresh = db_to_lin(benchmarks.get("clarity_floor_db", -36))
    speech_levels = []
    for i in range(0, len(samples) - frame_size, frame_size):
        chunk = samples[i: i + frame_size]
        level = rms_chunk(chunk)
        if level > thresh:
            speech_levels.append(level)

    if len(speech_levels) > 4:
        mean_e = sum(speech_levels) / len(speech_levels)
        variance = sum((x - mean_e)**2 for x in speech_levels) / len(speech_levels)
        cv = math.sqrt(variance) / (mean_e + 1e-12)
        consistency = max(0.0, 1.0 - min(1.0, cv * 1.5))
        lo, hi = benchmarks["energy_consistency"]
        scores["consistency"] = range_score(consistency, lo, hi)
        if scores["consistency"] < 70:
            if consistency < lo:
                feedback.append(("📊 Energy", f"Energy too variable for {character_name}. "
                    f"Consistency: {consistency*100:.0f}% — target {lo*100:.0f}–{hi*100:.0f}%."))
            else:
                feedback.append(("📊 Energy", f"Energy too flat for {character_name}. "
                    f"This character needs more dynamic variation. "
                    f"Consistency: {consistency*100:.0f}% — target {lo*100:.0f}–{hi*100:.0f}%."))
    else:
        scores["consistency"] = 50

    # ── Dynamic Range ─────────────────────────────────────────────
    if speech_levels:
        max_level = max(speech_levels)
        min_level = max(min(speech_levels), 1e-9)
        dyn_range_db = 20 * math.log10(max_level / min_level)
        lo, hi = benchmarks["dynamic_range_db"]
        scores["dynamic_range"] = range_score(dyn_range_db, lo, hi)
        if scores["dynamic_range"] < 70:
            if dyn_range_db < lo:
                feedback.append(("🎚 Dynamic Range", f"Not enough dynamic variation for {character_name}. "
                    f"Range: {dyn_range_db:.1f} dB — target {lo}–{hi} dB. Use more contrast between loud and soft."))
            else:
                feedback.append(("🎚 Dynamic Range", f"Too much dynamic variation for {character_name}. "
                    f"Range: {dyn_range_db:.1f} dB — target {lo}–{hi} dB. Even it out."))
    else:
        scores["dynamic_range"] = 50

    # ── Stutter Count ─────────────────────────────────────────────
    stutter_tol = benchmarks.get("stutter_tolerance", 0.01)
    max_ok = max(1, int(stutter_tol * duration))
    stutter_penalty = max(0, stats['stutter_count'] - max_ok)
    scores["stutters"] = max(0, 100 - stutter_penalty * 15)
    if stats['stutter_count'] > max_ok:
        feedback.append(("🔁 Delivery", f"{stats['stutter_count']} stutter(s) detected. "
            f"For {character_name}, aim for fewer than {max_ok+1}. Re-record flagged sections."))

    # ── Clarity ───────────────────────────────────────────────────
    unclear_penalty = stats['unclear_count']
    scores["clarity"] = max(0, 100 - unclear_penalty * 12)
    if stats['unclear_count'] > 0:
        is_ok_unclear = char.get("benchmarks", {}).get("clarity_floor_db", -36) <= -38
        if not is_ok_unclear:
            feedback.append(("🔊 Clarity", f"{stats['unclear_count']} unclear section(s). "
                f"{character_name} requires clear diction — check mic distance and re-record."))

    # ── Overall Score ─────────────────────────────────────────────
    weights = char.get("score_weights", {
        "pause_ratio": 0.25, "speech_rate": 0.20,
        "consistency": 0.20, "dynamic_range": 0.20, "clarity": 0.15
    })
    key_map = {
        "pause_ratio":   "pause_ratio",
        "speech_rate":   "speech_rate",
        "consistency":   "consistency",
        "dynamic_range": "dynamic_range",
        "clarity":       "clarity",
        "stutters":      "stutters",
    }
    total_w = sum(weights.values())
    overall = int(sum(
        scores.get(key_map.get(k, k), 70) * v
        for k, v in weights.items()
    ) / total_w)

    grade = "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 70 else "D" if overall >= 60 else "F"

    return {
        "character":      character_name,
        "category":       char["category"],
        "overall":        overall,
        "grade":          grade,
        "scores":         scores,
        "feedback":       feedback,
        "pro_tips":       char["pro_tips"],
        "common_mistakes": char["common_mistakes"],
        "vocal_qualities": char["vocal_qualities"],
        "reference_desc": char["reference_desc"],
        "example_pros":   char["example_pros"],
        "difficulty":     char["difficulty"],
        "description":    char["description"],
    }
