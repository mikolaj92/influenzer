"""Ship vs patch/typo/chore noise. Waitlist is not a ship. A merge log is not a ship.

Tryable is a README+URL heuristic. Look does not run the project.
Launching on watch is silence. Code in look is untrusted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

_README_ONLY_RE = re.compile(r"(?i)^\s*readme(?:\.md)?\s*[-:]?\s*only\b")
_DOC_PATH_ONLY_RE = re.compile(
    r"(?i)^\s*(?:\.\/)?(?:docs?|documentation)(?:\/[A-Za-z0-9_.@+ -]+)+\/?\s*$"
)
_PATCH_ONLY_RE = re.compile(
    r"(?i)^\s*(?:docs|style|test|refactor|build)(?:\([^)]*\))?:\s|"
    r"^\s*(?:fix(?:es)?\s+)?(?:a\s+)?typo\b|"
    r"\btypo\b|"
    r"^\s*patch\b"
)
_COMMIT_NOISE_RE = re.compile(
    r"(?i)^\s*(?:chore|typo|lint|ci|wip|bump\s+(?:version|deps)|fix(?:es)?\s+tests|merge\s+branch)\b"
)
# Dependency automation is handled by the bot-bump gate (#85), not by the
# human docs/typo/chore silence rule below.
_BOT_BUMP_RE = re.compile(
    r"(?i)(?:\b(?:dependabot|renovate|github-actions)(?:\[bot\])?\b|"
    r"^\s*(?:chore(?:\([^)]*\))?:\s*)?bump\b|"
    r"^\s*chore(?:\([^)]*\))?:\s*(?:update|upgrade)\b.*\b"
    r"(?:deps?|dependencies|lockfiles?|actions?)\b)"
)
_MERGED_PR_PREFIX_RE = re.compile(r"(?i)^\s*merged\s+pr\s+#\d+\s*:\s*")
_SHIP_TITLE_RE = re.compile(
    r"(?i)(?:^feat(?:ure)?(?:\([^)]*\))?:\s|"
    r"\b(?:ship(?:ped)?|launch(?:ed)?|released?)\b|"
    r"^add(?:ed)?\s)"
)
_INSTALL_RE = re.compile(
    r"(?i)\b(?:pip(?:x)? install|uv add|uv pip install|uv run|npm (?:i|install)|"
    r"pnpm add|yarn add|cargo install|go install|brew install)\b"
)
_WAITLIST_RE = re.compile(
    r"(?i)(?:"
    r"\bwaitlists?\b"
    r"|\bcoming\s+soon\b"
    r"|\bjoin\s+(?:the|our|my)\s+(?:beta|waitlists?|lists?|mailing\s+lists?)\b"
    r"|\bsign\s*[- ]?up\s+to\s+get\s+(?:early\s+)?access\b"
    r"|\bsign\s*[- ]?up\s+for\s+(?:(?:early\s+)?access|(?:the|our|my)\s+(?:beta|waitlists?|lists?))\b"
    r"|\bget\s+on\s+(?:the|our|my)\s+(?:beta|waitlists?|lists?)\b"
    r"|\bget\s+early\s+access\b"
    r"|\brequest\s+(?:early\s+)?access\b"
    r"|\blanding\s+page\b"
    r"|\bno\s+demo\b"
    r")"
)
_EVENT_RE = re.compile(
    r"(?i)(?:"
    r"\bwebinars?\b"
    r"|\bmeet[- ]?ups?\b"
    r"|\bcalendars?\b(?!\s+year\b)"
    r"|\bkalendarz(?:e|a|u|owi|em|ach)?\b"
    r"|\bwydarzeni(?:e|a|u|em|om|ami|ach)\b"
    r"|\bjoin\s+us\s+(?:this\s+|next\s+)?"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)\b"
    r"|\bdo[lł][aą]cz(?:cie)?\s+(?:do\s+nas\s+)?(?:w\s+)?"
    r"(?:poniedzia[lł]ek|wtorek|[sś]rod[eę]|czwartek|pi[aą]tek)\b"
    r")"
)
_CALENDAR_FILLER_RE = re.compile(
    r"(?i)(?:"
    r"\bhappy\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|holidays?)\b"
    r"|\bhappy\s+new\s+year\b"
    r"|\bmerry\s+christmas\b"
    r"|\bseason['’]?s\s+greetings\b"
    r"|\b(?:repo(?:sitory)?|project)\s+(?:birthday|anniversary)\b"
    r"|\bbirthday\s+of\s+(?:the\s+)?(?:repo(?:sitory)?|project)\b"
    r"|\b(?:repo(?:sitory)?|project)\s+turns\s+\d+\b"
    r"|\burodzin(?:y|om|ach)?\s+(?:repo(?:zytorium)?|projektu)\b"
    r"|\brocznic[aeyę]\s+(?:repo(?:zytorium)?|projektu)\b"
    r"|\bweso[lł]ych\s+[sś]wi[aą]t\b"
    r"|\bz\s+okazji\s+[sś]wi[aą]t\b"
    r"|\bmi[lł]ego\s+(?:pi[aą]tku|weekendu)\b"
    r"|\btgif\b"
    r"|\b[sś]wi[eę]t(?:a|o)\b"
    r")"
)
_COUNTER_TOTAL = r"(?:n|\d{1,3}(?:,\d{3})+|(?:\d+))(?:\.\d+)?[kmb]?"
_COUNTER_UNIT = (
    r"(?:github\s+)?(?:stars?|stargazers?|follows?(?!-?ups?\b|ing\b)|"
    r"followers?|watchers?|gwiazd(?:ek|ki|ka|k\u0105)?|obserwacj\w*|obserwuj\w*)"
)
_COUNTER_THANKS_RE = re.compile(
    r"(?i)(?:"
    r"\bthanks?\s+(?:to\s+)?(?:everyone\s+)?for\s+"
    r"(?:all\s+)?(?:the\s+|our\s+|every\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?{_COUNTER_UNIT}\b"
    r"|\bthank\s+you\s+(?:to\s+)?(?:everyone\s+)?for\s+"
    r"(?:all\s+)?(?:the\s+|our\s+|every\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?{_COUNTER_UNIT}\b"
    r"|\bgrateful\s+for\s+"
    r"(?:all\s+)?(?:the\s+|our\s+|every\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?{_COUNTER_UNIT}\b"
    r"|\bdzi[eę]k\w*\s+za\s+(?:ka[zż]d\w*\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?(?:gwiazd(?:ek|ki|ka|k\u0105)?|obserwacj\w*|follow(?:y|ów)?)\b"
    r"|\bpodzi[eę]kowani\w*\s+za\s+(?:licznik|gwiazd|follow|obserw)"
    r"|\bmilestone\s+follow\b"
    r"|\b(?:star|follow(?:er)?)\s+milestone\b"
    rf"|\b{_COUNTER_TOTAL}\s+follow(?:er)?\s+milestone\b"
    r"|\b(?:hit|reached|crossed)\s+"
    rf"{_COUNTER_TOTAL}\s+{_COUNTER_UNIT}\b"
    r".{0,40}\b(?:thanks?|thank\s+you)\b"
    r")"
)
_FOG_RE = re.compile(
    r"(?i)(?:"
    r"\bsubtweets?\b"
    r"|\bsubtweeting\b"
    r"|\byou[- ]know[- ]who\b"
    r"|\bif\s+you\s+know\s*,?\s+you\s+know\b"
    r"|\bthose\s+who\s+know\s*,?\s+know\b"
    r"|\bthey\s+know\s+who\s+they\s+are\b"
    r"|\biykyk\b"
    r"|\ba\s+certain\s+(?:someone|somebody|project|tool|repo|competitor|person)\b"
    r"|\b(?:we\s+)?(?:won['’]?t|do\s+not|don['’]?t)\s+name\s+names\b"
    r"|\bnot\s+naming\s+names\b"
    r"|\bunnamed\s+(?:competitor|project|tool|repo|someone)\b"
    r"|\bread(?:ing)?\s+between\s+the\s+lines\b"
    r"|\bhint\s+hint\b"
    r"|\baluzj[aąeęi]\b"
    r"|\bwiecie\s+kto\b"
    r"|\bnie\s+wymieniamy?\s+nazw"
    r"|\bpewien\s+(?:kto[sś]|projekt|narz[eę]dzie)\b"
    r"|\bmg[lł]a\b"
    r")"
)
_FOUNDER_JOURNAL_RE = re.compile(
    r"(?i)(?:"
    r"\bdesk\s+setups?\b"
    r"|\bdesk\s+tours?\b"
    r"|\boffice\s+tours?\b"
    r"|\bworkstation\s+setups?\b"
    r"|\bwhat(?:['’]?s| is)\s+on\s+(?:my|our)\s+desk\b"
    r"|\btools?\s+(?:i|we|they)\s+use[ds]?\b"
    r"|\bgear\s+(?:i|we)\s+use[ds]?\b"
    r"|\ba?\s*days?\s+in\s+(?:the|my|our|a)\s+life\b"
    r"|\bday[- ]in[- ]the[- ]life\b"
    r"|\bmorning\s+routines?\b"
    r"|\bmorning\s+rituals?\b"
    r"|\bfounder(?:['’]?s)?\s+(?:journal|diary|log)\b"
    r"|\bbuilder(?:['’]?s)?\s+(?:journal|diary)\b"
    r"|\bdziennik(?:u|iem|owi)?\s+za[lł]o[zż]yciel"
    r"|\bsetup\s+biurk"
    r"|\bbiurk(?:o|a)\s+(?:setup|tour)"
    r"|\bnarz[eę]dzi(?:a|e)\s+(?:kt[oó]r(?:e|ych)\s+)?u[zż]ywam\b"
    r"|\bnarz[eę]dzi(?:a|e)\s+(?:kt[oó]r(?:e|ych)\s+)?u[zż]ywamy\b"
    r"|\bmoje\s+narz[eę]dzi"
    r"|\bdzie[nń]\s+z\s+[zż]ycia\b"
    r"|\bporann[aąe]\s+rutyn"
    r"|\brutyna\s+porann"
    r")"
)
_PAYMENT_GATE_RE = re.compile(
    r"(?i)(?:"
    r"^\s*(?:(?:payment|billing|subscription|credit[- ]?card|card)[ -]+"
    r"(?:wall|gate|required)|paywall)\s*[.!]?\s*$"
    r"|\b(?:subscribe|pay)\s+to\s+(?:continue|view|access|try|use|unlock)\b"
    r"|\b(?:subscription|payment|billing|credit[- ]?card|debit[- ]?card|"
    r"card|payment\s+method)\s+(?:is\s+|are\s+)?required\b"
    r"|\b(?:artifact|demo|site|page|product|trial|access)\b.{0,36}\b"
    r"(?:requires?|demands?)\s+(?:an?\s+)?(?:paid\s+)?"
    r"(?:subscription|payment|credit[- ]?card|debit[- ]?card|card|payment\s+method)\b"
    r"|\b(?:enter|add|provide|submit)\s+(?:your\s+|a\s+)?"
    r"(?:credit[- ]?card|debit[- ]?card|card\s+(?:details?|number)|payment\s+method)\s+"
    r"(?:to|before)\s+(?:continue|view|access|try|use|unlock|start)\b"
    r"|\b(?:free\s+)?trial\s+(?:requires?|needs?)\s+(?:an?\s+)?"
    r"(?:credit[- ]?card|debit[- ]?card|card|payment\s+method)\b"
    r"|\b(?:credit[- ]?card|debit[- ]?card|card|payment)\s+before\s+"
    r"(?:the\s+)?(?:artifact|demo|product|trial|access)\b"
    r"|\b(?:behind|blocked\s+by)\s+(?:an?\s+|the\s+)?"
    r"(?:paywall|payment\s+(?:wall|gate)|subscription\s+(?:wall|gate)|checkout)\b"
    r"|\bkart(?:a|ę|y)\s+(?:przed\s+produktem|jest\s+wymagana|wymagana)\b"
    r"|\bwymaga\s+(?:podania\s+)?(?:karty|p[łl]atno[sś]ci|subskrypcji)\b"
    r"|\bsubskrybuj\s*[,;:]?\s+(?:aby|[zż]eby)\s+"
    r"(?:kontynuowa[cć]|wej[sś][cć]|zobaczy[cć]|wypr[oó]bowa[cć]|skorzysta[cć])\b"
    r")"
)
_PAYMENT_GATE_CLEARED_RE = re.compile(
    r"(?i)(?:"
    r"\bno\s+(?:credit[- ]?|debit[- ]?)?card\s+(?:is\s+)?required\b"
    r"|\bno\s+(?:payment|paid\s+subscription)\s+(?:is\s+)?required\b"
    r"|\b(?:credit[- ]?card|debit[- ]?card|card|payment|subscription)\s+"
    r"(?:is\s+)?(?:not\s+required|optional)\b"
    r"|\b(?:bez\s+karty|nie\s+wymaga\s+(?:karty|p[łl]atno[sś]ci|subskrypcji))\b"
    r")"
)
_LEAD_MAGNET_RE = re.compile(
    r"(?i)(?:"
    r"\blead[- ]magnets?\b"
    r"|\bebooks?\b"
    r"|\be[- ]books?\b"
    r"|\bfree\s+guides?\b"
    r"|\bfree\s+pdfs?\b"
    r"|\btypeforms?\b"
    r"|\bdownload\s+(?:the|our|my)\s+(?:free\s+)?(?:guide|ebook|e-book|pdf|checklist|whitepaper)\b"
    r"|\bget\s+(?:the|our|my)\s+(?:free\s+)?(?:guide|ebook|e-book|pdf)\b"
    r"|\benter\s+your\s+e[- ]?mail\s+to\s+(?:download|unlock|get|receive)\s+"
    r"(?:the\s+|our\s+|my\s+)?(?:free\s+)?(?:guide|ebook|e-book|pdf|checklist)\b"
    r"|\be[- ]?mail\s+to\s+(?:download|unlock|get|receive)\s+"
    r"(?:the\s+|our\s+|my\s+)?(?:free\s+)?(?:guide|ebook|e-book|pdf|checklist)\b"
    r"|\bswap\s+(?:your\s+)?e[- ]?mail\s+for\b"
    r"|\bgated\s+(?:pdf|content|guide|ebook|e-book)\b"
    r"|\bopt[- ]in\s+(?:form|pdf|guide|ebook)\b"
    r"|\bemail\s+gates?\b"
    r"|\bmail\s+gates?\b"
    r"|\bmagnet\s+za\s+mail"
    r"|\be[- ]?book\s+za\s+mail"
    r"|\bdarmow(?:y|e|a)\s+(?:przewodnik|ebook|e-book|pdf)\b"
    r"|\bza\s+maila\b"
    r"|\bbramk[aąę]\s+mail"
    r")"
)
_APOLOGY_RE = re.compile(
    r"(?i)(?:"
    r"\bwe\s+hear\s+you\b"
    r"|\bwe(?:['’]?ve|\s+have)\s+heard\s+you\b"
    r"|\bcrisis\s+(?:post|statement|message|update|response)\b"
    r"|\b(?:public|official)\s+apolog(?:y|ies)\b"
    r"|(?:^|\n)\s*(?:sorry|an?\s+apology|apologies)\s*[.!]?\s*(?=$|\n)"
    r"|\bsorry\s*(?:[.!]\s+|[—:-]\s+)(?=\S)"
    r"|\bwe\s+(?:apologi[sz]e|are\s+sorry)\b"
    r"|\bwe(?:['’]?re|\s+are)\s+sorry\b"
    r"|\b(?:we(?:['’]?re|\s+are)\s+)?sorry\s+(?:for|about|that|to)\b"
    r"|\bour\s+apologies\b"
    r"|\bprzepraszam(?:y)?\b"
    r"|\bprzeprosiny\b"
    r"|\bkryzysow(?:y|a|e)\s+(?:post|wpis|komunikat|o[sś]wiadczenie)\b"
    r")"
)
# Product EOL is a tombstone, not a launch. Keep technical shutdown features
# (graceful shutdown, worker cleanup) out unless the copy says the product ends.
_SUNSET_RE = re.compile(
    r"(?im)(?:"
    r"(?:^|\n)\s*(?:eol|end[- ]of[- ]life|sunset(?:ting)?|shutting\s+down|"
    r"we(?:['’]re|\s+are)\s+shutting\s+down|"
    r"(?:product|service|app(?:lication)?|project|platform|api|tool)\s+shutdown)"
    r"\s*[.!]?\s*(?=$|\n)"
    r"|\breleased?\s+(?:the\s+|our\s+)?(?:eol|end[- ]of[- ]life|sunset)"
    r"(?:\s+(?:notice|announcement))?\s*(?:[.!]|$)"
    r"|\b(?:eol|end[- ]of[- ]life)\s+(?:announcement|notice|for|of)\b"
    r"|\b(?:announc(?:e|es|ed|ing)|reaches?|reached)\s+"
    r"(?:the\s+|its\s+|our\s+)?(?:eol|end[- ]of[- ]life)\b"
    r"|\bwe(?:['’]re|\s+are|\s+will\s+be|['’]ll\s+be)\s+"
    r"(?:shutting\s+down|sunsetting|discontinuing)\b"
    r"|\b(?:shutting\s+down|sunsetting|discontinuing|retiring)\s+"
    r"(?:the\s+|our\s+|this\s+)?"
    r"(?:product|service|app(?:lication)?|project|platform|api|tool|repo(?:sitory)?)\b"
    r"|\b(?:product|service|app(?:lication)?|project|platform|api|tool|repo(?:sitory)?)\s+"
    r"(?:(?:is|will\s+be|has\s+been|is\s+being)\s+)?"
    r"(?:shutting\s+down|being\s+sunset|sunset(?:ted)?|discontinued|retired)\b"
    r"|\b(?:ceas(?:e|es|ed|ing)|end(?:s|ed|ing)?)\s+(?:all\s+)?operations\b"
    r"|\b(?:wy[lł][aą]czeni\w*|wy[lł][aą]cz(?:amy|ymy|ony|ona|one|yć)|"
    r"wygasz(?:amy|anie|any|ana|ane|ać)|zamykamy)\s+"
    r"(?:ten\s+|t[eę]\s+|nasz(?:ą|a|e)?\s+)?"
    r"(?:produkt\w*|us[lł]ug\w*|aplikacj\w*|serwis\w*|platform\w*|projekt\w*)\b"
    r"|\b(?:produkt\w*|us[lł]ug\w*|aplikacj\w*|serwis\w*|platform\w*|projekt\w*)\s+"
    r"(?:(?:zostanie|zostaje|jest|b[eę]dzie)\s+)?"
    r"(?:wy[lł][aą]cz\w*|wygasz\w*|zamkni[eę]t\w*)\b"
    r"|\bkoniec\s+(?:[zż]ycia|wsparcia)\s+(?:dla\s+)?"
    r"(?:produkt\w*|us[lł]ug\w*|aplikacj\w*|serwis\w*|platform\w*|projekt\w*)\b"
    r")"
)
_LOGO_REVEAL_RE = re.compile(
    r"(?i)(?:"
    r"\bre-?brands?(?:ing)?\b"
    r"|\bbrand\s+refresh(?:es)?\b"
    r"|\bnew\s+brands?\b"
    r"|\bvisual\s+identity\b"
    r"|\bbrand\s+identity\b"
    r"|\b(?:color|colour|brand|new)\s+palettes?\b"
    r"|\bpalet[aąęy]\b"
    r"|\bmood[- ]?boards?\b"
    r"|\blogo\s+reveals?\b"
    r"|\breveal(?:ing|s|ed)?\s+(?:the\s+|our\s+|a\s+)?(?:new\s+)?logos?\b"
    r"|\blogo\s+unveil(?:s|ed|ing)?\b"
    r"|\bunveil(?:ing|s|ed)?\s+(?:the\s+|our\s+|a\s+)?(?:new\s+)?logos?\b"
    r"|\bnew\s+logos?\b"
    r"|\blogo\s+drops?\b"
    r"|\blogo\s+redesigns?\b"
    r"|\bods[lł]on[aąęy]\s+logo\b"
    r"|\bods[lł]aniamy\s+logo\b"
    r"|\bods[lł]oni[eę]cie\s+logo\b"
    r"|\bnowe\s+logo\b"
    r"|\bnow[aą]\s+palet"
    r"|\bnowy\s+branding\b"
    r")"
)
_FOMO_RE = re.compile(
    r"(?i)(?:"
    r"\bfomo\b"
    r"|\blast\s+chances?\b"
    r"|\blast\s+calls?\b"
    r"|\bcount[- ]?downs?\b"
    r"|\bonly\s+(?:n|\d+)\s+(?:spots?|seats?|places?|slots?|tickets?)\b"
    r"|\bonly\s+(?:a\s+)?few\s+(?:spots?|seats?|places?|slots?)\b"
    r"|\blast\s+(?:n|\d+)\s+(?:spots?|seats?|places?|slots?)\b"
    r"|\blimited\s+(?:spots?|seats?|places?|slots?|tickets?)\b"
    r"|\b(?:spots?|seats?|places?|slots?)\s+(?:left|remaining)\b"
    r"|\blimited[- ]time\b"
    r"|\bending\s+soon\b"
    r"|\bdon['’]?t\s+miss\s+out\b"
    r"|\bwhile\s+supplies\s+last\b"
    r"|\bostatni[aea]\s+szans"
    r"|\btylko\s+(?:n|\d+)\s+miejsc"
    r"|\bostatni[ae]\s+miejsc"
    r"|\bodliczani"
    r")"
)
_MEME_RE = re.compile(
    r"(?i)(?:"
    r"\bmemes?\b"
    r"|\bdrake\b"
    r"|\bhotline\s+bling\b"
    r"|\bwojaks?\b"
    r"|\bsoyjaks?\b"
    r"|\breaction\s+(?:images?|gifs?|memes?|pics?|pictures?)\b"
    r"|\bmeme\s+(?:templates?|formats?|dumps?|boards?|walls?)\b"
    r"|\btablic[aąęy]\s+z\s+mem"
    r"|\b(?:sciana|ściana)\s+mem"
    r"|\bmem(?:y|ów|ow|ami|em|ie|ach|om)\b"
    r")"
)
_DECK_RE = re.compile(
    r"(?i)(?:"
    r"\bpitch\s+decks?\b"
    r"|\binvestor\s+(?:decks?|pitches?)\b"
    r"|\bslide\s+decks?\b"
    r"|\bslide\s+pdfs?\b"
    r"|\bpdf\s+(?:of\s+)?(?:the\s+)?slides?\b"
    r"|\bpdf\s+slajd"
    r"|\bslajd(?:y|ów|ami|ach|om|em)?\b"
    r"|\bone[- ]pagers?\b"
    r"|\bnotion\s+(?:one[- ]pager|page|doc)\b"
    r"|\bpitch(?:es)?\s+(?:pdf|slides?|deck)\b"
    r"|\b(?:our|the|this)\s+pitch\b"
    r"|\bpitch\s+(?:for|to)\s+(?:investors?|vcs?|angels?)\b"
    r"|\b(?:our|the|this)\s+decks?\b"
    r"|\bspeakerdecks?\b"
    r"|\bslideshare\b"
    r"|\bgoogle\s+slides\b"
    r"|\bdeck\s+nie\s+jest\s+artefakt"
    r")"
)
_LINKTREE_RE = re.compile(
    r"(?i)(?:"
    r"\blinktrees?\b"
    r"|\blinktr\.ee\b"
    r"|\bcarrds?\b"
    r"|\bbio\s+sites?\b"
    r"|\bbiosites?\b"
    r"|\blista\s+link"
    r"|\blink\s+lists?\b"
    r"|\blists?\s+of\s+links?\b"
    r"|\blink\s+boards?\b"
    r"|\ball\s+my\s+links?\b"
    r"|\bmy\s+links?\s+page\b"
    r"|\blinks?\s+page\b"
    r"|\bstron[aąeęy]\s+z\s+link"
    r"|\btablic[aąęy]\s+link"
    r"|\bbeacons\.ai\b"
    r"|\blinktree\s+nie\s+jest\s+artefakt"
    r")"
)
_CLOUD_DRIVE_RE = re.compile(
    r"(?i)(?:"
    r"\bgoogle\s+drives?\b"
    r"|\bdrives?\.google\b"
    r"|\bdropbox(?:es)?\b"
    r"|\bwetransfers?\b"
    r"|\bwe\.tl\b"
    r"|\bcloud\s+drives?\b"
    r"|\bonedrives?\b"
    r"|\b1drv\.ms\b"
    r"|\bdysk(?:u|iem|owi|ach|i)?\s+w\s+chmur"
    r"|\bdysk(?:u|iem|owi)?\s+google\b"
    r"|\bchmurow\w*\s+dysk"
    r"|\bdysk\s+w\s+chmurze\s+nie\s+jest\s+witryn"
    r")"
)
_SHIP_ARTIFACT_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:pull/\d+|issues/\d+|releases(?:/tag/[A-Za-z0-9._~-]+|/\d+))$"
)
# A compare page or one commit describes a change, not a product a stranger
# can try. Keep README blob URLs usable as the README source, but never accept
# these diff views as the artifact URL.
_GITHUB_DIFF_PATH_RE = re.compile(
    r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:compare|commit)(?:/|$)",
    re.I,
)
# Actions runs, jobs, and checks are CI plumbing, not a product artifact.
_GITHUB_ACTIONS_PATH_RE = re.compile(
    r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:actions|runs)(?:/|$)",
    re.I,
)
_MERGED_PR_FACT_RE = re.compile(r"(?i)^merged\s+pr\s+#\d+")
_TRYABLE_ARTIFACT_HOSTS = frozenset({"github.com"})
_UTM_QUERY_RE = re.compile(r"(?i)(?:^|[&])(?:utm_[a-z]+|fbclid|gclid|mc_cid|mc_eid)=")
_CLICK_HERE_RE = re.compile(r"(?i)(?:click[-_ ]here|kliknij[-_ ]tu(?:taj)?)")


def looks_like_patch_only(text: str) -> bool:
    stripped = text.strip()
    if _COMMIT_NOISE_RE.search(stripped):
        return True
    return bool(
        _PATCH_ONLY_RE.search(stripped)
        or _README_ONLY_RE.search(stripped)
        or _DOC_PATH_ONLY_RE.fullmatch(stripped)
    )


def looks_like_docs_chore_only(text: str) -> bool:
    """True for human docs/typo/chore changes, but not dependency bot bumps."""
    stripped = _MERGED_PR_PREFIX_RE.sub("", text).strip()
    if not stripped or _BOT_BUMP_RE.search(stripped):
        return False
    return bool(
        looks_like_patch_only(stripped)
        or _README_ONLY_RE.search(stripped)
        or _DOC_PATH_ONLY_RE.fullmatch(stripped)
    )


def all_changes_are_docs_chore(changes: Sequence[Any]) -> bool:
    """True when a non-empty change window contains only docs/typo/chore noise."""
    texts: list[str] = []
    for item in changes:
        if isinstance(item, Mapping):
            text = next(
                (
                    str(item.get(key) or "").strip()
                    for key in ("title", "subject", "message", "text")
                    if str(item.get(key) or "").strip()
                ),
                "",
            )
        else:
            text = str(item or "").strip()
        if text:
            texts.append(text)
    return bool(texts) and all(looks_like_docs_chore_only(text) for text in texts)


def looks_like_ship_title(text: str) -> bool:
    if looks_like_patch_only(text):
        return False
    return bool(_SHIP_TITLE_RE.search(text.strip()))


def looks_like_waitlist(text: str) -> bool:
    return bool(_WAITLIST_RE.search(text))


def looks_like_event(text: str) -> bool:
    """True for webinar / meetup / calendar / join us Thursday. Not a ship."""
    if not text or not text.strip():
        return False
    return bool(_EVENT_RE.search(text))


def looks_like_calendar_filler(text: str) -> bool:
    """True for a holiday, repo birthday, or happy Friday. A calendar does not write."""
    if not text or not text.strip():
        return False
    return bool(_CALENDAR_FILLER_RE.search(text))


def looks_like_counter_thanks(text: str) -> bool:
    """True for 'thanks for N stars' / a follower milestone. A thank-you is not an angle."""
    if not text or not text.strip():
        return False
    return bool(_COUNTER_THANKS_RE.search(text))


def looks_like_fog(text: str) -> bool:
    """True for a subtweet / you-know-who / unnamed allusion. Name it or stay silent."""
    if not text or not text.strip():
        return False
    return bool(_FOG_RE.search(text))


def looks_like_founder_journal(text: str) -> bool:
    """True for desk setup / tools I use / day in the life / morning routine. Lifestyle is not a product."""
    if not text or not text.strip():
        return False
    return bool(_FOUNDER_JOURNAL_RE.search(text))


def looks_like_payment_gate(text: str) -> bool:
    """True when a card, payment, or paid subscription precedes the product."""
    if not text or not text.strip():
        return False
    active_text = _PAYMENT_GATE_CLEARED_RE.sub("", text)
    return bool(_PAYMENT_GATE_RE.search(active_text))


def looks_like_lead_magnet(text: str) -> bool:
    """True for ebook / free guide / typeform for an email. A mail gate is not tryable."""
    if not text or not text.strip():
        return False
    return bool(_LEAD_MAGNET_RE.search(text))


def looks_like_apology(text: str) -> bool:
    """True for apology / crisis-response copy. It needs a separate new artifact."""
    if not text or not text.strip():
        return False
    return bool(_APOLOGY_RE.search(text))


def looks_like_sunset(text: str) -> bool:
    """True when copy announces product EOL or shutdown. A tombstone is not a ship."""
    if not text or not text.strip():
        return False
    return bool(_SUNSET_RE.search(text))


def looks_like_logo_reveal(text: str) -> bool:
    """True for rebrand / palette / moodboard / logo reveal. A look is not a ship."""
    if not text or not text.strip():
        return False
    return bool(_LOGO_REVEAL_RE.search(text))


def looks_like_fomo(text: str) -> bool:
    """True for only-N-spots / countdown / last chance. Pressure is not a product."""
    if not text or not text.strip():
        return False
    return bool(_FOMO_RE.search(text))


def looks_like_meme(text: str) -> bool:
    """True for Drake / wojak / reaction image / a meme board. A picture is not a product."""
    if not text or not text.strip():
        return False
    return bool(_MEME_RE.search(text))


def looks_like_deck(text: str) -> bool:
    """True for a pitch / PDF slides / Notion one-pager. A deck is not an artifact."""
    if not text or not text.strip():
        return False
    return bool(_DECK_RE.search(text))


def looks_like_linktree(text: str) -> bool:
    """True for Linktree / Carrd / bio site / a list of links. A board is not an artifact."""
    if not text or not text.strip():
        return False
    return bool(_LINKTREE_RE.search(text))


def looks_like_cloud_drive(text: str) -> bool:
    """True for Drive / Dropbox / WeTransfer. A file share is not a website."""
    if not text or not text.strip():
        return False
    return bool(_CLOUD_DRIVE_RE.search(text))


def is_ship_artifact(url: str | None) -> bool:
    if not url:
        return False
    return bool(_SHIP_ARTIFACT_RE.fullmatch(url.strip()))


def headline_prs(prs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in prs:
        title = str(item.get("title") or "")
        url = str(item.get("url") or "").strip()
        if looks_like_patch_only(title):
            continue
        if not looks_like_ship_title(title):
            continue
        if not is_ship_artifact(url):
            continue
        found.append(dict(item))
    return found


def readme_installable(text: str) -> bool:
    return bool(_INSTALL_RE.search(text))


def _normalized_host(host: str | None) -> str | None:
    value = (host or "").strip().rstrip(".").lower()
    if value.startswith("www."):
        value = value[4:]
    return value or None


def is_trusted_artifact_url(url: str | None) -> bool:
    """True only for https on github.com (or a host we add to the allowlist).

    Another origin, a shortener, a UTM-farm, or “kliknij tu” is silence.
    """
    if not url or not isinstance(url, str):
        return False
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    host = _normalized_host(parsed.hostname)
    if not host or not any(host == name or host.endswith("." + name) for name in _TRYABLE_ARTIFACT_HOSTS):
        return False
    if _GITHUB_DIFF_PATH_RE.match(parsed.path) or _GITHUB_ACTIONS_PATH_RE.match(parsed.path):
        return False
    if _UTM_QUERY_RE.search(parsed.query) or _CLICK_HERE_RE.search(raw):
        return False
    return True


def _https_url(value: object) -> bool:
    return is_trusted_artifact_url(value if isinstance(value, str) else None)


def readme_tryable_url(survey: Mapping[str, Any]) -> str | None:
    """README+URL only. Do not run the project. Code in look is untrusted."""
    if not readme_installable(str(survey.get("readme_text") or "")):
        return None
    url = survey.get("readme_url")
    if _https_url(url):
        return str(url)
    meta = survey.get("meta")
    if isinstance(meta, Mapping):
        for key in ("url", "homepageUrl"):
            candidate = meta.get(key)
            if _https_url(candidate):
                return str(candidate)
    return None


def looks_like_merged_pr_fact(text: str) -> bool:
    return bool(_MERGED_PR_FACT_RE.match(text.strip()))


def facts_are_merge_log(facts: Sequence[Mapping[str, Any]]) -> bool:
    """A stack of 'Merged PR #N: …' is changelog, not a tryable ship."""
    meat = [str(item.get("text") or "").strip() for item in facts if str(item.get("text") or "").strip()]
    if not meat:
        return False
    merge = [text for text in meat if looks_like_merged_pr_fact(text)]
    if not merge:
        return False
    return looks_like_merged_pr_fact(meat[0]) or len(merge) == len(meat)


def is_tryable(survey: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]) -> bool:
    """README+URL heuristic. A release is not a run. Launching is silence."""
    if facts_are_merge_log(facts) and not survey.get("releases"):
        return False
    return readme_tryable_url(survey) is not None
